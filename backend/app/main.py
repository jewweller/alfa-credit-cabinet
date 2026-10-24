"""Точка входа FastAPI. Swagger и схема — по путям из раздела 10 плана."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.api.errors import install_error_handlers
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.openapi import install_openapi
from app.services.audit import client_ip


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Alfa Credit Cabinet API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    @app.middleware("http")
    async def remember_client_ip(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # IP для журнала действий. За nginx фронта это адрес прокси: X-Forwarded-For не
        # используем, его может подставить кто угодно.
        token = client_ip.set(request.client.host if request.client else None)
        try:
            return await call_next(request)
        finally:
            client_ip.reset(token)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_v1_router)
    install_error_handlers(app)
    install_openapi(app)
    return app


app = create_app()
