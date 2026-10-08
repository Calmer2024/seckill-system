from seckill_observability.tracing import configure_tracing
from seckill_observability.http import RequestContextMiddleware


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.bootstrap.catalog_bootstrap import clear_product_cache, ensure_product_schema_and_seed
from app.core.config import settings
from app.core.database import Base, read_engine, redis_client, write_engine
from app.core.exceptions.handlers import register_exception_handlers
from app.infrastructure.logging.logger import configure_logging, get_logger
from app.observability.metrics import metrics_payload, record_http_request
from app.api import routes

configure_logging(settings.LOG_LEVEL)

# 初始化表结构 (生产环境中通常使用 Alembic 做数据迁移，不推荐直接 create_all)
Base.metadata.create_all(bind=write_engine)
ensure_product_schema_and_seed(write_engine)
clear_product_cache(redis_client)

logger = get_logger(__name__)

app = FastAPI(title=settings.PROJECT_NAME, description="重构后的商品微服务")
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(routes.router)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=metrics_payload(), media_type=CONTENT_TYPE_LATEST)


app.add_middleware(RequestContextMiddleware, record_http_request=record_http_request, logger=logger)

configure_tracing(app, "product", (read_engine, write_engine))
