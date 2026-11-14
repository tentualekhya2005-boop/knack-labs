import time
from collections import defaultdict
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    def __init__(self):
        # key -> list of float timestamps
        self.requests = defaultdict(list)

    def check(self, key: str, max_requests: int, window_seconds: int = 60):
        now = time.time()
        cutoff = now - window_seconds
        valid_requests = [t for t in self.requests[key] if t > cutoff]
        self.requests[key] = valid_requests

        if len(valid_requests) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {max_requests} requests per {window_seconds}s.",
                headers={"Retry-After": str(int(window_seconds))},
            )
        self.requests[key].append(now)

    def reset(self):
        self.requests.clear()


limiter = InMemoryRateLimiter()


def rate_limit_login(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    limiter.check(f"login:{client_ip}", max_requests=10, window_seconds=60)


def rate_limit_create_link(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    limiter.check(f"create_link:{client_ip}", max_requests=30, window_seconds=60)


def rate_limit_redirect(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    limiter.check(f"redirect:{client_ip}", max_requests=120, window_seconds=60)


def rate_limit_analytics(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    limiter.check(f"analytics:{client_ip}", max_requests=60, window_seconds=60)

