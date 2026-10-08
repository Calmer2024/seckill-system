from seckill_observability.tracing import configure_tracing
from app.core.database import order_engine, product_engine
from app.application.services.order_service import OrderWorker, ensure_topics_exist
from app.core.config import settings
from app.core.database import OrderSessionLocal
import os

from seckill_observability.logging import configure_logging
from seckill_observability.worker import WorkerMonitor


def main() -> None:
    configure_logging(settings.LOG_LEVEL, "order-worker")
    configure_tracing(None, "order-worker", (order_engine, product_engine,))
    monitor = WorkerMonitor(("order-outbox-publisher", "inventory-result-consumer", "payment-result-consumer"))
    monitor.start_server(int(os.getenv("WORKER_METRICS_PORT", "9106")))
    ensure_topics_exist()
    worker = OrderWorker(order_session_factory=OrderSessionLocal, monitor=monitor)
    worker.run()


if __name__ == "__main__":
    main()
