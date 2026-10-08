"""Three-minute local observation; reads and rejected requests only."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from trace_live_check import request, BASE, GATEWAY


def main():
    started = time.monotonic()
    rounds, ids, latencies = [], set(), []
    for index in range(7):
        for path, data, headers, expected in [
            ('/api/products?page=1&size=5', None, {}, 200),
            ('/api/inventory/products/1', None, {}, 200),
            ('/api/orders', None, {'X-User-Id': '899999999'}, 200),
            ('/api/orders/seckill', b'{"product_id":899999999,"quantity":1}',
             {'X-User-Id': '899999999', 'Content-Type': 'application/json'}, 404)]:
            code, headers, _ = request(GATEWAY + path, data, headers)
            assert code == expected, (path, code)
            ids.add(next(value for key, value in headers.items() if key.lower() == 'x-trace-id'))
        checks = {}
        for name, url in [('controller', BASE + '/api/performance/health'),
                          ('collector', 'http://127.0.0.1:13133/'), ('tempo', 'http://127.0.0.1:3200/ready'),
                          ('loki', 'http://127.0.0.1:3100/ready')]:
            code, _, _ = request(url)
            assert code == 200, (name, code)
            checks[name] = code
        counts = {}
        for query in ('method:GET', 'method:POST', '-method:GET', 'db_system:mysql'):
            before = time.monotonic()
            code, _, body = request(BASE + '/api/observability/traces?' + urlencode({'window': '1h', 'query': query}))
            elapsed = round((time.monotonic() - before) * 1000, 2)
            latencies.append(elapsed)
            assert code == 200 and body['traces'], (query, code)
            counts[query] = len(body['traces'])
            if query == '-method:GET':
                assert all(not r['name'].startswith('GET ') for r in body['traces'])
        rounds.append({'round': index + 1, 'health': checks, 'query_counts': counts})
        print(json.dumps(rounds[-1]), flush=True)
        if index < 6:
            time.sleep(30)
    evidence = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        details = list(pool.map(lambda tid: (tid, request(BASE + '/api/observability/traces/' + tid)), ids))
    for tid, (code, _, detail) in details:
        if code == 404:  # The deployed head sampler remains unchanged.
            continue
        assert code == 200, (tid, code)
        spans = detail['spans']
        assert len({s['span_id'] for s in spans}) == len(spans)
        root = next(s for s in spans if s['kind'] == 'SPAN_KIND_SERVER')
        assert root['attributes'].get('seckill.outcome')
        assert root['resource']['service.version'].startswith('source-sha256:')
        assert all(s['attributes'].get('db.query.fingerprint') for s in spans if s['name'] == 'SELECT')
        evidence.append(tid)
    assert evidence, 'No sampled evidence'
    report = {'passed': True, 'duration_seconds': round(time.monotonic() - started, 1),
              'requests': len(ids), 'sampled_traces_verified': len(evidence), 'rounds': rounds,
              'query_ms': {'min': min(latencies), 'max': max(latencies)}, 'data_reset': False,
              'sampler_unchanged': True, 'trace_ids': evidence}
    output = Path(__file__).resolve().parents[2] / 'docs/observability/trace-soak-validation.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('rounds', 'trace_ids')}), flush=True)


if __name__ == '__main__':
    main()
