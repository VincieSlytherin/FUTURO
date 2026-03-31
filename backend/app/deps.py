from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.memory.manager import MemoryManager

bearer_scheme = HTTPBearer()


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# Dependency aliases
AuthDep = Annotated[dict, Depends(verify_token)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_memory_manager() -> MemoryManager:
    return MemoryManager(
        memory_dir=settings.memory_dir,
        git_auto_commit=settings.git_auto_commit,
    )


MemoryDep = Annotated[MemoryManager, Depends(get_memory_manager)]
