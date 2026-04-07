from app.core.config import settings
from app.core.database import InventorySessionLocal, redis_client
from app.infrastructure.logging.logger import configure_logging
from app.services.inventory_service import InventoryWorker, ensure_topics_exist


def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    ensure_topics_exist()
    worker = InventoryWorker(inventory_session_factory=InventorySessionLocal, redis_client=redis_client)
    worker.run()


if __name__ == "__main__":
    main()
