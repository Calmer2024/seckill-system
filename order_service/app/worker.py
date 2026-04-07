from app.application.services.order_service import OrderWorker, ensure_order_topic_exists
from app.core.config import settings
from app.core.database import OrderSessionLocal, ProductSessionLocal, redis_client
from app.infrastructure.logging.logger import configure_logging


def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    ensure_order_topic_exists()
    worker = OrderWorker(
        order_session_factory=OrderSessionLocal,
        product_session_factory=ProductSessionLocal,
        redis_client=redis_client,
    )
    worker.run()


if __name__ == "__main__":
    main()
