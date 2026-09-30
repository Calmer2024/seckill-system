from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from performance.lib.docker import compose_files, mysql_sql, sql_quote


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the isolated performance product.")
    parser.add_argument("--compose-file", action="append", dest="compose_files")
    parser.add_argument("--product-id", type=int, default=900001)
    parser.add_argument("--initial-stock", type=int, default=100)
    args = parser.parse_args()
    files = compose_files(args.compose_files)

    product_name = "Performance Test Product"
    sql = f"""
USE seckill_db;
INSERT INTO seckill_product (
    id, name, price, stock, category, rating, review_count, tags, summary, highlight, visual_icon
) VALUES (
    {args.product_id}, {sql_quote(product_name)}, 1.00, {args.initial_stock},
    'performance', 5.0, 0, '[]', 'Isolated product for authorized performance tests.',
    'performance-test', 'lucide:zap'
)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    price = VALUES(price),
    stock = VALUES(stock),
    category = VALUES(category),
    rating = VALUES(rating),
    review_count = VALUES(review_count),
    tags = VALUES(tags),
    summary = VALUES(summary),
    highlight = VALUES(highlight),
    visual_icon = VALUES(visual_icon);

USE inventory_db;
INSERT INTO inventory_item (
    product_id, product_name, unit_price, available_stock, reserved_stock, sold_stock, version
) VALUES (
    {args.product_id}, {sql_quote(product_name)}, 1.00, {args.initial_stock}, 0, 0, 0
)
ON DUPLICATE KEY UPDATE
    product_name = VALUES(product_name),
    unit_price = VALUES(unit_price),
    available_stock = VALUES(available_stock),
    reserved_stock = VALUES(reserved_stock),
    sold_stock = VALUES(sold_stock),
    version = version + 1;
"""
    mysql_sql(files, sql)
    print(f"Seeded product {args.product_id} with stock {args.initial_stock}.")


if __name__ == "__main__":
    main()
