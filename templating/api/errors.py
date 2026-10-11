import logging
from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)

async def http_error(request: Request, exc: HTTPException):
    return Response(status_code=403 if exc.status_code == 403 else 404, headers=exc.headers)

async def validation_error(request: Request, exc: RequestValidationError):
    return Response(status_code=404)

async def server_error(request: Request, exc: Exception):
    logger.error("Unhandled request error", exc_info=(type(exc), exc, exc.__traceback__))
    return Response(status_code=404)
