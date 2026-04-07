from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions.business_exception import BusinessException
from app.infrastructure.logging.logger import get_logger


logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def handle_business_exception(request: Request, exc: BusinessException):
        request_id = getattr(request.state, "request_id", "")
        logger.info(
            "business exception captured",
            extra={
                "event": "business_exception",
                "request_id": request_id,
                "path": request.url.path,
                "status_code": exc.status_code,
                "error_code": exc.code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "")
        logger.info(
            "request validation failed",
            extra={
                "event": "request_validation_failed",
                "request_id": request_id,
                "path": request.url.path,
                "status_code": 422,
            },
        )
        return JSONResponse(
            status_code=422,
            content={
                "code": "REQUEST_VALIDATION_FAILED",
                "message": "请求参数校验失败",
                "details": exc.errors(),
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "")
        logger.error(
            "unexpected exception captured",
            exc_info=exc,
            extra={
                "event": "unexpected_exception",
                "request_id": request_id,
                "path": request.url.path,
                "status_code": 500,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "系统繁忙，请稍后重试",
                "request_id": request_id,
            },
        )
