from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from performance.lib.docker import compose_files, mysql_rows, mysql_sql, redis_command


def build_order_tables_sql(product_id: int, user_id_start: int, user_id_end: int) -> str:
    statements = []
    predicate = (
        f"(o.product_id = {product_id} OR "
        f"(o.user_id BETWEEN {user_id_start} AND {user_id_end}))"
    )
    for database in ("order_db_0", "order_db_1"):
        for shard in (0, 1):
            order_table = f"{database}.t_order_{shard}"
            outbox_table = f"{database}.t_order_outbox_event_{shard}"
            payment_table = f"{database}.t_payment_{shard}"
            statements.append(
                f"DELETE e FROM {outbox_table} e JOIN {order_table} o "
                f"ON o.order_id = e.aggregate_id WHERE {predicate};"
            )
            statements.append(
                f"DELETE p FROM {payment_table} p JOIN {order_table} o "
                f"ON o.order_id = p.order_id WHERE {predicate};"
            )
            statements.append(
                f"DELETE FROM {order_table} WHERE product_id = {product_id} OR "
                f"(user_id BETWEEN {user_id_start} AND {user_id_end});"
            )
        statements.append(
            f"DELETE FROM {database}.t_user_purchase_record "
            f"WHERE product_id = {product_id} OR "
            f"(user_id BETWEEN {user_id_start} AND {user_id_end});"
        )
    return "\n".join(statements)


def redis_keys(files, product_id: int, order_ids: list[str]) -> list[str]:
    patterns = [
        f"seckill:stock:{product_id}",
        f"seckill:user:*:product:{product_id}",
        "product:*",
    ]
    keys: list[str] = []
    for pattern in patterns:
        output = redis_command(files, ["--scan", "--pattern", pattern])
        keys.extend(line.strip() for line in output.splitlines() if line.strip())
    keys.extend(f"seckill:reservation:{order_id}" for order_id in order_ids)
    return sorted(set(keys))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset only the isolated performance data range.")
    parser.add_argument("--compose-file", action="append", dest="compose_files")
    parser.add_argument("--product-id", type=int, default=900001)
    parser.add_argument("--initial-stock", type=int, default=100)
    parser.add_argument("--user-id-start", type=int, default=9000001)
    parser.add_argument("--user-count", type=int, default=10000)
    args = parser.parse_args()
    files = compose_files(args.compose_files)
    user_id_end = args.user_id_start + args.user_count - 1

    order_id_rows = mysql_rows(
        files,
        f"""
SELECT order_id FROM order_db_0.t_order_0
WHERE product_id = {args.product_id} OR (user_id BETWEEN {args.user_id_start} AND {user_id_end})
UNION ALL
SELECT order_id FROM order_db_0.t_order_1
WHERE product_id = {args.product_id} OR (user_id BETWEEN {args.user_id_start} AND {user_id_end})
UNION ALL
SELECT order_id FROM order_db_1.t_order_0
WHERE product_id = {args.product_id} OR (user_id BETWEEN {args.user_id_start} AND {user_id_end})
UNION ALL
SELECT order_id FROM order_db_1.t_order_1
WHERE product_id = {args.product_id} OR (user_id BETWEEN {args.user_id_start} AND {user_id_end});
""",
    )
    order_ids = [row[0] for row in order_id_rows if row]
    keys = redis_keys(files, args.product_id, order_ids)
    for offset in range(0, len(keys), 500):
        batch = keys[offset : offset + 500]
        if batch:
            redis_command(files, ["DEL", *batch])

    sql = f"""
USE inventory_db;
DELETE e FROM inventory_outbox_event e
JOIN inventory_reservation r ON r.order_id = e.aggregate_id
WHERE r.product_id = {args.product_id}
   OR (r.user_id BETWEEN {args.user_id_start} AND {user_id_end});
DELETE FROM inventory_reservation
WHERE product_id = {args.product_id}
   OR (user_id BETWEEN {args.user_id_start} AND {user_id_end});
UPDATE inventory_item
SET available_stock = {args.initial_stock}, reserved_stock = 0, sold_stock = 0, version = version + 1
WHERE product_id = {args.product_id};

{build_order_tables_sql(args.product_id, args.user_id_start, user_id_end)}

USE seckill_db;
CREATE TABLE IF NOT EXISTS performance_test_user (
    user_id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
UPDATE seckill_product SET stock = {args.initial_stock} WHERE id = {args.product_id};
DELETE FROM performance_test_user WHERE user_id BETWEEN {args.user_id_start} AND {user_id_end};
"""
    mysql_sql(files, sql)
    print(
        f"Reset product {args.product_id}, stock {args.initial_stock}, "
        f"and users {args.user_id_start}-{user_id_end}."
    )


if __name__ == "__main__":
    main()
