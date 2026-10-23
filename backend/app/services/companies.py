"""Автозаполнение компании по ИНН из ЕГРЮЛ (10 цифр) или ЕГРИП (12 цифр), план, раздел 4, этап 1.

Ответы реестров приводятся к одной схеме CompanyLookupResponse; данные берутся через тот же
SourceClient, что и в конвейере заявки.
"""

from typing import Any

from app.api.errors import ApiError
from app.integrations.base import SourceClient
from app.schemas.common import ErrorCode
from app.schemas.companies import CompanyKind, CompanyLookupResponse
from app.scoring.inputs import SourceState


def _from_egrul(payload: dict[str, Any]) -> CompanyLookupResponse:
    director = payload.get("director") or {}
    return CompanyLookupResponse(
        inn=payload["inn"],
        kind=CompanyKind.LLC,
        ogrn=payload["ogrn"],
        name=payload["name"],
        status=payload["status"],
        registered_at=payload["registered_at"],
        okved_main=payload["okved_main"],
        okved_extra=payload.get("okved_extra") or [],
        region=payload["region"],
        address=payload.get("address"),
        director_fio=director.get("fio"),
    )


def _from_egrip(payload: dict[str, Any]) -> CompanyLookupResponse:
    return CompanyLookupResponse(
        inn=payload["inn"],
        kind=CompanyKind.IE,
        ogrn=payload["ogrnip"],
        name=payload["fio"],
        status=payload["status"],
        registered_at=payload["registered_at"],
        okved_main=payload["okved_main"],
        region=payload["region"],
    )


def lookup(sources: SourceClient, inn: str) -> CompanyLookupResponse:
    source, parse, label = (
        ("egrul", _from_egrul, "ЕГРЮЛ") if len(inn) == 10 else ("egrip", _from_egrip, "ЕГРИП")
    )
    result = sources.fetch(source, inn)
    if result.state == SourceState.NOT_FOUND:
        raise ApiError(
            404, ErrorCode.COMPANY_NOT_FOUND, f"Компания с таким ИНН не найдена в {label}"
        )
    if result.state != SourceState.OK or result.payload is None:
        raise ApiError(
            503, ErrorCode.UPSTREAM_UNAVAILABLE, f"{label} сейчас не отвечает, попробуйте позже"
        )
    return parse(result.payload)
