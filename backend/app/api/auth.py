from datetime import datetime, timedelta
import bcrypt
from fastapi import APIRouter, HTTPException, status
from jose import jwt

from app.config import settings
from app.models.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    try:
        valid = bcrypt.checkpw(
            body.password.encode("utf-8"),
            settings.user_password_hash.encode("utf-8"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid USER_PASSWORD_HASH configuration",
        ) from exc

    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    expire = datetime.utcnow() + timedelta(days=settings.jwt_expire_days)
    token = jwt.encode(
        {"sub": "futuro-user", "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(access_token=token)
