"""Whole-environment, read-only physical-shard audit; never uses pressure-run IDs."""
import os
import threading
import time
import json
import re
from order_snapshot import read_order, recent_orders
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pymysql
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily

LOCK = threading.Lock()
ORDER_QUERY_LOCK = threading.Semaphore(1)  # One UI connection plus the background audit; account limit is two.
STATE = {"snapshot": None, "last_success": 0, "success": 0, "errors": 0}
ORDER_TABLES = tuple(f"order_db_{db}.t_order_{table}" for db in range(2) for table in range(2))
OUTBOX_TABLES = tuple(("order", f"order_db_{db}.t_order_outbox_event_{table}") for db in range(2) for table in range(2)) + (("inventory", "inventory_db.inventory_outbox_event"),)


def sample(connection):
    result = {"outbox": {"order": [0, 0], "inventory": [0, 0]}, "negative_items": 0, "pending_orders": 0, "pending_age": 0}
    # One InnoDB read view across all physical shards; no write, migration or payload read.
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION MAX_EXECUTION_TIME=2000")
        cursor.execute("SET SESSION time_zone='+00:00'")
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        for owner, table in OUTBOX_TABLES:
            cursor.execute(f"SELECT COUNT(*), COALESCE(MAX(TIMESTAMPDIFF(SECOND,created_at,UTC_TIMESTAMP())),0) FROM {table} WHERE status IN ('NEW','RETRY')")
            count, age = cursor.fetchone()
            result["outbox"][owner][0] += int(count)
            result["outbox"][owner][1] = max(result["outbox"][owner][1], max(0, int(age)))
        for table in ORDER_TABLES:
            cursor.execute(f"SELECT COUNT(*), COALESCE(MAX(TIMESTAMPDIFF(SECOND,created_at,UTC_TIMESTAMP())),0) FROM {table} WHERE status='PENDING_INVENTORY'")
            count, age = cursor.fetchone()
            result["pending_orders"] += int(count)
            result["pending_age"] = max(result["pending_age"], max(0, int(age)))
        cursor.execute("SELECT COUNT(*) FROM inventory_db.inventory_item WHERE available_stock<0 OR reserved_stock<0 OR sold_stock<0")
        result["negative_items"] = int(cursor.fetchone()[0])
    connection.rollback()
    return result


def poll():
    while True:
        connection = None
        try:
            connection = pymysql.connect(host=os.getenv("AUDIT_MYSQL_HOST", "mysql-primary"), user=os.getenv("AUDIT_MYSQL_USER", "observability_audit"),
                                         password=os.environ["AUDIT_MYSQL_PASSWORD"], connect_timeout=2, read_timeout=3, write_timeout=3, autocommit=False)
            snapshot = sample(connection)
            with LOCK:
                STATE.update(snapshot=snapshot, last_success=time.time(), success=1)
        except Exception:
            # Never expose SQL/DSN/secrets, never replace last known evidence with zero.
            with LOCK:
                STATE["success"] = 0
                STATE["errors"] += 1
        finally:
            if connection is not None:
                connection.close()
        time.sleep(30)


class Collector:
    def collect(self):
        with LOCK:
            state = dict(STATE)
        for suffix, key in (("collection_success", "success"), ("last_success_timestamp_seconds", "last_success")):
            metric = GaugeMetricFamily("observability_business_" + suffix, "Global audit freshness; check before using evidence")
            metric.add_metric([], state[key])
            yield metric
        errors = CounterMetricFamily("observability_business_collection_errors", "Global audit collection failures")
        errors.add_metric([], state["errors"])
        yield errors
        snapshot = state["snapshot"]
        if snapshot is None:
            return
        for name, key in (("inventory_negative_items", "negative_items"), ("pending_orders", "pending_orders"), ("pending_order_oldest_age_seconds", "pending_age")):
            metric = GaugeMetricFamily("observability_business_" + name, "Read-only consistent snapshot; requires fresh successful collection")
            metric.add_metric([], snapshot[key])
            yield metric
        for name, position in (("outbox_pending_events", 0), ("outbox_oldest_age_seconds", 1)):
            metric = GaugeMetricFamily("observability_business_" + name, "All physical shards; no product/user filters", labels=["owner"])
            for owner, values in snapshot["outbox"].items():
                metric.add_metric([owner], values[position])
            yield metric


REGISTRY = CollectorRegistry()
REGISTRY.register(Collector())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        match = re.fullmatch(r'/orders/([1-9][0-9]{0,18})', self.path)
        list_orders = urlparse(self.path).path == '/orders'
        if match or list_orders:
            connection = None
            acquired = False
            try:
                acquired = ORDER_QUERY_LOCK.acquire(timeout=2)
                if not acquired:
                    raise RuntimeError('order reader busy')
                connection = pymysql.connect(host=os.getenv('AUDIT_MYSQL_HOST', 'mysql-primary'), user=os.getenv('AUDIT_MYSQL_USER', 'observability_audit'),
                    password=os.environ['AUDIT_MYSQL_PASSWORD'], connect_timeout=2, read_timeout=2, write_timeout=2, autocommit=False)
                if list_orders:
                    params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                    if not {'start','end'} <= set(params) or set(params) - {'start', 'end', 'status', 'order_id', 'product_id', 'before'} or any(len(v)!=1 for v in params.values()):
                        raise ValueError('invalid filters')
                    payload = recent_orders(connection, **{k:v[0] for k,v in params.items()})
                else:
                    payload = read_order(connection, match[1])
                code = 200
            except ValueError:
                payload, code = {'error': 'invalid_order_id'}, 400
            except Exception:
                payload, code = {'error': 'order_evidence_unavailable'}, 503
            finally:
                if connection is not None:
                    connection.close()
                if acquired:
                    ORDER_QUERY_LOCK.release()
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/metrics":
            self.send_error(404)
            return
        body = generate_latest(REGISTRY)
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 9124), Handler).serve_forever()
