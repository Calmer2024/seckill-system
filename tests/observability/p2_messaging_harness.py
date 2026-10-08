"""Exercise sampled async span semantics in a separate tracing process."""
import time
from types import SimpleNamespace
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from seckill_observability.context import current_context, log_context
from seckill_observability.messaging import capture_event_metadata, serialize_metadata, publish_attempt, processing_message, mark_duplicate
from seckill_observability.tracing import SafeExporter

provider = TracerProvider()
exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(SafeExporter(exporter)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("p2-test")
with tracer.start_as_current_span("origin") as origin, log_context(request_id="origin-request"):
    metadata = capture_event_metadata()
metadata["created_at_unix"] = time.time() - 301
event = SimpleNamespace(id=1, aggregate_id=123, user_id=4, topic="orders", retry_count=0,
                        observability_metadata=serialize_metadata(metadata))
with tracer.start_as_current_span("unrelated") as unrelated:
    with publish_attempt(event, "order"):
        span = trace.get_current_span()
        assert span.get_span_context().trace_id != origin.get_span_context().trace_id
        assert span.get_span_context().trace_id != unrelated.get_span_context().trace_id
        assert current_context()["event_id"] == metadata["event_id"]
    assert current_context() == {}

message = SimpleNamespace(topic="orders", partition=0, offset=1, timestamp=int((time.time()-301)*1000),
                          value={"order_id":123}, headers=[("traceparent", metadata["traceparent"].encode()),
                          ("x-seckill-event-id",metadata["event_id"].encode())])
with processing_message(message, "inventory-group", "inventory-order-created-consumer"):
    mark_duplicate()
with processing_message(SimpleNamespace(topic="legacy", partition=0, offset=2, value={}, headers=[]),
                        "inventory-group", "inventory-order-created-consumer"):
    pass
assert current_context() == {}
legacy = SimpleNamespace(id=1,aggregate_id=123,user_id=4,topic="orders",retry_count=0,observability_metadata=None)
identities=[]
for namespace in ("order","order","inventory"):
    with publish_attempt(legacy,namespace) as legacy_metadata:
        identities.append(legacy_metadata["event_id"])
assert identities[0]==identities[1] and identities[0]!=identities[2]
spans = exporter.get_finished_spans()
delayed = next(span for span in spans if span.name=="outbox.publish")
assert delayed.parent is None and len(delayed.links)==1
assert delayed.links[0].context.trace_id==origin.get_span_context().trace_id
assert delayed.links[0].attributes=={"seckill.link.reason":"delayed"}
processed = [span for span in spans if span.name=="kafka.process"]
assert processed[0].parent is None and len(processed[0].links)==1
assert processed[0].attributes["seckill.outcome"]=="duplicate"
assert processed[1].attributes["seckill.outcome"]=="processed" and not processed[1].links
from seckill_observability.tracing import SAFE_EVENTS
assert all(event.name in SAFE_EVENTS for span in spans for event in span.events)
assert any(event.name == 'message.processed' for span in spans for event in span.events)
print("delayed root/link, legacy messages, duplicate and context cleanup OK")
provider.shutdown()
