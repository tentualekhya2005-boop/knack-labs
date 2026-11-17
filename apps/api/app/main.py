from contextlib import asynccontextmanager
import json
import time
import uuid
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errors import get_error_code, make_error_envelope
from app.core.logging import logger, redact_text
from app.routers import admin, auth, links, redirect


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    logger.info(f"Starting API service on port {settings.port}")
    yield
    # Graceful Shutdown on SIGTERM/SIGINT
    logger.info("Graceful shutdown initiated: draining in-flight requests and closing connection pools...")
    try:
        from app.db.session import engine
        engine.dispose()
    except Exception as e:
        logger.error(f"Error during engine disposal: {e}")

    try:
        from app.core.cache import cache_service
        if cache_service.redis_client:
            cache_service.redis_client.close()
    except Exception as e:
        logger.error(f"Error closing redis connection: {e}")
    logger.info("Graceful shutdown completed successfully.")


app = FastAPI(
    title="Link Shortener & Analytics API",
    description="B2B Multi-Tenant URL Shortener & Analytics API with Structured Logging & Error Envelope",
    version="0.3.0",
    lifespan=lifespan,
)


class RequestTracingMiddleware:
    """Pure ASGI middleware for request_id tracing, latency measurement, and structured logging.
    Avoids Starlette BaseHTTPMiddleware concurrency/deadlock issues with anyio and httpx ASGITransport.
    """

    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate X-Request-ID
        raw_headers = dict(scope.get("headers", []))
        incoming_id = raw_headers.get(b"x-request-id", b"").decode("latin1")
        request_id = incoming_id if incoming_id else f"req_{uuid.uuid4().hex[:12]}"

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        start_time = time.perf_counter()
        status_code = [200]
        response_started = [False]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_started[0] = True
                status_code[0] = message["status"]
                res_headers = list(message.get("headers", []))
                existing_header_names = [k.lower() for k, _ in res_headers]
                if b"x-request-id" not in existing_header_names:
                    res_headers.append((b"x-request-id", request_id.encode("latin1")))
                message["headers"] = res_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            status_code[0] = 500
            path = scope.get("path", "")
            method = scope.get("method", "")

            # Server-side structured diagnostic log with traceback and redacted secrets
            logger.error(
                f"Unhandled server error: {exc.__class__.__name__}",
                extra={
                    "request_id": request_id,
                    "route": path,
                    "method": method,
                    "status_code": 500,
                    "error_code": "INTERNAL_SERVER_ERROR",
                },
                exc_info=True,
            )

            # Return safe sanitized 500 response if response has not started
            if not response_started[0]:
                envelope = make_error_envelope(
                    status_code=500,
                    message="Internal Server Error",
                    request_id=request_id,
                    code="INTERNAL_SERVER_ERROR",
                    detail="Internal Server Error",
                )
                body = json.dumps(envelope).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("latin1")),
                        (b"x-request-id", request_id.encode("latin1")),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
        finally:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            path = scope.get("path", "")
            method = scope.get("method", "")
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"

            logger.info(
                f"{method} {path} -> {status_code[0]} ({latency_ms}ms)",
                extra={
                    "request_id": request_id,
                    "route": path,
                    "method": method,
                    "status_code": status_code[0],
                    "latency_ms": latency_ms,
                    "client_ip": client_ip,
                },
            )


app.add_middleware(RequestTracingMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    code = (
        "VALIDATION_ERROR"
        if exc.status_code in (400, 422) and "validation" in str(exc.detail).lower()
        else get_error_code(exc.status_code)
    )
    message = str(exc.detail) if isinstance(exc.detail, str) else "Request error"
    envelope = make_error_envelope(
        status_code=exc.status_code,
        message=message,
        request_id=request_id,
        code=code,
        detail=exc.detail,
    )
    headers = dict(exc.headers) if exc.headers else {}
    headers["X-Request-ID"] = request_id

    logger.warning(
        f"HTTP {exc.status_code}: {message}",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "error_code": code,
        },
    )
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    errors = exc.errors()
    error_messages = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
        for err in errors
    ]
    message = "; ".join(error_messages) if error_messages else "Validation failed"
    envelope = make_error_envelope(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=message,
        request_id=request_id,
        code="VALIDATION_ERROR",
        detail=error_messages,
    )

    logger.warning(
        f"Validation error: {message}",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": status.HTTP_400_BAD_REQUEST,
            "error_code": "VALIDATION_ERROR",
        },
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=envelope,
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    message = str(exc)
    envelope = make_error_envelope(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=message,
        request_id=request_id,
        code="VALIDATION_ERROR",
        detail=message,
    )

    logger.warning(
        f"Value error: {message}",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": status.HTTP_400_BAD_REQUEST,
            "error_code": "VALIDATION_ERROR",
        },
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=envelope,
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"

    # Server-side structured diagnostic log with traceback and redacted secrets
    logger.error(
        f"Unhandled server error: {exc.__class__.__name__}",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error_code": "INTERNAL_SERVER_ERROR",
        },
        exc_info=True,
    )

    # Clean, sanitized client response: NO stack trace, NO database credentials
    envelope = make_error_envelope(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal Server Error",
        request_id=request_id,
        code="INTERNAL_SERVER_ERROR",
        detail="Internal Server Error",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope,
        headers={"X-Request-ID": request_id},
    )


@app.get("/health")
def get_health():
    """Liveness probe: returns 200 OK immediately if the web process is running."""
    return {"ok": True}


@app.get("/ready")
def get_ready():
    """Readiness probe: validates connectivity to essential backend dependencies before receiving traffic."""
    dependencies = {}
    is_ready = True

    # 1. Check PostgreSQL connectivity
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            dependencies["database"] = "ready"
        finally:
            db.close()
    except Exception as exc:
        is_ready = False
        dependencies["database"] = f"unhealthy: {exc}"
        logger.error(f"Readiness check failed on database: {exc}")

    # 2. Check Redis connectivity (graceful degradation if cache is degraded)
    try:
        from app.core.cache import cache_service
        if cache_service.redis_client:
            cache_service.redis_client.ping()
            dependencies["redis"] = "ready"
        else:
            dependencies["redis"] = "degraded_in_memory"
    except Exception as exc:
        dependencies["redis"] = f"degraded: {exc}"
        logger.warning(f"Readiness check warning on redis: {exc}")

    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ok": False, "status": "not_ready", "dependencies": dependencies},
        )

    return {"ok": True, "status": "ready", "dependencies": dependencies}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(links.router)
app.include_router(redirect.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=False)
