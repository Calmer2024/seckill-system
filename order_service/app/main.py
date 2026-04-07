import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.application.services.order_service import ensure_order_topic_exists
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.infrastructure.logging.logger import configure_logging, get_logger


configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_order_topic_exists()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="秒杀订单服务",
    lifespan=lifespan,
)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        "request completed",
        extra={
            "event": "http_access",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response
