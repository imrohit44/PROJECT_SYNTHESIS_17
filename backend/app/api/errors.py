from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette import status

from backend.app.application.auth import AuthenticationError
from backend.app.domain.exceptions import (
    AccountNotActiveError,
    AccountNotFoundError,
    CustomerNotFoundError,
    InsufficientFundsError,
    InvalidAmountError,
    InvalidTransferError,
)


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def domain_handler(
    code: str, status_code: int
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(_: Request, exception: Exception) -> JSONResponse:
        return error_response(code, str(exception), status_code)

    return handler


async def validation_handler(_: Request, exception: Exception) -> JSONResponse:
    details = (
        exception.errors() if isinstance(exception, RequestValidationError) else []
    )
    messages = "; ".join(str(error.get("msg", "Invalid request")) for error in details)
    return error_response("VALIDATION_ERROR", messages, 422)


async def integrity_handler(_: Request, __: Exception) -> JSONResponse:
    return error_response(
        "DATABASE_CONFLICT",
        "The requested operation conflicts with existing data.",
        status.HTTP_409_CONFLICT,
    )


async def authentication_handler(_: Request, __: Exception) -> JSONResponse:
    return error_response("AUTHENTICATION_FAILED", "Invalid email or password", 401)


async def http_exception_handler(_: Request, exception: Exception) -> JSONResponse:
    if not isinstance(exception, HTTPException):
        return error_response("HTTP_ERROR", "Request failed", 500)
    codes = {401: "AUTHENTICATION_REQUIRED", 403: "FORBIDDEN", 429: "RATE_LIMITED"}
    return error_response(
        codes.get(exception.status_code, "HTTP_ERROR"),
        str(exception.detail),
        exception.status_code,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        AccountNotFoundError,
        domain_handler("ACCOUNT_NOT_FOUND", status.HTTP_404_NOT_FOUND),
    )
    app.add_exception_handler(
        CustomerNotFoundError,
        domain_handler("CUSTOMER_NOT_FOUND", status.HTTP_404_NOT_FOUND),
    )
    app.add_exception_handler(
        InvalidAmountError,
        domain_handler("INVALID_AMOUNT", 422),
    )
    app.add_exception_handler(
        InsufficientFundsError,
        domain_handler("INSUFFICIENT_FUNDS", status.HTTP_409_CONFLICT),
    )
    app.add_exception_handler(
        AccountNotActiveError,
        domain_handler("ACCOUNT_NOT_ACTIVE", status.HTTP_409_CONFLICT),
    )
    app.add_exception_handler(
        InvalidTransferError,
        domain_handler("INVALID_TRANSFER", status.HTTP_400_BAD_REQUEST),
    )
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(IntegrityError, integrity_handler)
    app.add_exception_handler(AuthenticationError, authentication_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
