"""Схемы входа и текущего пользователя (план, разделы 2, 6, 10)."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.companies import CompanyBrief


class UserRole(StrEnum):
    CLIENT = "client"
    UNDERWRITER = "underwriter"
    ADMIN = "admin"


# Сотрудники банка: кабинет банка, история и файлы любых заявок (план, разделы 2 и 9).
BANK_ROLES = frozenset({UserRole.UNDERWRITER, UserRole.ADMIN})


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254, examples=["bakery@demo.local"])
    password: str = Field(min_length=1, examples=["Demo2026!"])


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT для заголовка `Authorization: Bearer <token>`.")
    token_type: Literal["bearer"] = "bearer"


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    company: CompanyBrief | None = Field(
        description="Компания клиента. У сотрудников банка (underwriter, admin) — null."
    )
