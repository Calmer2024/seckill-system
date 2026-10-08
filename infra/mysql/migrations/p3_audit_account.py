"""Provision SELECT-only global audit access; passwords come only from environment."""
import os
import pymysql

TABLES = tuple((f"order_db_{db}", f"t_order{suffix}_{table}") for db in range(2) for table in range(2) for suffix in ("", "_outbox_event")) + (("inventory_db", "inventory_item"), ("inventory_db", "inventory_outbox_event"))


def main():
    password = os.environ["OBSERVABILITY_AUDIT_PASSWORD"]
    if len(password) < 24:
        raise ValueError("audit password must contain at least 24 characters")
    connection = pymysql.connect(host=os.getenv("OBSERVABILITY_ADMIN_HOST", "127.0.0.1"), port=int(os.getenv("OBSERVABILITY_ADMIN_PORT", "3307")),
                                 user=os.getenv("OBSERVABILITY_ADMIN_USER", "root"), password=os.environ["OBSERVABILITY_ADMIN_PASSWORD"], connect_timeout=3, autocommit=True)
    try:
        with connection.cursor() as cursor:
            for schema, table in TABLES:
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name=%s", (schema, table))
                if cursor.fetchone()[0] != 1:
                    raise ValueError("required audit table missing")
            cursor.execute("CREATE USER IF NOT EXISTS 'observability_audit'@'%%' IDENTIFIED BY %s WITH MAX_USER_CONNECTIONS 2", (password,))
            cursor.execute("ALTER USER 'observability_audit'@'%%' IDENTIFIED BY %s WITH MAX_USER_CONNECTIONS 2", (password,))
            cursor.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'observability_audit'@'%'")
            for schema, table in TABLES:
                cursor.execute(f"GRANT SELECT ON `{schema}`.`{table}` TO 'observability_audit'@'%'")
        print("Audit account provisioned: SELECT on 10 fixed physical tables, maximum 2 connections")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
