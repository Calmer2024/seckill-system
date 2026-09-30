import { check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

export const ordersAccepted = new Counter('business_orders_accepted');
export const duplicateRequests = new Counter('business_duplicate_requests');
export const outOfStockRequests = new Counter('business_out_of_stock_requests');
export const rejectedRequests = new Counter('business_rejected_requests');
export const authFailures = new Counter('business_auth_failures');
export const requestTimeouts = new Counter('business_request_timeouts');
export const businessSuccessRate = new Rate('business_order_success_rate');
export const businessResponseTime = new Trend('business_order_response_time');

export const BASE_URL = (__ENV.BASE_URL || 'http://frontend_nginx').replace(/\/$/, '');
export const PRODUCT_ID = Number(__ENV.PRODUCT_ID || 900001);
export const PRODUCT_IDS = (__ENV.PRODUCT_IDS || String(PRODUCT_ID))
  .split(',')
  .map((value) => Number(value.trim()))
  .filter((value) => Number.isInteger(value) && value > 0);
export const USER_ID_START = Number(__ENV.USER_ID_START || 9000001);
export const USER_COUNT = Number(__ENV.USER_COUNT || 10000);

export function httpParams(userId = null, tags = {}) {
  const headers = {
    'X-Request-ID': `${__ENV.PERF_RUN_ID || 'local'}-${__VU}-${__ITER}`,
  };
  if (userId !== null) {
    headers['X-User-Id'] = String(userId);
  }
  return {
    headers,
    tags,
    timeout: __ENV.HTTP_TIMEOUT || '10s',
  };
}

export function randomProductId() {
  return PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];
}

export function parseStages(value, fallback) {
  const raw = (value || fallback).split(',').map((item) => item.trim()).filter(Boolean);
  return raw.map((item) => {
    const [duration, target] = item.split(':');
    return { duration, target: Number(target) };
  });
}

export function orderUserId() {
  const vus = Number(__ENV.CONTENTION_VUS || USER_COUNT);
  return USER_ID_START + (__VU - 1) + (__ITER * vus);
}

export function recordProductResponse(response) {
  check(response, {
    'product response received': (item) => item.status > 0,
    'product response is successful': (item) => item.status === 200,
  });
}

export function recordInventoryResponse(response) {
  check(response, {
    'inventory response received': (item) => item.status > 0,
    'inventory response is successful': (item) => item.status === 200,
  });
}

export function recordOrderResponse(response) {
  const duration = response.timings ? response.timings.duration : 0;
  businessResponseTime.add(duration);

  if (response.status === 0) {
    requestTimeouts.add(1);
    businessSuccessRate.add(false);
    return;
  }

  let body = {};
  try {
    body = response.json();
  } catch (_) {
    body = {};
  }

  if (response.status >= 200 && response.status < 300) {
    ordersAccepted.add(1);
    businessSuccessRate.add(true);
    check(response, { 'order accepted': (item) => item.status === 200 || item.status === 201 });
    return;
  }

  businessSuccessRate.add(false);
  const code = body.code || '';
  if (response.status === 401) {
    authFailures.add(1);
  } else if (code === 'DUPLICATE_ORDER') {
    duplicateRequests.add(1);
  } else if (code === 'OUT_OF_STOCK') {
    outOfStockRequests.add(1);
  } else {
    rejectedRequests.add(1);
  }
  check(response, { 'order response classified': (item) => item.status > 0 });
}
