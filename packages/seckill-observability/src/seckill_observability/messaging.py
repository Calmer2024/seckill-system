"""Durable event identity and bounded W3C Kafka propagation; never stores payloads."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
import re
import time
import uuid

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Counter, Histogram

from .context import current_context, log_context

_duplicate = ContextVar("seckill_duplicate", default=False)
_event = ContextVar("seckill_event", default=None)
_propagator = TraceContextTextMapPropagator()
_parent = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
_request = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PUBLISHES = Counter("event_publish_attempts_total", "Kafka send attempts completed", ["outcome"])
PROCESSES = Counter("event_process_total", "Message processing including offset commit", ["role", "outcome"])
COMMIT_FAILURES = Counter("event_offset_commit_failures_total", "Failed Kafka offset commits", ["role"])
PROCESS_DURATION = Histogram("event_process_duration_seconds", "Business handling and Kafka offset commit duration", ["role"], buckets=(.005,.01,.025,.05,.1,.25,.5,1,2.5,5,10,30))
TRANSITIONS = Counter("business_state_transitions_total", "Committed business state changes", ["entity", "to_status"])


def event_id(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def sanitize_metadata(value):
    if isinstance(value, str):
        if len(value) > 2048:
            return {}
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    if not isinstance(value, dict):
        return {}
    result = {"schema_version": 1}
    for key in ("event_id", "causation_id"):
        parsed = event_id(value.get(key))
        if parsed:
            result[key] = parsed
    for key in ("traceparent", "last_publish_traceparent"):
        parent = value.get(key)
        if isinstance(parent, str) and _parent.fullmatch(parent):
            context = _propagator.extract({"traceparent": parent}, context=Context())
            if trace.get_current_span(context).get_span_context().is_valid:
                result[key] = parent
    state = value.get("tracestate")
    # Reject invalid state without asking the propagator to log the raw value.
    if isinstance(state, str) and len(state) <= 512 and all(32 <= ord(c) <= 126 for c in state):
        parts = state.split(",") if state else []
        keys = set()
        if len(parts) <= 32 and all(_valid_state(part.strip(), keys) for part in parts):
            result["tracestate"] = state
    request = value.get("request_id")
    if isinstance(request, str) and _request.fullmatch(request):
        result["request_id"] = request
    created = value.get("created_at_unix")
    if isinstance(created, (int, float)) and not isinstance(created, bool) and 0 < created <= time.time() + 60:
        result["created_at_unix"] = created
    return result


def _valid_state(part, keys):
    if "=" not in part:
        return False
    key, value = part.split("=", 1)
    valid_key = re.fullmatch(r"[a-z][a-z0-9_*/-]{0,255}|[a-z0-9][a-z0-9_*/-]{0,240}@[a-z][a-z0-9_*/-]{0,13}", key)
    if not valid_key or key in keys or not value or len(value) > 256 or any(c in ",=" for c in value) or value.endswith(" "):
        return False
    keys.add(key)
    return True


def carrier():
    result = {}
    _propagator.inject(result)
    return result


def capture_event_metadata():
    context = current_context()
    return sanitize_metadata({"event_id": str(uuid.uuid4()), "causation_id": context.get("event_id"),
                              "request_id": context.get("request_id"), "created_at_unix": time.time(), **carrier()})


def serialize_metadata(metadata=None):
    return json.dumps(sanitize_metadata(metadata if metadata is not None else capture_event_metadata()), separators=(",", ":"))


def current_event_metadata():
    return _event.get()


def retry_metadata():
    return serialize_metadata(_event.get() or {})


def _extract(metadata):
    return _propagator.extract({key: metadata[key] for key in ("traceparent", "tracestate") if key in metadata}, context=Context())


def _links(metadata, delayed=False):
    links = []
    for key, reason in (("traceparent", "delayed"), ("last_publish_traceparent", "retry")):
        if key == "traceparent" and not delayed:
            continue
        context = _extract({"traceparent": metadata.get(key)} if key in metadata else {})
        span_context = trace.get_current_span(context).get_span_context()
        if span_context.is_valid and all(link.context != span_context for link in links):
            links.append(Link(span_context, {"seckill.link.reason": reason}))
    return links


@contextmanager
def publish_attempt(event, namespace):
    metadata = sanitize_metadata(getattr(event, "observability_metadata", None))
    metadata.setdefault("event_id", str(uuid.uuid5(uuid.NAMESPACE_URL,
        f"seckill:{namespace}:{event.aggregate_id}:{getattr(event, 'user_id', '')}:{event.id}:{event.topic}")))
    created = metadata.get("created_at_unix")
    if created is None and isinstance(getattr(event, "created_at", None), datetime):
        created = event.created_at.replace(tzinfo=timezone.utc).timestamp() if event.created_at.tzinfo is None else event.created_at.timestamp()
    delayed = created is not None and time.time() - created > float(os.getenv("SECKILL_TRACE_ASYNC_MAX_AGE_SECONDS", "300"))
    token = _event.set(metadata)
    try:
        with log_context(event_id=metadata["event_id"], causation_id=metadata.get("causation_id"), request_id=metadata.get("request_id")):
            with trace.get_tracer("seckill.messaging").start_as_current_span("outbox.publish",
                    context=Context() if delayed else _extract(metadata), links=_links(metadata, delayed),
                    record_exception=False, set_status_on_exception=False) as span:
                span.set_attribute("messaging.message.id", metadata["event_id"])
                span.set_attribute("messaging.destination.name", event.topic)
                span.set_attribute("seckill.attempt", int(event.retry_count or 0) + 1)
                span.set_attribute("seckill.order_id", str(event.aggregate_id))
                try:
                    yield metadata
                except Exception:
                    span.set_status(Status(StatusCode.ERROR))
                    raise
    finally:
        _event.reset(token)


def send_event(producer, topic, payload):
    metadata = _event.get() or capture_event_metadata()
    order_id = payload.get("order_id")
    with log_context(event_id=metadata["event_id"], causation_id=metadata.get("causation_id"), request_id=metadata.get("request_id")):
        with trace.get_tracer("seckill.messaging").start_as_current_span("kafka.send", kind=SpanKind.PRODUCER,
                record_exception=False, set_status_on_exception=False) as span:
            span.set_attributes({"messaging.system": "kafka", "messaging.destination.name": topic,
                                 "messaging.operation.type": "send", "messaging.message.id": metadata["event_id"]})
            if isinstance(order_id, int) and not isinstance(order_id, bool):
                span.set_attribute("seckill.order_id", str(order_id))
            injected = carrier()
            if "traceparent" in injected:
                metadata["last_publish_traceparent"] = injected["traceparent"]
            headers = {**injected, "x-seckill-schema-version": "1", "x-seckill-event-id": metadata["event_id"]}
            for key, header in (("causation_id", "x-seckill-causation-id"), ("request_id", "x-request-id")):
                if key in metadata:
                    headers[header] = metadata[key]
            try:
                result = producer.send(topic, payload, key=str(order_id).encode("ascii") if isinstance(order_id, int) and not isinstance(order_id, bool) else None,
                                       headers=[(key, value.encode("ascii")) for key, value in headers.items()]).get(timeout=20)
                span.set_attribute("messaging.kafka.partition", result.partition)
                span.add_event('message.acked', {'messaging.kafka.partition': result.partition})
                PUBLISHES.labels("acked").inc()
                logging.getLogger("seckill.messaging").info("event acknowledged", extra={"event": "event.publish_acked", "topic": topic, "partition": result.partition})
                return result
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                PUBLISHES.labels("failed").inc()
                raise


def message_metadata(message):
    headers = getattr(message, "headers", None) or []
    values = {}
    names = {"traceparent": "traceparent", "tracestate": "tracestate", "x-request-id": "request_id",
             "x-seckill-event-id": "event_id", "x-seckill-causation-id": "causation_id"}
    if not isinstance(headers, (list, tuple)) or len(headers) > 128:
        headers = []
    for header in headers:
        if not isinstance(header, (tuple, list)) or len(header) != 2:
            continue
        key, value = header
        if isinstance(key, str) and key in names and isinstance(value, bytes) and len(value) <= 512:
            try:
                decoded = value.decode("ascii")
            except UnicodeDecodeError:
                continue
            if names[key] in values:
                values[names[key]] = None  # Duplicate propagation headers are rejected.
            else:
                values[names[key]] = decoded
    metadata = sanitize_metadata(values)
    metadata.setdefault("event_id", str(uuid.uuid5(uuid.NAMESPACE_URL,
        f"seckill:kafka:{message.topic}:{message.partition}:{message.offset}")))
    return metadata


@contextmanager
def processing_message(message, group, role):
    metadata = message_metadata(message)
    started = time.monotonic()
    token = _duplicate.set(False)
    try:
        with _processing_message(message, group, role, metadata) as span:
            yield span
    finally:
        PROCESS_DURATION.labels(role).observe(time.monotonic() - started)
        _duplicate.reset(token)


@contextmanager
def _processing_message(message, group, role, metadata):
    with log_context(event_id=metadata["event_id"], causation_id=metadata.get("causation_id"), request_id=metadata.get("request_id")):
        with trace.get_tracer("seckill.messaging").start_as_current_span("kafka.process", context=Context() if _message_delayed(message) else _extract(metadata), links=_links(metadata, _message_delayed(message)),
                kind=SpanKind.CONSUMER, record_exception=False, set_status_on_exception=False) as span:
            span.set_attributes({"messaging.system": "kafka", "messaging.destination.name": message.topic,
                                 "messaging.consumer.group.name": group, "messaging.operation.type": "process",
                                 "messaging.message.id": metadata["event_id"], "messaging.kafka.partition": message.partition,
                                 "messaging.kafka.offset": message.offset})
            payload = message.value if isinstance(message.value, dict) else {}
            if isinstance(payload.get("order_id"), int):
                span.set_attribute("seckill.order_id", str(payload["order_id"]))
            from .tracing import business_attributes
            for key in ('product_id', 'quantity'):
                business_attributes(span, payload.get(key), key)
            for key in ('request_id', 'causation_id'):
                if metadata.get(key):
                    span.set_attribute('seckill.' + key, metadata[key])
            timestamp = getattr(message, 'timestamp', None)
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                span.set_attribute('seckill.queue_wait_ms', max(0, time.time() * 1000 - timestamp))
            try:
                yield span
                outcome = "duplicate" if _duplicate.get() else "processed"
                span.set_attribute("seckill.outcome", outcome)
                span.add_event('message.processed', {'seckill.outcome': outcome})
                PROCESSES.labels(role, outcome).inc()
                logging.getLogger("seckill.messaging").info("event processing completed", extra={"event": "event.process_completed", "outcome": outcome})
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("seckill.outcome", "failed")
                PROCESSES.labels(role, "failed").inc()
                raise


def record_transition(entity, status):
    allowed = {"order": {"PENDING_INVENTORY", "CREATED", "FAILED", "PAYING", "PAID"},
               "inventory": {"RESERVED", "CONFIRMED", "CANCELED"}}
    if status not in allowed.get(entity, set()):
        raise ValueError("unknown business state")
    TRANSITIONS.labels(entity, status).inc()
    span = trace.get_current_span()
    span.set_attributes({'seckill.entity': entity, 'seckill.business_state': status})
    span.add_event('business.state_committed', {'seckill.entity': entity, 'seckill.business_state': status})
    logging.getLogger("seckill.messaging").info("business state committed", extra={"event": "business.state_changed", "status": status})


def publish_failed():
    trace.get_current_span().set_status(Status(StatusCode.ERROR))


def _message_delayed(message):
    timestamp = getattr(message, "timestamp", None)
    return isinstance(timestamp, (int, float)) and timestamp > 0 and time.time() - timestamp / 1000 > float(os.getenv("SECKILL_TRACE_ASYNC_MAX_AGE_SECONDS", "300"))


def mark_duplicate():
    _duplicate.set(True)


def commit_offset(consumer, role):
    try:
        consumer.commit()
        trace.get_current_span().add_event('message.offset_committed')
    except Exception:
        COMMIT_FAILURES.labels(role).inc()
        trace.get_current_span().set_attribute("seckill.error_code", "OFFSET_COMMIT_FAILED")
        raise
