import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap.catalog_bootstrap import clear_product_cache, ensure_product_schema_and_seed
from app.core.config import settings
from app.core.database import Base, redis_client, write_engine
from app.core.exceptions.handlers import register_exception_handlers
from app.infrastructure.logging.logger import configure_logging, get_logger
from app.api import routes

# 初始化表结构 (生产环境中通常使用 Alembic 做数据迁移，不推荐直接 create_all)
Base.metadata.create_all(bind=write_engine)
ensure_product_schema_and_seed(write_engine)
clear_product_cache(redis_client)

configure_logging(settings.LOG_LEVEL)
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
