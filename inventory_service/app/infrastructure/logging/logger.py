"""Compatibility exports for the shared logging schema."""
from seckill_observability.logging import JsonFormatter, get_logger
from seckill_observability.logging import configure_logging as _configure_logging


def configure_logging(level: str = "INFO") -> None:
    _configure_logging(level, "inventory-api")
