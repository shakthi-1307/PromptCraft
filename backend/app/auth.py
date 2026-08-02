from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
bearer      = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(email: str, expires_minutes: int = None) -> str:
    hours   = settings.JWT_EXPIRE_HOURS
    minutes = expires_minutes if expires_minutes else hours * 60
    expire  = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(credentials: HTTPAuthorizationCredentials = Security(bearer)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")