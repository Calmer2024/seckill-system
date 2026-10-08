from seckill_observability.tracing import configure_tracing
from seckill_observability.http import RequestContextMiddleware

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.api import routes
from app.application.services.order_service import ensure_topics_exist
from app.core.database import order_engine, product_engine
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


app.add_middleware(RequestContextMiddleware, record_http_request=record_http_request, logger=logger)

configure_tracing(app, "order-api", (order_engine, product_engine))
