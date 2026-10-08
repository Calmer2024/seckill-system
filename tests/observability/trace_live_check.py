"""Local live-service smoke: real HTTP/SQL/Tempo/Loki, no fixtures or data reset."""
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8100'
GATEWAY = 'http://127.0.0.1'
REPORT = Path(__file__).resolve().parents[2] / 'docs/observability/trace-live-validation.json'


def request(url, data=None, headers=None):
    try:
        response = urlopen(Request(url, data=data, headers=headers or {}), timeout=20)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        return response.status, dict(response.headers), json.loads(body) if body.startswith((b'{', b'[')) else None


def query(**params):
    code, _, body = request(BASE + '/api/observability/traces?' + urlencode({'window': '1h', **params}))
    assert code == 200, (code, body)
    return body['traces']


def main():
    report = {'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'controller': BASE,
              'business_mode': 'existing baseline', 'data_reset': False, 'fixtures': False,
              'health': {}, 'requests': [], 'evidence': {}, 'checks': []}
    for name, url in [('controller', BASE + '/api/performance/health'),
                      ('collector', 'http://127.0.0.1:13133/'), ('tempo', 'http://127.0.0.1:3200/ready'),
                      ('loki', 'http://127.0.0.1:3100/ready')]:
        code, _, _ = request(url)
        report['health'][name] = code
        assert code == 200, (name, code)
    cases = {
        'product_read': ('/api/products', None, {}, 200),
        'inventory_read': ('/api/inventory/products/899999999', None, {}, 404),
        'order_read': ('/api/orders', None, {'X-User-Id': '899999999'}, 200),
        'order_rejected': ('/api/orders/seckill', b'{"product_id":899999999,"quantity":1}',
                           {'X-User-Id': '899999999', 'Content-Type': 'application/json'}, 404),
    }
    captured = {name: [] for name in cases}
    # Keep the deployed head sampler unchanged. Bounded, sequential requests await sampled evidence.
    for batch in range(8):
        for name in cases.keys() - report['evidence'].keys():
            path, data, headers, expected = cases[name]
            for _ in range(8):
                code, response_headers, body = request(GATEWAY + path, data, headers)
                assert code == expected, (name, code)
                if name == 'order_rejected':
                    assert body.get('code') == 'PRODUCT_NOT_FOUND', body
                trace_id = {key.lower(): value for key, value in response_headers.items()}.get('x-trace-id')
                assert trace_id and len(trace_id) == 32, (name, response_headers.keys())
                captured[name].append(trace_id)
                report['requests'].append({'case': name, 'http_status': code, 'trace_id': trace_id})
                time.sleep(.05)
        time.sleep(4)
        for name, ids in captured.items():
            if name in report['evidence']:
                continue
            for trace_id in reversed(ids):
                code, _, detail = request(BASE + '/api/observability/traces/' + trace_id)
                if code == 404:
                    continue
                assert code == 200 and detail['spans'], (trace_id, code)
                spans = detail['spans']
                assert any(s['attributes'].get('db.system') == 'mysql' for s in spans), name
                assert all('db.statement' not in s['attributes'] and 'http.url' not in s['attributes'] for s in spans)
                if name == 'order_rejected':
                    assert any(s['name'] == 'order.submit' and s['attributes'].get('seckill.error_code') == 'PRODUCT_NOT_FOUND'
                               and s['attributes'].get('seckill.outcome') == 'rejected' for s in spans)
                    business = next(s for s in spans if s['name'] == 'order.submit')
                    assert business['attributes']['seckill.product_id'] == '899999999'
                    assert int(business['attributes']['seckill.quantity']) == 1
                    assert business['attributes'].get('seckill.request_id')
                    assert any(e['name'] == 'business.rejected' for e in business['events'])
                    assert business['resource'].get('service.instance.id')
                    assert detail['summary']['api_result'] == 'rejected'
                    assert detail['analysis']['quality']['completeness'] == 'not_proven'
                    assert all(s['self_duration_ms'] >= 0 for s in spans)
                    report['business_context'] = {'product_id': business['attributes']['seckill.product_id'],
                        'quantity': business['attributes']['seckill.quantity'], 'request_id': business['attributes']['seckill.request_id'],
                        'instance': business['resource']['service.instance.id'], 'events': [e['name'] for e in business['events']]}
                report['evidence'][name] = {'trace_id': trace_id, 'span_count': len(spans),
                    'services': sorted({s['service'] for s in spans}), 'nodes': [s['name'] for s in spans],
                    'error_spans': sum(s['status'] == 'error' for s in spans)}
                break
        if len(report['evidence']) == len(cases):
            break
    assert len(report['evidence']) == len(cases), ('sampled evidence incomplete', report['evidence'].keys())
    rejected = report['evidence']['order_rejected']['trace_id']
    # Detail and search indexing can become visible at different times. Narrow by
    # ID so a bounded 50-result search does not exclude the evidence under load.
    began = time.monotonic()
    for attempt in range(30):
        if rejected in {r['trace_id'] for r in query(query='trace_id:' + rejected + ' error:PRODUCT_NOT_FOUND')}:
            break
        time.sleep(2)
    else:
        raise AssertionError(('search indexing did not catch up', rejected))
    report['search_wait_seconds'] = round(time.monotonic() - began, 2)
    error_rows = query(errors='true')
    for row in error_rows[:3]:
        code, _, detail = request(BASE + '/api/observability/traces/' + row['trace_id'])
        assert code == 200 and any(s['status'] == 'error' for s in detail['spans'])
    report['technical_error_traces'] = len(error_rows)
    assert rejected in {r['trace_id'] for r in query(query='trace_id:' + rejected + ' service:order-api name:"POST /api/orders/seckill"', query_scope='root')}
    assert rejected in {r['trace_id'] for r in query(query='trace_id:' + rejected + ' name:order.submit', query_scope='all')}
    report['checks'] += ['response ID matches stored trace', 'real MySQL child spans', 'business rejection code query',
                         'root service/name query', 'all-spans query', 'sensitive attributes omitted']
    logs = []
    for _ in range(6):
        code, _, data = request(BASE + '/api/observability/logs?' + urlencode({'window': 15, 'trace_id': rejected}))
        assert code == 200, code
        logs = data.get('logs', [])
        if logs:
            break
        time.sleep(2)
    report['correlated_logs'] = {'trace_id': rejected, 'count': len(logs)}
    assert logs, ('no correlated Loki logs', data.keys())
    report['checks'].append('real Loki trace correlation')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/?trace_range=1h&trace=' + rejected + '#traces')
        page.locator('#tx-node-header h2').wait_for(timeout=30000)
        while page.locator('#tx-tree [data-fold][aria-expanded=false]:visible').count():
            page.locator('#tx-tree [data-fold][aria-expanded=false]:visible').first.click()
            page.wait_for_timeout(190)
        page.wait_for_timeout(250)
        assert page.locator('[data-span]:visible').count() == report['evidence']['order_rejected']['span_count']
        assert page.evaluate('scrollY === 0 && document.documentElement.scrollHeight === innerHeight')
        page.locator('[data-tab="attributes"]').click()
        screenshot = Path(os.getenv('TEMP', '.')) / 'seckill-trace-live.png'
        page.screenshot(path=str(screenshot))
        page.locator('[data-logs]').click()
        page.wait_for_function("document.querySelector('#log-search input[name=trace_id]').value === '" + rejected + "'")
        page.locator('#tx-return-trace').click()
        assert page.locator('[data-tab="attributes"]').get_attribute('aria-pressed') == 'true'
        page.locator('[data-close]').click()
        page.locator('#tx-query').fill('trace_id:' + rejected + ' service:order-api name:"POST /api/orders/seckill"')
        page.locator('#tx-query').press('Enter')
        page.locator('[data-trace="' + rejected + '"]').wait_for(timeout=30000)
        assert page.locator('[data-trace="' + rejected + '"]').count() == 1
        assert not errors, errors
        report['screenshot'] = str(screenshot)
        report['checks'] += ['live browser list/query', 'live tree and attributes', 'local scrolling',
                             'logs navigation and return', 'no browser errors']
        browser.close()
    report['passed'] = True
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'requests': len(report['requests']), 'evidence': report['evidence'],
                      'logs': report['correlated_logs']['count'], 'report': str(REPORT)}))


if __name__ == '__main__':
    main()
