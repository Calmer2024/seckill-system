import http from 'k6/http';
import {check} from 'k6';
export const options = {
  vus: 4,
  duration: __ENV.DURATION || '20s',
  summaryTrendStats: ['avg','med','p(95)','p(99)','max'],
  thresholds: {http_req_failed:['rate==0'], checks:['rate==1']},
};
let sample = null;
export default function() {
  // Fixed isolation targets: never accept a caller-supplied external URL.
  const service = __ENV.TARGET === 'off' ? 'product-off' : 'product-on';
  const response = http.get(`http://${service}:8000/api/products`, {timeout:'3s'});
  check(response, {'catalog responds 200': r=>r.status===200});
  if (!sample && response.headers['X-Trace-Id']) {
    sample = {trace_id:response.headers['X-Trace-Id'],request_id:response.headers['X-Request-Id']};
    console.log('P4_TRACE_SAMPLE '+JSON.stringify(sample));
  }
}
export function handleSummary(data) {
  return {['/results/'+__ENV.RESULT+'.json']:JSON.stringify(data),stdout:JSON.stringify({result:__ENV.RESULT,requests:data.metrics.http_reqs.values.count})+'\n'};
}
