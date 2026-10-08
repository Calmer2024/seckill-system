"""Collector/Tempo link preservation only; no database or Kafka writes."""
import sys
import time
from types import SimpleNamespace
from seckill_observability.messaging import publish_attempt, serialize_metadata
from seckill_observability.tracing import configure_tracing, trace_fields

provider = configure_tracing(None, "order-worker")
metadata = {"event_id":"5eadd365-ce7b-42d7-863f-733f599c57f4", "created_at_unix":time.time()-301,
            "traceparent":"00-"+sys.argv[1]+"-"+sys.argv[2]+"-01"}
event = SimpleNamespace(id=1,aggregate_id=999800001,user_id=999800002,topic="p2-link-validation",
                        retry_count=1,observability_metadata=serialize_metadata(metadata))
with publish_attempt(event, "order"):
    print("P2_LINK_TRACE=" + trace_fields()["trace_id"], flush=True)
provider.force_flush(timeout_millis=5000)
provider.shutdown()
