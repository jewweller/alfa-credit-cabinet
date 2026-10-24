"""Зависимости запросов: сессия БД и текущий пользователь из JWT (план, раздел 9)."""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import BANK_ROLES, UserRole
from app.security import InvalidTokenError, decode_access_token

# Описание совпадает с contract.py: в OpenAPI это одна и та же схема безопасности.
_bearer = HTTPBearer(auto_error=False, description="JWT из `POST /api/v1/auth/login`.")
_CHALLENGE = {"WWW-Authenticate": "Bearer"}

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(401, "Нужно войти в систему", headers=_CHALLENGE)
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(401, str(exc), headers=_CHALLENGE) from exc
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Пользователь не найден", headers=_CHALLENGE)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_client(user: CurrentUser) -> User:
    if user.role != UserRole.CLIENT or user.company_id is None:
        raise HTTPException(403, "Операция доступна только клиенту")
    return user


ClientUser = Annotated[User, Depends(require_client)]


def require_bank_staff(user: CurrentUser) -> User:
    if user.role not in BANK_ROLES:
        raise HTTPException(403, "Операция доступна только сотрудникам банка")
    return user


BankUser = Annotated[User, Depends(require_bank_staff)]
