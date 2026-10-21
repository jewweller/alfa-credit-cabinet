"""Реализованные эндпоинты `/api/v1`. Сюда переносятся операции из contract.py."""

from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")


@api_v1_router.get("/health", tags=["system"], operation_id="health")
def health() -> dict[str, str]:
    """Живость API (план, раздел 10). Корневой `/health` остаётся для Docker healthcheck."""
    return {"status": "ok"}
