from typing import Any, Dict, Optional

STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
}


def get_error_code(status_code: int) -> str:
    return STATUS_TO_CODE.get(status_code, f"HTTP_{status_code}")


def make_error_envelope(
    status_code: int,
    message: str,
    request_id: str,
    code: Optional[str] = None,
    detail: Optional[Any] = None,
) -> Dict[str, Any]:
    resolved_code = code or get_error_code(status_code)
    resolved_detail = detail if detail is not None else message
    return {
        "error": {
            "code": resolved_code,
            "message": message,
            "request_id": request_id,
        },
        "detail": resolved_detail,
    }

