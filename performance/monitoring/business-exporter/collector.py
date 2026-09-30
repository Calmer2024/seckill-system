from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone

import pymysql
import redis
from prometheus_client import Gauge, start_http_server


PRODUCT_ID = int(os.getenv("PERF_PRODUCT_ID", "900001"))
USER_ID_START = int(os.getenv("PERF_USER_ID_START", "9000001"))
USER_COUNT = int(os.getenv("PERF_USER_COUNT", "10000"))
USER_ID_END = USER_ID_START + USER_COUNT - 1
INITIAL_STOCK = int(os.getenv("PERF_INITIAL_STOCK", "100"))
REDIS_RESERVATION_ENABLED = os.getenv("PERF_REDIS_RESERVATION_ENABLED", "true").lower() == "true"
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql-primary")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "418124")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

INVENTORY_STOCK = Gauge(
    "performance_inventory_stock",
    "Inventory state for the configured performance product",
    ["product_id", "state"],
)
ORDER_STATUS_TOTAL = Gauge(
    "performance_order_status_total",
    "Order count by status for the configured performance data range",
    ["status"],
)
OUTBOX_PENDING = Gauge(
    "performance_outbox_pending",
    "Pending NEW or RETRY Outbox events",
    ["service"],
)
OUTBOX_PEAK = Gauge(
    "performance_outbox_pending_peak",
    "Maximum pending Outbox events observed since the collector started",
    ["service"],
)
OUTBOX_MAX_AGE_SECONDS = Gauge(
    "performance_outbox_oldest_age_seconds",
    "Age of the oldest pending Outbox event",
    ["service"],
)
DUPLICATE_ORDER_GROUPS = Gauge(
    "performance_duplicate_order_groups",
    "Active duplicate user and product order groups",
)
VALID_ORDER_TOTAL = Gauge(
    "performance_valid_order_total",
    "Orders in CREATED, PAYING, or PAID state",
)
CONFIRMED_RESERVATION_TOTAL = Gauge(
    "performance_confirmed_reservation_total",
    "Confirmed inventory reservations",
)
STATE_CONVERGED = Gauge(
    "performance_state_converged",
    "Whether the configured performance data has converged",
)
REDIS_STOCK = Gauge(
    "performance_redis_stock",
    "Redis stock value for the configured performance product",
    ["product_id"],
)
COLLECTOR_ERRORS = Gauge(
    "performance_business_collector_errors",
    "Whether the last business metrics collection failed",
)
OUTBOX_PEAK_VALUES = {"order": 0, "inventory": 0}


def connect(database: str | None = None):
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=3,
        read_timeout=3,
        write_timeout=3,
    )


def query_one(database: str, statement: str, params: tuple = ()) -> dict:
    connection = connect(database)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchone() or {}
    finally:
        connection.close()


def query_all(database: str, statement: str, params: tuple = ()) -> list[dict]:
    connection = connect(database)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
            return list(cursor.fetchall())
    finally:
        connection.close()


def set_gauge(gauge: Gauge, value: object, *labels: str) -> None:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    (gauge.labels(*labels) if labels else gauge).set(number)


def order_tables() -> list[tuple[str, str]]:
    return [
        (database, f"t_order_{shard}")
        for database in ("order_db_0", "order_db_1")
        for shard in (0, 1)
    ]


