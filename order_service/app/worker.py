from app.application.services.order_service import OrderWorker, ensure_topics_exist
from app.core.config import settings
from app.core.database import OrderSessionLocal
from app.infrastructure.logging.logger import configure_logging


def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    ensure_topics_exist()
    worker = OrderWorker(order_session_factory=OrderSessionLocal)
    worker.run()


if __name__ == "__main__":
    main()
