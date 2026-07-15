from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from app.config import settings


def get_user_from_request(request: Request) -> str:
    """Use JWT email as rate limit key, fall back to IP."""
    try:
        from jose import jwt
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub", request.client.host)
    except Exception:
        return request.client.host


limiter = Limiter(key_func=get_user_from_request)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. You can generate up to 10 prompts per minute."},
    )