def collect() -> None:
    inventory = query_one(
        "inventory_db",
        """
        SELECT available_stock, reserved_stock, sold_stock
        FROM inventory_item
        WHERE product_id = %s
        """,
        (PRODUCT_ID,),
    )
    product_label = str(PRODUCT_ID)
    for state in ("available", "reserved", "sold"):
        set_gauge(INVENTORY_STOCK, inventory.get(f"{state}_stock", 0), product_label, state)

    reservation_statuses = query_all(
        "inventory_db",
        """
        SELECT status, COUNT(*) AS total
        FROM inventory_reservation
        WHERE product_id = %s
        GROUP BY status
        """,
        (PRODUCT_ID,),
    )
    confirmed_reservations = 0
    reserved_reservations = 0
    for item in reservation_statuses:
        status = str(item["status"])
        total = int(item["total"])
        if status == "CONFIRMED":
            confirmed_reservations = total
        if status == "RESERVED":
            reserved_reservations = total

    order_counts: dict[str, int] = {}
    order_union = []
    for database, table in order_tables():
        order_union.append(
            f"SELECT user_id, product_id, quantity, status FROM {database}.{table}"
        )
        rows = query_all(
            database,
            f"""
            SELECT status, COUNT(*) AS total
            FROM {table}
            WHERE (product_id = %s OR (user_id BETWEEN %s AND %s))
            GROUP BY status
            """,
            (PRODUCT_ID, USER_ID_START, USER_ID_END),
        )
        for item in rows:
            status = str(item["status"])
            order_counts[status] = order_counts.get(status, 0) + int(item["total"])

    for status in ("PENDING_INVENTORY", "CREATED", "PAYING", "PAID", "FAILED"):
        set_gauge(ORDER_STATUS_TOTAL, order_counts.get(status, 0), status)

    valid_orders = sum(order_counts.get(status, 0) for status in ("CREATED", "PAYING", "PAID"))
    set_gauge(VALID_ORDER_TOTAL, valid_orders)
    set_gauge(CONFIRMED_RESERVATION_TOTAL, confirmed_reservations)

    order_outbox_pending = 0
    order_oldest = None
    for database in ("order_db_0", "order_db_1"):
        for shard in (0, 1):
            row = query_one(
                database,
                f"""
                SELECT COUNT(e.id) AS pending, MIN(e.created_at) AS oldest
                FROM t_order_outbox_event_{shard} e
                JOIN t_order_{shard} o ON o.order_id = e.aggregate_id
                WHERE e.status IN ('NEW', 'RETRY')
                  AND (o.product_id = %s OR (o.user_id BETWEEN %s AND %s))
                """,
                (PRODUCT_ID, USER_ID_START, USER_ID_END),
            )
            order_outbox_pending += int(row.get("pending") or 0)
            if row.get("oldest") and (order_oldest is None or row["oldest"] < order_oldest):
                order_oldest = row["oldest"]

    inventory_outbox = query_one(
        "inventory_db",
        """
        SELECT COUNT(e.id) AS pending, MIN(e.created_at) AS oldest
        FROM inventory_outbox_event e
        JOIN inventory_reservation r ON r.order_id = e.aggregate_id
        WHERE e.status IN ('NEW', 'RETRY')
          AND (r.product_id = %s OR (r.user_id BETWEEN %s AND %s))
        """,
        (PRODUCT_ID, USER_ID_START, USER_ID_END),
    )
    inventory_outbox_pending = int(inventory_outbox.get("pending") or 0)
    set_gauge(OUTBOX_PENDING, order_outbox_pending, "order")
    set_gauge(OUTBOX_PENDING, inventory_outbox_pending, "inventory")
    OUTBOX_PEAK_VALUES["order"] = max(OUTBOX_PEAK_VALUES["order"], order_outbox_pending)
    OUTBOX_PEAK_VALUES["inventory"] = max(OUTBOX_PEAK_VALUES["inventory"], inventory_outbox_pending)
    OUTBOX_PEAK.labels("order").set(OUTBOX_PEAK_VALUES["order"])
    OUTBOX_PEAK.labels("inventory").set(OUTBOX_PEAK_VALUES["inventory"])

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for service, oldest in (("order", order_oldest), ("inventory", inventory_outbox.get("oldest"))):
        age = 0
        if oldest:
            age = max(0, int((now - oldest).total_seconds()))
        set_gauge(OUTBOX_MAX_AGE_SECONDS, age, service)

    duplicate_sql = f"""
    SELECT COUNT(*) AS total FROM (
      SELECT user_id, product_id, COUNT(*) AS order_count
      FROM ({' UNION ALL '.join(order_union)}) orders
      WHERE product_id = %s AND status IN ('PENDING_INVENTORY', 'CREATED', 'PAYING', 'PAID')
      GROUP BY user_id, product_id
      HAVING COUNT(*) > 1
    ) duplicates
    """
    duplicate_params = (PRODUCT_ID,)
    duplicate_row = query_one("order_db_0", duplicate_sql, duplicate_params)
    duplicate_groups = int(duplicate_row.get("total") or 0)
    set_gauge(DUPLICATE_ORDER_GROUPS, duplicate_groups)

    available = int(inventory.get("available_stock") or 0)
    reserved = int(inventory.get("reserved_stock") or 0)
    sold = int(inventory.get("sold_stock") or 0)
    converged = (
        reserved == 0
        and reserved_reservations == 0
        and order_outbox_pending == 0
        and inventory_outbox_pending == 0
        and sold == valid_orders
        and available + reserved + sold == INITIAL_STOCK
        and duplicate_groups == 0
    )
    set_gauge(STATE_CONVERGED, int(converged))

    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=3)
    raw_stock = redis_client.get(f"seckill:stock:{PRODUCT_ID}")
    redis_stock = float(raw_stock) if raw_stock is not None else None
    REDIS_STOCK.labels(product_label).set(redis_stock if redis_stock is not None else 0)
    if REDIS_RESERVATION_ENABLED and redis_stock is not None and redis_stock != available:
        set_gauge(STATE_CONVERGED, 0)
    COLLECTOR_ERRORS.set(0)


def main() -> None:
    start_http_server(9105)
    COLLECTOR_ERRORS.set(1)
    for service in ("order", "inventory"):
        OUTBOX_PEAK.labels(service).set(0)
    while True:
        try:
            collect()
        except Exception:
            COLLECTOR_ERRORS.set(1)
            logging.exception("Business metrics collection failed")
        time.sleep(float(os.getenv("PERF_METRICS_INTERVAL_SECONDS", "5")))


if __name__ == "__main__":
    main()
