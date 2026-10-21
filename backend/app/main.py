"""Точка входа FastAPI. Swagger и схема — по путям из раздела 10 плана."""

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.openapi import install_openapi


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

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_v1_router)
    install_error_handlers(app)
    install_openapi(app)
    return app


app = create_app()
