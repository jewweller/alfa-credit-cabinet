"""Приведение всех ошибок API к формату `{code, message, field?}` (план, раздел 10)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.state_machine import InvalidTransitionError
from app.schemas.common import ErrorCode, ErrorResponse

_CODE_BY_STATUS: dict[int, ErrorCode] = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.FILE_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
}

# Части пути ошибки валидации, которые говорят «где», а не «какое поле».
_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


def error_response(
    status_code: int, code: ErrorCode, message: str, field: str | None = None
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, field=field)
    return JSONResponse(
        status_code=status_code, content=body.model_dump(mode="json", exclude_none=True)
    )


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    parts = [str(part) for part in first.get("loc", ()) if part not in _LOCATION_PREFIXES]
    return error_response(
        422,
        ErrorCode.VALIDATION_ERROR,
        first.get("msg", "Некорректный запрос"),
        ".".join(parts) or None,
    )


async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _CODE_BY_STATUS.get(exc.status_code, ErrorCode.HTTP_ERROR)
    return error_response(exc.status_code, code, str(exc.detail))


async def _handle_invalid_transition(_: Request, exc: InvalidTransitionError) -> JSONResponse:
    return error_response(409, ErrorCode.INVALID_TRANSITION, str(exc))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(InvalidTransitionError, _handle_invalid_transition)
