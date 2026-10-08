"""Local durable Alertmanager notification sink. Ack only after SQLite commit."""
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlparse
from prometheus_client import CollectorRegistry, Counter, generate_latest, CONTENT_TYPE_LATEST

DB = os.getenv("ALERT_DATABASE", "/data/notifications.sqlite")
LABELS = {"alertname", "severity", "service", "environment", "instance", "job", "role", "topic", "consumergroup", "owner", "notification_owner"}
ANNOTATIONS = {"summary", "description", "runbook_url", "dashboard_url"}
REGISTRY = CollectorRegistry()
DELIVERIES = Counter("observability_alert_webhook_requests_total", "Notification request outcome", ["outcome"], registry=REGISTRY)


@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=3)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, identity TEXT UNIQUE, received REAL, status TEXT, payload TEXT)")
        with db:
            yield db
    finally:
        db.close()


def accept(payload):
    if not isinstance(payload, dict) or payload.get("version") != "4" or not isinstance(payload.get("alerts"), list) or len(payload["alerts"]) > 100:
        raise ValueError("invalid notification")
    rows = []
    for alert in payload["alerts"]:
        if not isinstance(alert, dict) or alert.get("status") not in {"firing", "resolved"}:
            raise ValueError("invalid alert")
        labels = {k: str(v)[:160] for k, v in alert.get("labels", {}).items() if k in LABELS}
        if labels.get("environment") != "local" or not labels.get("alertname"):
            raise ValueError("invalid scope")
        item = {"labels": labels, "annotations": {k: str(v)[:1000] for k, v in alert.get("annotations", {}).items() if k in ANNOTATIONS},
                "status": alert["status"], "starts_at": str(alert.get("startsAt", ""))[:64], "ends_at": str(alert.get("endsAt", ""))[:64],
                "fingerprint": str(alert.get("fingerprint", ""))[:64]}
        # Firing endsAt moves on every refresh, so it must not break deduplication.
        identity = json.dumps([item["fingerprint"], labels, item["status"], item["starts_at"], item["ends_at"] if item["status"] == "resolved" else ""], sort_keys=True)
        rows.append((identity, time.time(), item["status"], json.dumps(item, ensure_ascii=False)))
    with connection() as db:
        db.executemany("INSERT OR IGNORE INTO notifications(identity, received, status, payload) VALUES(?,?,?,?)", rows)
        db.execute("DELETE FROM notifications WHERE received < ?", (time.time() - 7 * 86400,))
        db.execute("DELETE FROM notifications WHERE id NOT IN (SELECT id FROM notifications ORDER BY id DESC LIMIT 10000)")


def events():
    with connection() as db:
        rows = db.execute("SELECT received,payload FROM notifications ORDER BY id DESC LIMIT 100").fetchall()
    return [{"received_at": received, **json.loads(payload)} for received, payload in rows]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/metrics":
            body = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif route == "/health":
            try:
                with connection() as db:
                    db.execute("SELECT 1")
                self.send(200, {"status": "ok"})
            except sqlite3.Error:
                self.send(503, {"error": "storage_unavailable"})
        elif route == "/events":
            try:
                self.send(200, {"events": events()})
            except sqlite3.Error:
                self.send(503, {"error": "storage_unavailable"})
        else:
            self.send(404, {"error": "not_found"})

    def do_POST(self):
        self.connection.settimeout(5)
        if self.path != "/webhook":
            self.send(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 524288:
                raise ValueError()
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError()
            accept(json.loads(body))
        except (ValueError, TypeError, AttributeError):
            DELIVERIES.labels("rejected").inc()
            self.send(400, {"error": "invalid_notification"})
        except (sqlite3.Error, OSError):
            DELIVERIES.labels("storage_failure").inc()
            self.send(503, {"error": "storage_unavailable"})
        else:
            DELIVERIES.labels("persisted").inc()
            self.send(200, {"status": "persisted"})


if __name__ == "__main__":
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connection():
        pass
    ThreadingHTTPServer(("0.0.0.0", 9122), Handler).serve_forever()
