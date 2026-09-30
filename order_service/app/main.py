import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.api import routes
from app.application.services.order_service import ensure_topics_exist
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.infrastructure.logging.logger import configure_logging, get_logger
from app.observability.metrics import metrics_payload, record_http_request


configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_topics_exist()
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


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=metrics_payload(), media_type=CONTENT_TYPE_LATEST)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        route = request.scope.get("route")
        metric_path = getattr(route, "path", request.url.path)
        if metric_path != "/metrics":
            record_http_request(request.method, metric_path, 500, time.perf_counter() - start_time)
        raise

    route = request.scope.get("route")
    metric_path = getattr(route, "path", request.url.path)
    duration_seconds = time.perf_counter() - start_time
    duration_ms = round(duration_seconds * 1000, 2)
    if metric_path != "/metrics":
        record_http_request(request.method, metric_path, response.status_code, duration_seconds)

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
