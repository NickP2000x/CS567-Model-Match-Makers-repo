import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """A participant-safe failure using the shared contract's error codes."""

    def __init__(self, status: int, code: str, message: str, state: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        # Only set when the server changed state while rejecting (TASK_EXPIRED).
        self.state = state


def error_response(status: int, code: str, message: str, state: dict | None = None) -> JSONResponse:
    content: dict = {"error": {"code": code, "message": message}}
    if state is not None:
        content["state"] = state
    return JSONResponse(status_code=status, content=content)


def install_error_handlers(app: FastAPI) -> None:
    """Return every failure as {"error": {"code", "message"}} without internal details."""

    @app.exception_handler(ApiError)
    async def api_error(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error.status, error.code, error.message, error.state)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
        return error_response(400, "INVALID_REQUEST", "The request body or parameters are invalid.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        if error.status_code == 404:
            return error_response(404, "NOT_FOUND", "Not found.")
        if error.status_code == 405:
            return error_response(405, "INVALID_REQUEST", "Method not allowed.")
        return error_response(error.status_code, "INVALID_REQUEST", "The request could not be processed.")

    @app.exception_handler(Exception)
    async def internal_error(_: Request, error: Exception) -> JSONResponse:
        # Log the type only; messages from providers or settings could contain secrets.
        logger.error("Unhandled server error: %s", type(error).__name__)
        return error_response(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")
