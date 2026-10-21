"""Схема автозаполнения компании по ИНН из ЕГРЮЛ / ЕГРИП (план, разделы 6 и 8)."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import INN_PATTERN


class CompanyKind(StrEnum):
    LLC = "LLC"
    IE = "IE"


class CompanyRegistryStatus(StrEnum):
    """Статус в реестре.

    Значения взяты из контракта ЕГРЮЛ; для ЕГРИП в плане не перечислены (TBD).
    """

    ACTIVE = "ACTIVE"
    LIQUIDATING = "LIQUIDATING"
    LIQUIDATED = "LIQUIDATED"


class CompanyLookupResponse(BaseModel):
    """Данные из реестра в едином виде для ООО (ЕГРЮЛ) и ИП (ЕГРИП). Клиент их не редактирует."""

    inn: str = Field(pattern=INN_PATTERN, examples=["7701000019"])
    kind: CompanyKind = Field(description="LLC — из ЕГРЮЛ, IE — из ЕГРИП.")
    ogrn: str = Field(description="ОГРН для ООО или ОГРНИП для ИП.")
    name: str = Field(description="Наименование ООО или ФИО индивидуального предпринимателя.")
    status: CompanyRegistryStatus
    registered_at: date
    okved_main: str = Field(examples=["10.71"])
    okved_extra: list[str] = Field(default_factory=list, description="Только для ЕГРЮЛ.")
    region: str
    address: str | None = Field(default=None, description="Только для ЕГРЮЛ.")
    director_fio: str | None = Field(default=None, description="Только для ЕГРЮЛ.")
