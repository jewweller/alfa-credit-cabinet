"""Пароли (bcrypt) и токены доступа (JWT HS256) — план, раздел 9."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.config import get_settings

_ALGORITHM = "HS256"
# Хэш для проверки пароля, когда пользователь не найден: время ответа не выдаёт, есть ли email.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode()


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), (password_hash or _DUMMY_HASH).encode())
    except ValueError:  # bcrypt не принимает пароли длиннее 72 байт и битые хэши
        return False


def _secret() -> str:
    secret = get_settings().jwt_secret
    if secret is None:
        raise RuntimeError("JWT_SECRET не задан: выдача и проверка токенов невозможны")
    return secret.get_secret_value()


def create_access_token(user_id: UUID, role: str, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": issued,
        "exp": issued + timedelta(minutes=get_settings().jwt_ttl_minutes),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    """ID пользователя из токена. Роль берётся из БД, а не из токена."""
    try:
        payload = jwt.decode(
            token, _secret(), algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError("Токен недействителен или истёк") from exc
