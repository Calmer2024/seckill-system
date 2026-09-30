import http from 'k6/http';

import {
  BASE_URL,
  httpParams,
  randomProductId,
  recordInventoryResponse,
  recordProductResponse,
} from './lib.js';

export const options = {
  scenarios: {
    stability_soak: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.SOAK_RPS || 300),
      timeUnit: '1s',
      duration: __ENV.SOAK_DURATION || '1h',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 300),
      maxVUs: Number(__ENV.MAX_VUS || 1000),
    },
  },
};

export default function () {
  const productId = randomProductId();
  if (Math.random() < 0.8) {
    const response = http.get(
      `${BASE_URL}/api/products/${productId}`,
      httpParams(null, { scenario: 'stability-soak', operation: 'product-read' }),
    );
    recordProductResponse(response);
    return;
  }

  const response = http.get(
    `${BASE_URL}/api/inventory/products/${productId}`,
    httpParams(null, { scenario: 'stability-soak', operation: 'inventory-read' }),
  );
  recordInventoryResponse(response);
}
