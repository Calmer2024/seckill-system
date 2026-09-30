from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from performance.lib.docker import compose_files, mysql_sql, sql_quote


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed isolated performance users.")
    parser.add_argument("--compose-file", action="append", dest="compose_files")
    parser.add_argument("--user-id-start", type=int, default=9000001)
    parser.add_argument("--user-count", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    files = compose_files(args.compose_files)

    schema_sql = """
USE seckill_db;
CREATE TABLE IF NOT EXISTS performance_test_user (
    user_id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
    mysql_sql(files, schema_sql)

    for batch_start in range(0, args.user_count, args.batch_size):
        batch_end = min(batch_start + args.batch_size, args.user_count)
        values = []
        for offset in range(batch_start, batch_end):
            user_id = args.user_id_start + offset
            username = f"perf_user_{user_id}"
            values.append(
                f"({user_id}, {sql_quote(username)})"
            )
        sql = f"""
USE seckill_db;
INSERT INTO performance_test_user (user_id, username)
VALUES {', '.join(values)}
ON DUPLICATE KEY UPDATE username = VALUES(username);
"""
        mysql_sql(files, sql)

    print(f"Seeded {args.user_count} users starting at {args.user_id_start}.")


if __name__ == "__main__":
    main()
