"""Explicit additive migration. Set OBSERVABILITY_MIGRATION_DATABASE_URL to primary MySQL.

Run once before deploying P2 applications; reruns verify all five physical tables.
MySQL DDL is not transactional. A partial application is safe to resume.
"""
import os
from sqlalchemy import create_engine, text

TABLES = tuple((f"order_db_{db}", f"t_order_outbox_event_{table}") for db in range(2) for table in range(2)) + (
    ("inventory_db", "inventory_outbox_event"),)
COLUMN = "observability_metadata"


def migrate(engine):
    changes = []
    with engine.connect() as connection:
        if connection.execute(text("SELECT GET_LOCK('seckill_observability_p2', 10)")).scalar() != 1:
            raise RuntimeError("migration lock unavailable")
        try:
            pending = []
            for schema, table in TABLES:
                exists = connection.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=:s AND table_name=:t"), {"s": schema, "t": table}).scalar()
                if exists != 1:
                    raise RuntimeError(f"required physical table missing: {schema}.{table}")
                column = connection.execute(text("SELECT DATA_TYPE, IS_NULLABLE FROM information_schema.columns WHERE table_schema=:s AND table_name=:t AND column_name=:c"), {"s": schema, "t": table, "c": COLUMN}).first()
                if column and tuple(column) != ("text", "YES"):
                    raise RuntimeError(f"incompatible metadata column: {schema}.{table}")
                if not column:
                    pending.append((schema, table))
            # Identifiers come only from the constant whitelist; INSTANT avoids a table copy.
            for schema, table in pending:
                connection.execute(text(f"ALTER TABLE `{schema}`.`{table}` ADD COLUMN `{COLUMN}` TEXT NULL, ALGORITHM=INSTANT"))
                changes.append(f"{schema}.{table}")
            connection.commit()
        finally:
            connection.execute(text("SELECT RELEASE_LOCK('seckill_observability_p2')"))
    return changes


if __name__ == "__main__":
    engine = create_engine(os.environ["OBSERVABILITY_MIGRATION_DATABASE_URL"])
    try:
        print({"changed": migrate(engine), "verified_tables": len(TABLES)})
    finally:
        engine.dispose()
