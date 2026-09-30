import http from 'k6/http';

import {
  BASE_URL,
  httpParams,
  parseStages,
  randomProductId,
  recordProductResponse,
} from './lib.js';

export const options = {
  scenarios: {
    product_read_ramp: {
      executor: 'ramping-arrival-rate',
      startRate: Number(__ENV.START_RPS || 50),
      timeUnit: '1s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 200),
      maxVUs: Number(__ENV.MAX_VUS || 2000),
      stages: parseStages(
        __ENV.STAGES,
        '30s:50,30s:100,30s:200,30s:500,30s:1000',
      ),
    },
  },
};

export default function () {
  const response = http.get(
    `${BASE_URL}/api/products/${randomProductId()}`,
    httpParams(null, { scenario: 'product-read' }),
  );
  recordProductResponse(response);
}
