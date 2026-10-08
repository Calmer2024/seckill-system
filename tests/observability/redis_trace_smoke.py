"""Real Lua execution using absent keys; rejects before changing business data."""
from opentelemetry import trace
from app.main import app
from app.core.database import redis_client
from app.services.inventory_service import StockCacheService

cache = StockCacheService(redis_client)
user_id = product_id = order_id = 899999999
keys = [cache.stock_key(product_id), cache.user_purchase_key(user_id, product_id), cache.reservation_status_key(order_id)]
assert redis_client.exists(*keys) == 0, 'validation keys are already in use'
with trace.get_tracer('seckill.validation').start_as_current_span('validation.redis') as root:
    assert cache.reserve_stock(user_id, product_id, order_id, 1) == -1
    print('REDIS_TRACE=' + format(root.get_span_context().trace_id, '032x'))
assert redis_client.exists(*keys) == 0, 'Lua rejected request unexpectedly wrote business keys'
trace.get_tracer_provider().force_flush(4000)
