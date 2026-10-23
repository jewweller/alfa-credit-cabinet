"""Схемы подписания договора (экран C6). Симуляция ПЭП: код показывается в интерфейсе,
SMS и прочие внешние каналы не используются (план, раздел 11; ограничение кейса)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SIGNING_CODE_PATTERN = r"^\d{6}$"


class SigningCodeResponse(BaseModel):
    """Одноразовый код подписи. На демо показывается на экране в рамке «Симуляция ПЭП»."""

    code: str = Field(pattern=SIGNING_CODE_PATTERN, description="Шесть цифр.", examples=["482915"])
    expires_at: datetime = Field(description="До какого момента код действует.")


class SigningConfirmRequest(BaseModel):
    """Подтверждение подписи введённым кодом."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=SIGNING_CODE_PATTERN, examples=["482915"])
