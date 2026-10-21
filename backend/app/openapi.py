"""Сборка OpenAPI: рабочая схема приложения и контракт для фронтенда (docs/api/openapi.json).

Файл контракта генерируется из кода, вручную его не правят:
    uv run python -m app.openapi           # записать docs/api/openapi.json
    uv run python -m app.openapi --check   # выйти с кодом 1, если файл устарел
"""

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from app.api.v1.contract import contract_router

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"

IMPLEMENTED = "implemented"
PLANNED = "planned"
_PLANNED_NOTE = "**Только контракт — ещё не реализовано.**"
_ERROR_REF = "#/components/schemas/ErrorResponse"
_FASTAPI_VALIDATION_SCHEMAS = ("HTTPValidationError", "ValidationError")

_CONTRACT_DESCRIPTION = (
    "Контракт API умного кредитного кабинета. Генерируется из кода backend.\n\n"
    "У каждой операции есть `x-implementation-status`: `implemented` — работает в приложении, "
    "`planned` — только контракт. Значения с пометкой TBD требуют согласования."
)


def _replace_validation_refs(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("$ref") in {f"#/components/schemas/{n}" for n in _FASTAPI_VALIDATION_SCHEMAS}:
            node["$ref"] = _ERROR_REF
        for value in node.values():
            _replace_validation_refs(value)
    elif isinstance(node, list):
        for value in node:
            _replace_validation_refs(value)


def build_openapi(app: FastAPI, extra_routes: Iterable[BaseRoute] = ()) -> dict[str, Any]:
    """OpenAPI по маршрутам приложения; стандартная схема 422 заменена на ErrorResponse."""
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=[*app.routes, *extra_routes],
    )
    _replace_validation_refs(spec)
    schemas = spec.get("components", {}).get("schemas", {})
    for name in _FASTAPI_VALIDATION_SCHEMAS:
        schemas.pop(name, None)
    return spec


def build_contract_openapi(app: FastAPI) -> dict[str, Any]:
    """Реализованные операции приложения + запланированные из contract_router."""
    spec = build_openapi(app, contract_router.routes)
    spec["info"]["description"] = _CONTRACT_DESCRIPTION

    for operations in spec["paths"].values():
        for operation in operations.values():
            operation["x-implementation-status"] = IMPLEMENTED

    for route in contract_router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            operation = spec["paths"][route.path][method.lower()]
            operation["x-implementation-status"] = PLANNED
            description = operation.get("description", "")
            operation["description"] = f"{_PLANNED_NOTE}\n\n{description}".strip()
    return spec


def install_openapi(app: FastAPI) -> None:
    """Рабочая схема `/api/openapi.json`: только реализованное, ошибки в формате ErrorResponse."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = build_openapi(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


def render_contract(app: FastAPI) -> str:
    return json.dumps(build_contract_openapi(app), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    from app.main import create_app

    parser = argparse.ArgumentParser(description="Генерация docs/api/openapi.json")
    parser.add_argument("--check", action="store_true", help="только проверить актуальность")
    args = parser.parse_args(argv)

    rendered = render_contract(create_app())
    current = CONTRACT_PATH.read_text(encoding="utf-8") if CONTRACT_PATH.exists() else None

    if args.check:
        if current != rendered:
            print(f"{CONTRACT_PATH} устарел: выполните `uv run python -m app.openapi`")
            return 1
        print(f"{CONTRACT_PATH} актуален")
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered, encoding="utf-8")
    print(f"записан {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
