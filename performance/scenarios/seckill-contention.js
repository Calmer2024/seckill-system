import http from 'k6/http';

import {
  BASE_URL,
  PRODUCT_ID,
  USER_COUNT,
  httpParams,
  orderUserId,
  recordOrderResponse,
} from './lib.js';

const VUS = Number(__ENV.CONTENTION_VUS || USER_COUNT);
const ITERATIONS_PER_VU = Number(__ENV.CONTENTIONS_PER_VU || 1);

export const options = {
  scenarios: {
    seckill_contention: {
      executor: 'per-vu-iterations',
      vus: VUS,
      iterations: ITERATIONS_PER_VU,
      maxDuration: __ENV.MAX_DURATION || '2m',
    },
  },
};

export default function () {
  const userId = orderUserId();
  if (userId >= Number(__ENV.USER_ID_START || 9000001) + USER_COUNT) {
    return;
  }

  const params = httpParams(userId, { scenario: 'seckill-contention' });
  const response = http.post(
    `${BASE_URL}/api/orders/seckill`,
    JSON.stringify({ product_id: PRODUCT_ID, quantity: 1 }),
    {
      ...params,
      headers: {
        ...params.headers,
        'Content-Type': 'application/json',
      },
    },
  );
  recordOrderResponse(response);
}
