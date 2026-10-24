"""Общие типы контракта API: деньги, ставки, ИНН и единый формат ошибок (план, раздел 10)."""

import re
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, WithJsonSchema
from pydantic.json_schema import GetJsonSchemaHandler, JsonSchemaValue
from pydantic_core import CoreSchema

DECIMAL_2_PATTERN = r"^\d+\.\d{2}$"
INN_PATTERN = r"^(\d{10}|\d{12})$"

_DECIMAL_2_RE = re.compile(DECIMAL_2_PATTERN)
_CENT = Decimal("0.01")


def _parse_decimal_2(value: Any) -> Any:
    # Из JSON принимаем только строку: число в JSON — это float, он теряет копейки.
    if isinstance(value, str) and _DECIMAL_2_RE.fullmatch(value):
        return value
    if isinstance(value, Decimal) and value == value.quantize(_CENT):
        return value
    raise ValueError('ожидается строка с двумя знаками после точки, например "3000000.00"')


def _format_decimal_2(value: Decimal) -> str:
    # Правило округления в плане не задано, поэтому молча не округляем.
    if value != value.quantize(_CENT):
        raise ValueError(f"значение {value} содержит больше двух знаков после точки")
    return f"{value:.2f}"


Money = Annotated[
    Decimal,
    BeforeValidator(_parse_decimal_2),
    PlainSerializer(_format_decimal_2, return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": DECIMAL_2_PATTERN,
            "description": "Сумма в рублях строкой с двумя знаками после точки.",
            "examples": ["3000000.00"],
        }
    ),
]

Rate = Annotated[
    Decimal,
    BeforeValidator(_parse_decimal_2),
    PlainSerializer(_format_decimal_2, return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": DECIMAL_2_PATTERN,
            "description": (
                "Годовая процентная ставка в процентах строкой с двумя знаками "
                'после точки: "18.00" означает 18% годовых.'
            ),
            "examples": ["18.00"],
        }
    ),
]


class DescribedStrEnum(StrEnum):
    """StrEnum с пояснением к каждому значению.

    Пояснения попадают в OpenAPI дважды: списком в `description` (видно в Swagger)
    и массивом `x-enum-descriptions` (из него openapi-typescript делает комментарии к типам).
    """

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        raise NotImplementedError

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler.resolve_ref_schema(handler(core_schema))
        descriptions = cls.value_descriptions()
        intro = (cls.__doc__ or "").strip()
        items = "\n".join(f"- `{member.value}` — {descriptions[member]}" for member in cls)
        schema["description"] = f"{intro}\n\n{items}" if intro else items
        schema["x-enum-descriptions"] = [descriptions[member] for member in cls]
        return schema


class ErrorCode(StrEnum):
    """Технические коды ошибок. Предварительный контракт: в плане не закреплены, TBD."""

    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    INVALID_TRANSITION = "invalid_transition"
    VERSION_CONFLICT = "version_conflict"
    COMPANY_NOT_FOUND = "company_not_found"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    OFFER_NOT_ACTIVE = "offer_not_active"
    DOCUMENTS_REQUIRED = "documents_required"
    FILE_TOO_LARGE = "file_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    INVALID_CODE = "invalid_code"
    ASSIGNED_TO_OTHER = "assigned_to_other"
    DEMO_MODE_DISABLED = "demo_mode_disabled"
    HTTP_ERROR = "http_error"


class ErrorResponse(BaseModel):
    """Единый формат ошибки `{code, message, field?}` (план, раздел 10)."""

    code: ErrorCode = Field(description="Машинный код ошибки (список предварительный, TBD).")
    message: str = Field(description="Понятный текст ошибки.")
    field: str | None = Field(
        default=None,
        description="Поле запроса, к которому относится ошибка. Нет, если ошибка не про поле.",
    )
