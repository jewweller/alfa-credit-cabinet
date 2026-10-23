from uuid import uuid4

import pytest
from pydantic import SecretStr

from app import security
from app.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip() -> None:
    password_hash = hash_password("Demo2026!")

    assert password_hash.startswith("$2b$")
    assert verify_password("Demo2026!", password_hash)
    assert not verify_password("demo2026!", password_hash)


@pytest.mark.parametrize("password_hash", [None, "not-a-bcrypt-hash"])
def test_verify_without_valid_hash_is_false(password_hash: str | None) -> None:
    assert not verify_password("Demo2026!", password_hash)


def test_password_longer_than_bcrypt_limit_is_rejected_not_crashing() -> None:
    assert not verify_password("x" * 100, hash_password("Demo2026!"))


def test_token_roundtrip() -> None:
    user_id = uuid4()

    assert decode_access_token(create_access_token(user_id, "client")) == user_id


def test_missing_secret_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = security.get_settings().model_copy(update={"jwt_secret": None})
    monkeypatch.setattr(security, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_access_token(uuid4(), "client")


def test_token_signed_with_other_secret_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    token = create_access_token(uuid4(), "client")
    other = security.get_settings().model_copy(
        update={"jwt_secret": SecretStr("another-secret-key-0123456789abcdef")}
    )
    monkeypatch.setattr(security, "get_settings", lambda: other)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
