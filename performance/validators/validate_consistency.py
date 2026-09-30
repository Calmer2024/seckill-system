from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from performance.lib.docker import compose_files, mysql_rows, redis_command


def first_row(files, sql: str) -> list[str]:
    rows = mysql_rows(files, sql)
    return rows[0] if rows else []


def int_value(row: list[str], index: int, default: int = 0) -> int:
    try:
        return int(row[index])
    except (IndexError, TypeError, ValueError):
        return default


def check(name: str, passed: bool, actual: object, expected: object, details: str = "") -> dict:
    return {
        "name": name,
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate business invariants after a performance run.")
    parser.add_argument("--compose-file", action="append", dest="compose_files")
    parser.add_argument("--product-id", type=int, default=900001)
    parser.add_argument("--initial-stock", type=int, default=100)
    parser.add_argument("--user-id-start", type=int, default=9000001)
    parser.add_argument("--user-count", type=int, default=10000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    files = compose_files(args.compose_files)
    user_id_end = args.user_id_start + args.user_count - 1

    inventory_row = first_row(
        files,
        f"""
SELECT available_stock, reserved_stock, sold_stock
FROM inventory_db.inventory_item
WHERE product_id = {args.product_id};
""",
    )
    available_stock = int_value(inventory_row, 0)
    reserved_stock = int_value(inventory_row, 1)
    sold_stock = int_value(inventory_row, 2)

    reservation_row = first_row(
        files,
        f"""
SELECT
  COUNT(*),
  COALESCE(SUM(status = 'CONFIRMED'), 0),
  COALESCE(SUM(status = 'RESERVED'), 0),
  COALESCE(SUM(status = 'CANCELED'), 0),
  COALESCE(SUM(quantity), 0)
FROM inventory_db.inventory_reservation
WHERE product_id = {args.product_id};
""",
    )
    reservation_total = int_value(reservation_row, 0)
    confirmed_reservations = int_value(reservation_row, 1)
    reserved_reservations = int_value(reservation_row, 2)
    canceled_reservations = int_value(reservation_row, 3)
    reserved_quantity = int_value(reservation_row, 4)

    order_union = " UNION ALL ".join(
        f"SELECT order_id, user_id, product_id, quantity, status FROM {database}.t_order_{shard}"
        for database in ("order_db_0", "order_db_1")
        for shard in (0, 1)
    )
    order_row = first_row(
        files,
        f"""
SELECT
  COUNT(*),
  COALESCE(SUM(status IN ('CREATED', 'PAYING', 'PAID')), 0),
  COALESCE(SUM(status = 'FAILED'), 0),
  COALESCE(SUM(quantity), 0)
FROM ({order_union}) orders
WHERE product_id = {args.product_id}
   OR (user_id BETWEEN {args.user_id_start} AND {user_id_end});
""",
    )
    order_total = int_value(order_row, 0)
    valid_orders = int_value(order_row, 1)
    failed_orders = int_value(order_row, 2)
    order_quantity = int_value(order_row, 3)

    duplicate_row = first_row(
        files,
        f"""
SELECT COUNT(*) FROM (
  SELECT user_id, product_id, COUNT(*) AS order_count
  FROM ({order_union}) orders
  WHERE product_id = {args.product_id}
    AND status IN ('PENDING_INVENTORY', 'CREATED', 'PAYING', 'PAID')
  GROUP BY user_id, product_id
  HAVING COUNT(*) > 1
) duplicates;
""",
    )
    duplicate_groups = int_value(duplicate_row, 0)

    outbox_union = " UNION ALL ".join(
        f"SELECT e.status FROM {database}.t_order_outbox_event_{shard} e "
        f"JOIN {database}.t_order_{shard} o ON o.order_id = e.aggregate_id "
        f"WHERE o.product_id = {args.product_id} OR "
        f"(o.user_id BETWEEN {args.user_id_start} AND {user_id_end})"
        for database in ("order_db_0", "order_db_1")
        for shard in (0, 1)
    )
    order_outbox_row = first_row(
        files,
        f"""
SELECT
  COALESCE(SUM(status IN ('NEW', 'RETRY')), 0),
  COUNT(*)
FROM ({outbox_union}) events;
""",
    )
    order_outbox_pending = int_value(order_outbox_row, 0)
    order_outbox_total = int_value(order_outbox_row, 1)

    inventory_outbox_row = first_row(
        files,
        f"""
SELECT COALESCE(SUM(e.status IN ('NEW', 'RETRY')), 0), COUNT(*)
FROM inventory_db.inventory_outbox_event e
JOIN inventory_db.inventory_reservation r ON r.order_id = e.aggregate_id
WHERE (r.product_id = {args.product_id} OR (r.user_id BETWEEN {args.user_id_start} AND {user_id_end}));
""",
    )
    inventory_outbox_pending = int_value(inventory_outbox_row, 0)
    inventory_outbox_total = int_value(inventory_outbox_row, 1)

    purchase_row = first_row(
        files,
        f"""
SELECT COUNT(*)
FROM (
  SELECT user_id, product_id FROM order_db_0.t_user_purchase_record
  UNION ALL
  SELECT user_id, product_id FROM order_db_1.t_user_purchase_record
) purchases
WHERE product_id = {args.product_id}
  AND user_id BETWEEN {args.user_id_start} AND {user_id_end};
""",
    )
    purchase_records = int_value(purchase_row, 0)

    redis_stock_raw = redis_command(
        files,
        ["GET", f"seckill:stock:{args.product_id}"],
        check=False,
    ).strip()
    redis_stock = None
    if redis_stock_raw:
        try:
            redis_stock = int(redis_stock_raw)
        except ValueError:
            redis_stock = None

    checks = [
        check(
            "stock_non_negative",
            available_stock >= 0 and reserved_stock >= 0 and sold_stock >= 0,
            {"available": available_stock, "reserved": reserved_stock, "sold": sold_stock},
            "all values >= 0",
        ),
        check(
            "stock_conservation",
            available_stock + reserved_stock + sold_stock == args.initial_stock,
            available_stock + reserved_stock + sold_stock,
            args.initial_stock,
            "initial stock = available + reserved + sold",
        ),
        check(
            "successful_order_matches_sold_stock",
            valid_orders == sold_stock,
            valid_orders,
            sold_stock,
            "valid orders must match confirmed sold quantity",
        ),
        check(
            "confirmed_reservation_matches_successful_order",
            confirmed_reservations == valid_orders,
            confirmed_reservations,
            valid_orders,
            "confirmed reservations must match valid orders",
        ),
        check(
            "no_duplicate_active_orders",
            duplicate_groups == 0,
            duplicate_groups,
            0,
            "one active order per user and product",
        ),
        check(
            "purchase_record_matches_successful_order",
            purchase_records == valid_orders,
            purchase_records,
            valid_orders,
            "purchase idempotency records must match valid orders",
        ),
        check(
            "no_unconfirmed_reservations",
            reserved_reservations == 0 and reserved_stock == 0,
            {"reserved_reservations": reserved_reservations, "reserved_stock": reserved_stock},
            {"reserved_reservations": 0, "reserved_stock": 0},
            "final state should converge after workers recover",
        ),
        check(
            "order_outbox_drained",
            order_outbox_pending == 0,
            order_outbox_pending,
            0,
            "NEW and RETRY order outbox events",
        ),
        check(
            "inventory_outbox_drained",
            inventory_outbox_pending == 0,
            inventory_outbox_pending,
            0,
            "NEW and RETRY inventory outbox events",
        ),
        check(
            "redis_stock_non_negative",
            redis_stock is None or redis_stock >= 0,
            redis_stock,
            "null or >= 0",
            "null is expected when Redis stock reservation is disabled",
        ),
    ]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_id": args.product_id,
        "initial_stock": args.initial_stock,
        "user_id_range": {"start": args.user_id_start, "end": user_id_end},
        "inventory": {
            "available_stock": available_stock,
            "reserved_stock": reserved_stock,
            "sold_stock": sold_stock,
            "reservation_total": reservation_total,
            "confirmed_reservations": confirmed_reservations,
            "reserved_reservations": reserved_reservations,
            "canceled_reservations": canceled_reservations,
            "reserved_quantity": reserved_quantity,
        },
        "orders": {
            "total_orders": order_total,
            "valid_orders": valid_orders,
            "failed_orders": failed_orders,
            "order_quantity": order_quantity,
            "duplicate_groups": duplicate_groups,
            "purchase_records": purchase_records,
        },
        "outbox": {
            "order_pending": order_outbox_pending,
            "order_total": order_outbox_total,
            "inventory_pending": inventory_outbox_pending,
            "inventory_total": inventory_outbox_total,
        },
        "redis": {"stock": redis_stock},
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "output": str(output)}, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
