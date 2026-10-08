"""Run in an isolated order API container against real inventory, without business writes.

Only the order repositories are substituted, so a nonexistent product reaches
the real inventory API and is rejected before a reservation can be created.
"""
import json
import threading
import time
from unittest.mock import Mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import uvicorn
from opentelemetry import trace
from app.main import app
from app.api.dependencies import get_order_application_service
from app.application.services.order_service import OrderApplicationService, InventoryServiceClient
from app.core.security import CurrentUser, get_current_user

service = OrderApplicationService.__new__(OrderApplicationService)
service.order_repository = Mock()
service.order_repository.find_active_by_user_and_product.return_value = None
service.product_repository = Mock()
service.product_repository.get_product.return_value = Mock(price=1)
service.id_generator = Mock()
service.id_generator.next_id.return_value = 899999999999999999
service.inventory_client = InventoryServiceClient()
service.direct_producer = None
app.dependency_overrides[get_order_application_service] = lambda: service
app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=899999999)
server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8180, log_config=None, access_log=False))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started and time.monotonic() < deadline:
    time.sleep(.02)
assert server.started
try:
    urlopen(Request('http://127.0.0.1:8180/api/orders/seckill', data=json.dumps({'product_id': 899999999, 'quantity': 1}).encode(), headers={'Content-Type': 'application/json'}))
    raise AssertionError('nonexistent product was accepted')
except HTTPError as response:
    assert response.code == 404
    trace_id = response.headers['X-Trace-ID']
    print('SMOKE_TRACE=' + trace_id)
service.order_repository.create_pending_order_and_outbox.assert_not_called()
trace.get_tracer_provider().force_flush(4000)
server.should_exit = True
thread.join(5)
