"""Read-only/rejected requests against real services, preserving ingress sampling."""
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def read(url, data=None, headers=None, with_headers=False):
    try:
        response = urlopen(Request(url, data=data, headers=headers or {}), timeout=20)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read()
        result = (response.status, json.loads(body) if body.startswith((b'{', b'[')) else None)
        return (*result, {k.lower(): v for k, v in response.headers.items()}) if with_headers else result


def main():
    base = 'http://127.0.0.1:8100/api/observability/traces'
    for attempt in range(20):
        status, catalogue = read('http://127.0.0.1/api/products')
        if status == 200:
            break
        time.sleep(.5)
    assert status == 200, ('gateway not ready', status)
    product_id = catalogue[0]['id']
    cases = [('product_list', '/api/products?page=1&size=5', None, 200),
             ('product_detail', f'/api/products/{product_id}', None, 200),
             ('inventory_detail', f'/api/inventory/products/{product_id}', None, 200),
             ('inventory_missing', '/api/inventory/products/899999999', None, 404),
             ('order_list', '/api/orders', None, 200),
             ('order_missing', '/api/orders/899999999', None, 404),
             ('order_rejected', '/api/orders/seckill', b'{"product_id":899999999,"quantity":1}', 404)]
    records = []
    requests = 0
    for name, path, body, expected in cases:
        candidates = []
        found = None
        for batch in range(8):
            for attempt in range(8):
                status, _, headers = read('http://127.0.0.1' + path, body, {
                    'X-User-Id': '899999999', 'Content-Type': 'application/json'}, with_headers=True)
                requests += 1
                assert status == expected, (name, status)
                candidates.append(headers['x-trace-id'])
            time.sleep(2)
            for candidate in candidates:
                code, _ = read(base + '/' + candidate)
                if code == 200:
                    found = candidate
                    break
            if found:
                break
        assert found, ('no sampled evidence', name)
        tid = found
        records.append((name, tid))
    report = {'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'fixtures': False,
              'data_reset': False, 'sampler_unchanged': True, 'requests': requests, 'traces': {}}
    for name, tid in records:
        for attempt in range(20):
            status, detail = read(base + '/' + tid)
            if status == 200:
                break
            time.sleep(.5)
        assert status == 200, (name, status)
        spans = detail['spans']
        root = next(s for s in spans if s['kind'] == 'SPAN_KIND_SERVER')
        assert root['attributes'].get('seckill.request_id')
        assert root['attributes']['seckill.outcome'] in ('success', 'rejected')
        assert all(s['resource']['service.version'].startswith('source-sha256:') for s in spans)
        queries = [s for s in spans if s['name'] == 'SELECT']
        assert queries and all(s['attributes'].get('db.query.fingerprint') for s in queries), (name, [s['attributes'] for s in queries])
        assert all('db.statement' not in s['attributes'] for s in spans)
        if name.endswith('list'):
            assert 'seckill.result_count' in root['attributes']
            assert any(s['name'] in ('product.list', 'order.list') for s in spans)
        if name == 'inventory_missing':
            assert root['attributes']['seckill.product_id'] == '899999999'
        if name in ('product_detail', 'inventory_detail'):
            assert root['attributes']['seckill.product_id'] == str(product_id)
        if name == 'inventory_detail':
            assert all('seckill.' + field in root['attributes'] for field in ('available_stock', 'reserved_stock', 'sold_stock'))
        if name == 'order_missing':
            assert root['attributes']['seckill.order_id'] == '899999999'
        if name == 'order_rejected':
            assert root['attributes']['seckill.product_id'] == '899999999'
            assert int(root['attributes']['seckill.quantity']) == 1
            assert detail['summary']['business_state_reason'] == 'not_created'
        report['traces'][name] = {'trace_id': tid, 'version': root['resource']['service.version'],
            'root_attributes': root['attributes'], 'business': detail['summary']['business'],
            'sql_fingerprints': [s['attributes']['db.query.fingerprint'] for s in queries]}
    status, lifecycle = read(base + '/lifecycle?order_id=899999999&window=1h')
    assert status == 200 and lifecycle['timeline'] and not lifecycle['authoritative_order_state']
    report['lifecycle_nodes'] = len(lifecycle['timeline'])
    report['passed'] = True
    output = Path(__file__).resolve().parents[2] / 'docs/observability/trace-collection-validation.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'traces': len(records), 'lifecycle_nodes': len(lifecycle['timeline']), 'report': str(output)}))


if __name__ == '__main__':
    main()
