"""Run inside an existing worker to emit synthetic telemetry without business writes.

docker exec stdout is not in the container log driver. The formatted probe is
written explicitly to PID 1 stdout; it never changes business state or Kafka.
"""
import json
import logging
import os
import uuid

os.environ["SECKILL_TRACE_SAMPLE_RATIO"] = "1"
from opentelemetry import trace
from seckill_observability.context import log_context
from seckill_observability.logging import ContextFilter, JsonFormatter
from seckill_observability.tracing import configure_tracing

configure_tracing(None, "order-worker")
event_id = str(uuid.uuid4())
with log_context(request_id="p3-" + event_id, event_id=event_id):
    with trace.get_tracer("p3-validation").start_as_current_span("p3.validation"):
        record = logging.LogRecord("p3.validation", logging.INFO, __file__, 1,
                                   "P3 validation password=P3_SYNTHETIC_SECRET Bearer P3_SYNTHETIC_TOKEN example@example.invalid 13800000000", (), None)
        record.event = "p3_validation"
        ContextFilter().filter(record)
        line = JsonFormatter("order-worker").format(record)
        with open("/proc/1/fd/1", "w") as output:
            output.write(line + "\n")
        fields = json.loads(line)
trace.get_tracer_provider().force_flush(3000)
print(json.dumps({"trace_id": fields["trace_id"], "event_id": event_id, "request_id": fields["request_id"], "timestamp": fields["timestamp"]}))
