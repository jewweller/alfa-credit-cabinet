"""Запрос документов и файлы клиента (план, разделы 4, 6, 7 и 9)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_MIME_TYPES = ("application/pdf", "image/jpeg", "image/png")


class DocumentKind(StrEnum):
    """Тип документа.

    Набор — решение backend (K4), аналитиком не подтверждён. Правило R4 принимает декларацию
    (`tax_return`) или выписку по счёту (`bank_statement`): любой из двух закрывает пункт запроса.
    """

    TAX_RETURN = "tax_return"
    BANK_STATEMENT = "bank_statement"
    FINANCIAL_STATEMENTS = "financial_statements"
    CONTRACT = "contract"
    OTHER = "other"


class InfoRequestStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"


class InfoRequestItem(BaseModel):
    kind: DocumentKind
    title: str = Field(
        description="Что загрузить, понятными словами.",
        examples=["Налоговая декларация за 2025 год"],
    )
    required: bool = Field(description="Без обязательных пунктов повторная отправка вернёт 422.")


class InfoRequest(BaseModel):
    """Запрос банка на дополнительные документы (исход «запрос информации»)."""

    id: UUID
    status: InfoRequestStatus
    items: list[InfoRequestItem]
    message: str | None = Field(description="Комментарий банка клиенту, если есть.")
    created_at: datetime


class DocumentInfo(BaseModel):
    """Загруженный файл. Скачивание — `GET /api/v1/documents/{id}`."""

    id: UUID
    kind: DocumentKind
    filename: str = Field(description="Имя файла, как его загрузил клиент.")
    mime: str = Field(examples=["application/pdf"])
    size_bytes: int = Field(ge=1, le=MAX_UPLOAD_BYTES)
    info_request_id: UUID | None = Field(description="Ответом на какой запрос загружен файл.")
    uploaded_at: datetime
