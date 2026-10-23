"""Смешанный режим фронта пропускает в API ровно реализованные операции контракта."""

import json
from pathlib import Path

from app.main import create_app
from app.openapi import IMPLEMENTED, build_contract_openapi

REAL_OPERATIONS = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "mocks" / "real-operations.json"
)
# Служебные эндпоинты фронт не вызывает.
_NOT_FOR_FRONTEND = {("get", "/health"), ("get", "/api/v1/health")}


def test_frontend_real_operations_match_implemented_contract() -> None:
    spec = build_contract_openapi(create_app())
    implemented = {
        (method, path)
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if operation["x-implementation-status"] == IMPLEMENTED
    } - _NOT_FOR_FRONTEND

    listed = [(method.lower(), path) for method, path in json.loads(REAL_OPERATIONS.read_text())]

    assert len(listed) == len(set(listed)), "в real-operations.json есть повторы"
    assert set(listed) == implemented, (
        "frontend/src/mocks/real-operations.json расходится с реализованными операциями"
    )
