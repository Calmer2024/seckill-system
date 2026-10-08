from seckill_observability.tracing import configure_tracing
from app.core.database import inventory_engine
from app.core.config import settings
from app.core.database import InventorySessionLocal, redis_client
import os

from seckill_observability.logging import configure_logging
from seckill_observability.worker import WorkerMonitor
from app.services.inventory_service import InventoryWorker, ensure_topics_exist


def main() -> None:
    configure_logging(settings.LOG_LEVEL, "inventory-worker")
    configure_tracing(None, "inventory-worker", (inventory_engine,))
    monitor = WorkerMonitor(("inventory-outbox-publisher", "inventory-order-created-consumer"))
    monitor.start_server(int(os.getenv("WORKER_METRICS_PORT", "9106")))
    ensure_topics_exist()
    worker = InventoryWorker(inventory_session_factory=InventorySessionLocal, redis_client=redis_client, monitor=monitor)
    worker.run()


if __name__ == "__main__":
    main()
