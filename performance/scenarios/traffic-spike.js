import http from 'k6/http';

import {
  BASE_URL,
  httpParams,
  randomProductId,
  recordProductResponse,
} from './lib.js';

export const options = {
  scenarios: {
    traffic_spike: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 500),
      maxVUs: Number(__ENV.MAX_VUS || 4000),
      stages: [
        { duration: '2s', target: Number(__ENV.SPIKE_RPS || 2000) },
        { duration: __ENV.SPIKE_HOLD || '10s', target: Number(__ENV.SPIKE_RPS || 2000) },
        { duration: '10s', target: 0 },
      ],
    },
  },
};

export default function () {
  const response = http.get(
    `${BASE_URL}/api/products/${randomProductId()}`,
    httpParams(null, { scenario: 'traffic-spike' }),
  );
  recordProductResponse(response);
}
