"""Browser regression check. Run against the local controller; fixtures never enter production."""
import json
import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.getenv('TRACE_UI_URL', 'http://127.0.0.1:8100')
TRACE, OTHER = 'a' * 32, 'b' * 32
START = 1791446400000000000


def span(index, parent, name, service, duration, attrs=None, error=False):
    return {'span_id': f'{index:016x}', 'parent_span_id': f'{parent:016x}' if parent else '',
            'name': name, 'service': service, 'kind': 'SPAN_KIND_SERVER',
            'start_time_ns': str(START + index * 1000000), 'duration_ms': duration,
            'status': 'error' if error else 'ok', 'attributes': attrs or {}, 'links': []}


SPANS = [span(1, 0, 'POST /api/orders', 'order-api', 1800, {'http.request.method': 'POST', 'http.route': '/api/orders', 'http.response.status_code': 500}),
         span(2, 1, 'order.submit', 'order-api', 1700, {'seckill.order_id': '91284', 'seckill.outcome': 'error'}, True),
         span(3, 2, 'reserve inventory', 'inventory-api', 640),
         span(4, 3, 'redis reserve', 'inventory-api', 32, {'db.system': 'redis', 'db.operation': 'EVAL'}),
         span(5, 2, 'publish order.created', 'order-worker', 71, {'messaging.system': 'kafka', 'messaging.destination.name': 'order.created'}),
         span(6, 99, 'retry inventory result', 'inventory-worker', 120, error=True)]
SPANS[-1]['links'] = [{'trace_id': OTHER, 'span_id': '0000000000000001', 'reason': 'retry'}]
SPANS[1]['events'] = [{'name': 'business.failed', 'time_ns': str(START + 3000000), 'attributes': {'seckill.order_id': '91284'}}]
SPANS[1]['resource'] = {'service.version': 'test-v1', 'service.instance.id': 'test-pod'}
SPANS[1]['self_duration_ms'] = 889


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        errors = []
        delayed, searches = [], []
        bulk = False
        page.on('pageerror', lambda error: errors.append(str(error)))

        def respond(route):
            path = route.request.url.split('/api/observability/traces', 1)[1]
            if path.startswith('/lifecycle?'):
                route.fulfill(content_type='application/json', body=json.dumps({'trace_count': 1, 'truncated': False,
                    'unavailable_traces': 0, 'sampling_note': 'sampled', 'timeline': [{'trace_id': OTHER,
                    'span_id': SPANS[0]['span_id'], 'name': 'order.confirmed', 'service': 'order-worker',
                    'time_ns': str(START), 'duration_ms': 100, 'state': 'CREATED', 'events': []}]}))
                return
            if path.endswith('/summary'):
                route.fulfill(content_type='application/json', body=json.dumps({'status': 'error', 'input': 'POST /api/orders', 'output': 'HTTP 500', 'error': 'order.submit'}))
                return
            if path == '/' + 'c' * 32:
                delayed.append(route)
                return
            if path == '/' + 'd' * 32:
                route.fulfill(status=503, content_type='application/json', body='{}')
                return
            if path.startswith('?'):
                params = parse_qs(path[1:])
                searches.append(params)
                body = {'traces': [{'trace_id': TRACE, 'name': 'POST /api/orders', 'service': 'order-api', 'duration_ms': 1800, 'start_time_ns': str(START), 'status': 'unknown'},
                                   {'trace_id': OTHER, 'name': 'inventory.result', 'service': 'inventory-worker', 'duration_ms': 120, 'start_time_ns': str(START), 'status': 'unknown'}],
                        'window_minutes': 15, 'limit': 50, 'sampled_at': START // 1000000000, 'sampling_note': '仅测试已采样数据'}
                if params.get('query') == ['name:missing']:
                    body['traces'] = []
                if bulk:
                    body['traces'] = [{'trace_id': f'{index:032x}', 'name': ['POST /api/orders', 'GET /api/products', 'inventory.reserve', 'order.created.publish'][index % 4] + f' · {index}',
                                       'service': ['order-api', 'product', 'inventory-api', 'order-worker'][index % 4], 'duration_ms': index * 87.3,
                                       'start_time_ns': str(START - index * 1000000000), 'status': 'error' if index % 9 == 0 else 'ok'} for index in range(1, 46)]
            else:
                body = {'trace_id': path[1:], 'spans': SPANS if path[1:] == TRACE else [SPANS[0]], 'scope': 'environment_live',
                        'analysis': {'response_ms': 1800, 'observed_span_ms': 1800, 'quality': {},
                            'slowest': [{'span_id': SPANS[1]['span_id'], 'name': 'order.submit', 'self_ms': 889}]}}
                if bulk:
                    body['spans'] = SPANS + [span(index, 1, f'order processing step {index}', 'order-api', 12) for index in range(7, 50)]
            route.fulfill(content_type='application/json', body=json.dumps(body))

        page.route('**/api/observability/traces**', respond)
        page.goto(BASE + '/#traces')
        page.locator('[data-trace]').first.wait_for()
        assert page.locator('[data-trace]').count() == 2
        page.wait_for_function("document.querySelector('[data-col=input]').tagName === 'TH' && document.querySelector('#trace-results [data-col=input]').textContent === 'POST /api/orders'")
        assert page.locator('#trace-results [data-col="output"]').first.inner_text() == 'HTTP 500'
        assert page.locator('#workspace-traces .workspace-heading').count() == 0
        assert page.locator('#workspace-traces .tx-project-bar').count() == 0
        assert page.locator('.sidebar').evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgb(250, 251, 253)'
        # Shared controls remain named and equal-sized after icon-only conversion.
        controls = page.locator('#tx-reset,#tx-save-view,#tx-views-button,#tx-columns-button,#tx-refresh')
        styles = controls.evaluate_all("""els=>els.map(el=>{const c=getComputedStyle(el);return {height:el.getBoundingClientRect().height,background:c.backgroundColor,border:c.borderWidth,shadow:c.boxShadow,label:el.getAttribute('aria-label'),tooltip:el.dataset.tooltip,text:el.textContent.trim(),icon:el.querySelector('use')?.getAttribute('href')};})""")
        assert len(styles) == 5
        for style in styles:
            assert style['height'] == 32 and style['border'] == '0px', style
            assert style['background'] == 'rgba(0, 0, 0, 0)' and style['shadow'] == 'none', style
            assert style['label'] and style['tooltip'] and style['icon'].startswith('/icons.svg#') and not style['text'], style
        for selector in ['#tx-time-button', '#workspace-traces .tx-toolbar .tx-segment', '.tx-sort-control .select-trigger']:
            assert page.locator(selector).evaluate('el=>el.getBoundingClientRect().height') == 32, selector
        page.locator('#tx-save-view').hover()
        assert page.locator('#tx-save-view').evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
        page.locator('#tx-save-view').focus()
        assert page.locator('#tx-save-view').evaluate('el=>getComputedStyle(el).outlineWidth') == '2px'
        page.locator('#tx-query').focus()
        checkbox = page.locator('[name=services][value="order-api"]')
        checkbox.check()
        page.wait_for_timeout(100)
        geometry = checkbox.evaluate("""el=>{const icon=el.parentElement.querySelector('svg'),a=el.getBoundingClientRect(),b=icon.getBoundingClientRect();return {dx:Math.abs(a.x+a.width/2-b.x-b.width/2),dy:Math.abs(a.y+a.height/2-b.y-b.height/2),color:getComputedStyle(icon).color,width:b.width};}""")
        assert geometry['dx'] < 0.5 and geometry['dy'] < 0.5 and geometry['width'] == 12, geometry
        assert geometry['color'] == 'rgb(255, 255, 255)'
        assert page.locator('[data-clear-filter="services"]').count() == 1
        page.reload()
        page.locator('[data-trace]').first.wait_for()
        assert page.locator('[name=services][value="order-api"]').is_checked()
        page.locator('[data-clear-filter="services"]').click()
        page.wait_for_timeout(100)
        assert not page.locator('[name=services][value="order-api"]').is_checked()
        page.locator('#tx-filter-toggle').click()
        page.wait_for_timeout(230)
        assert page.locator('#workspace-traces .tx-facets').first.evaluate('el=>el.inert')
        assert page.locator('#workspace-traces .tx-table-scroll').first.evaluate('el=>el.getBoundingClientRect().width') > 1600
        page.locator('#tx-filter-toggle').click()
        page.wait_for_timeout(230)
        before = len(searches)
        page.locator('#tx-query').fill('status:success')
        page.locator('#tx-query').press('Enter')
        assert 'error、ok、unset' in page.locator('#tx-query-error').inner_text()
        assert len(searches) == before
        page.locator('#tx-query').fill('')
        page.locator('#tx-query').press('Enter')
        page.wait_for_timeout(100)
        page.locator('#tx-save-view').click()
        page.locator('#tx-save-view-form input').fill('storage failure')
        page.evaluate("() => {window.realSetItem=Storage.prototype.setItem;Storage.prototype.setItem=()=>{throw new Error('blocked');};}")
        page.locator('#tx-save-view-form button[type=submit]').click()
        assert '无法保存视图' in page.locator('#tx-save-view-form [role=alert]').inner_text()
        page.evaluate('() => {Storage.prototype.setItem=window.realSetItem;}')
        page.locator('#tx-refresh').click()
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
        page.locator('#tx-time-button').click()
        assert page.locator('[data-range]').count() == 10
        page.locator('[data-range="3h"]').click()
        page.wait_for_function("document.querySelector('#trace-results [data-trace]') !== null")
        assert searches[-1]['window'] == ['3h']
        page.locator('#tx-time-button').click()
        page.locator('[data-range="6h"]').hover()
        page.locator('[data-default="6h"]').click()
        assert 'Default' in page.locator('#workspace-traces .tx-time-option').filter(has=page.locator('[data-range="6h"]')).inner_text()
        page.locator('#tx-relative').fill('15h')
        page.locator('#tx-relative').press('Enter')
        page.wait_for_timeout(100)
        assert searches[-1]['window'] == ['15h']
        page.locator('#tx-time-button').click()
        page.locator('[data-choose-dates]').click()
        page.locator('#tx-dates-form input[name="start"]').fill('2026-10-01T08:00')
        page.locator('[data-calendar="start"]').click()
        page.locator('#tx-calendar [data-day="3"]').click()
        assert page.locator('#tx-dates-form input[name="start"]').input_value() == '2026-10-03T08:00'
        page.locator('#tx-dates-form input[name="start"]').fill('2026-10-01T08:00')
        page.locator('#tx-dates-form input[name="end"]').fill('2026-10-02T08:00')
        page.locator('#tx-dates-form button[type="submit"]').click()
        page.wait_for_timeout(100)
        assert searches[-1]['window'] == ['custom']
        assert int(searches[-1]['end'][0]) - int(searches[-1]['start'][0]) == 86400
        page.locator('#tx-query').focus()
        page.locator('[data-query-field="name"]').click()
        assert page.locator('#tx-query').input_value() == 'name:'
        page.locator('[data-operator="not"]').click()
        assert page.locator('#tx-query').input_value() == '-name:'
        page.locator('#tx-query').fill('name:"POST /api/orders"')
        page.locator('#tx-query').press('Enter')
        page.wait_for_timeout(100)
        assert searches[-1]['query'] == ['name:"POST /api/orders"']
        page.locator('#workspace-traces .tx-sort-control .select-trigger').click()
        page.locator('#workspace-traces .tx-sort-control [data-value="duration"]').click()
        page.locator('#tx-save-view').click()
        page.locator('#tx-save-view-form input').fill('订单请求调查')
        page.locator('#tx-save-view-form button[type="submit"]').click()
        page.locator('#tx-reset').click()
        page.wait_for_timeout(100)
        assert searches[-1]['window'] == ['6h']
        assert '最新优先' in page.locator('#workspace-traces .tx-sort-control .select-trigger').inner_text()
        page.locator('#tx-views-button').click()
        page.locator('[data-load-view]').click()
        page.wait_for_timeout(100)
        assert searches[-1]['window'] == ['custom']
        assert searches[-1]['query'] == ['name:"POST /api/orders"']
        assert '耗时最长' in page.locator('#workspace-traces .tx-sort-control .select-trigger').inner_text()
        page.locator('#tx-columns-button').click()
        page.locator('[data-column="input"]').uncheck()
        assert page.locator('[data-col="input"]').first.is_hidden()
        page.locator('[data-column="input"]').check()
        page.locator('#tx-columns-button').click()
        page.locator('[data-trace] .tx-record-name').first.click()
        page.locator('#tx-node-header h2').wait_for()
        drawer_buttons = page.locator('#trace-detail .tx-peek-header button:not(.tx-copy),#trace-detail .tx-tree-actions button')
        for style in drawer_buttons.evaluate_all("els=>els.map(el=>({height:el.getBoundingClientRect().height,bg:getComputedStyle(el).backgroundColor,border:getComputedStyle(el).borderWidth,name:el.getAttribute('aria-label')}))"):
            assert style['height'] == 32 and style['bg'] == 'rgba(0, 0, 0, 0)' and style['border'] == '0px' and style['name'], style
        sprite = ET.fromstring(page.request.get(BASE + '/icons.svg').text())
        symbols = {node.get('id') for node in sprite.iter() if node.get('id')}
        for ref in page.locator('svg use').evaluate_all("els=>els.map(el=>el.getAttribute('href'))"):
            assert ref.startswith('/icons.svg#') and ref.split('#')[1] in symbols, ref
        page.locator('[data-step="1"]').click()
        page.wait_for_function("document.querySelectorAll('#tx-tree [data-span]').length === 1")
        assert page.locator('[data-step="1"]').is_disabled()
        page.locator('[data-step="-1"]').click()
        page.wait_for_function("document.querySelectorAll('#tx-tree [data-span]').length === 6")
        assert page.locator('[data-step="-1"]').is_disabled()
        assert page.locator('[data-span]:visible').count() == 5  # grandchild initially hidden
        section = page.locator('#workspace-traces .tx-section').first
        section.locator('summary').click()
        assert section.get_attribute('data-expanded') == 'false'
        assert section.locator('.tx-disclosure-body').evaluate("el=>getComputedStyle(el).transitionDuration") == '0.18s, 0.18s, 0s'
        page.wait_for_timeout(230)
        assert section.get_attribute('open') is None
        section.locator('summary').click()
        assert section.get_attribute('open') is not None
        section.locator('summary').click()
        section.locator('summary').click()
        page.wait_for_timeout(230)
        assert section.get_attribute('open') is not None
        assert section.get_attribute('data-expanded') == 'true'
        def expand_tree():
            for _ in range(100):
                buttons=page.locator('#tx-tree [data-fold][aria-expanded=false]:visible')
                if not buttons.count(): break
                buttons.first.click()
                page.wait_for_timeout(190)
        def collapse_tree():
            for _ in range(100):
                buttons=page.locator('#tx-tree [data-fold][aria-expanded=true]:visible')
                if not buttons.count(): break
                buttons.last.click()
                page.wait_for_timeout(190)
        expand_tree()
        page.wait_for_timeout(230)
        assert page.locator('[data-span]:visible').count() == 6
        page.locator('[data-span="0000000000000004"]').click()
        assert page.locator('#tx-node-header').inner_text().find('redis reserve') >= 0
        page.locator('[data-tab="analysis"]').click()
        page.locator('[data-focus-span]').click()
        assert 'order.submit' in page.locator('#tx-node-header').inner_text()
        page.locator('[data-tab="events"]').click()
        assert 'business.failed' in page.locator('#tx-node-body').inner_text()
        page.locator('[data-tab="runtime"]').click()
        assert 'test-v1' in page.locator('#tx-node-body').inner_text()
        page.locator('[data-tab="lifecycle"]').click()
        page.locator('#tx-lifecycle-form button[type=submit]').click()
        page.locator('#tx-lifecycle-result [data-related]').first.wait_for()
        assert 'CREATED' in page.locator('#tx-lifecycle-result').inner_text()
        page.locator('#tx-lifecycle-result [data-related]').first.click()
        page.wait_for_function("document.querySelectorAll('#tx-tree [data-span]').length === 1")
        page.locator('[data-back-trace]').click()
        page.locator('[data-span="0000000000000004"]').click()
        page.locator('[data-tab="attributes"]').click()
        assert 'EVAL' in page.locator('#tx-node-body').inner_text()
        collapse_tree()
        page.wait_for_timeout(230)
        assert page.locator('[data-span]:visible').count() == 2  # root and orphan
        page.locator('#tx-tree-query').fill('redis')
        assert page.locator('[data-span]:visible').count() == 4  # matching node plus ancestors
        page.locator('#tx-tree-query').fill('')
        expand_tree()
        page.wait_for_timeout(230)
        page.locator('[data-span="0000000000000006"]').click()
        page.locator('[data-tab="links"]').click()
        page.locator('[data-related]').click()
        page.wait_for_function("document.querySelector('#tx-tree [data-span]') && document.querySelectorAll('#tx-tree [data-span]').length === 1")
        assert 'trace=' + OTHER in page.url
        page.locator('[data-back-trace]').click()
        page.locator('[data-related]').wait_for()
        assert 'trace=' + TRACE in page.url
        assert page.locator('[data-tab="links"]').get_attribute('aria-pressed') == 'true'
        assert 'retry inventory result' in page.locator('#tx-node-header').inner_text()
        page.locator('[data-related]').click()
        page.wait_for_function("document.querySelectorAll('#tx-tree [data-span]').length === 1")
        page.reload()
        page.locator('#tx-node-header h2').wait_for()
        assert 'trace=' + OTHER in page.url
        page.locator('[data-close]').click()
        assert 'trace=' not in page.url
        assert page.locator('#trace-detail').evaluate('el=>el.hidden')
        page.locator('#trace-detail').wait_for(state='hidden')
        page.locator('#tx-query').fill('name:missing')
        page.locator('#tx-query').press('Enter')
        page.wait_for_timeout(100)
        assert page.locator('[data-trace]').count() == 0
        page.locator('#tx-query').fill('')
        page.locator('#tx-query').press('Escape')
        page.locator('#tx-refresh').click()
        page.locator('[data-trace]').first.wait_for()
        page.locator('[data-trace] .tx-record-name').first.click()
        page.locator('#tx-node-header h2').wait_for()
        expand_tree()
        page.wait_for_timeout(230)
        out = Path(os.getenv('TEMP', '.')) / 'seckill-trace-desktop.png'
        page.screenshot(path=str(out))
        print('Desktop screenshot:', out)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.locator('#trace-detail').evaluate('(el)=>el.getBoundingClientRect().width') == 390
        assert page.locator('#workspace-traces .tx-node-detail').evaluate('(el)=>el.scrollWidth <= el.clientWidth')
        page.screenshot(path=str(out.with_name('seckill-trace-mobile.png')))
        page.locator('[data-span="0000000000000006"]').click()
        page.locator('[data-tab="links"]').click()
        page.locator('[data-logs]').click()
        assert page.url.endswith('#logs')
        assert page.locator('#log-search input[name="trace_id"]').input_value() == TRACE
        page.locator('#tx-return-trace').click()
        page.locator('#tx-node-header h2').wait_for()
        assert page.url.endswith('#traces')
        assert page.locator('[data-tab="links"]').get_attribute('aria-pressed') == 'true'
        page.goto(BASE + '/#traces')
        page.locator('[data-trace]').first.wait_for()
        page.evaluate("() => { window.traceExplorer.open('c'.repeat(32)); }")
        page.wait_for_timeout(100)
        assert delayed
        page.evaluate("() => { window.traceExplorer.open('b'.repeat(32)); }")
        page.locator('#tx-node-header h2').wait_for()
        delayed.pop().fulfill(content_type='application/json', body=json.dumps({'trace_id': 'c' * 32, 'spans': SPANS}))
        page.wait_for_timeout(100)
        assert 'trace=' + OTHER in page.url
        assert page.locator('[data-span]:visible').count() == 1
        page.evaluate("() => { window.traceExplorer.open('d'.repeat(32)); }")
        page.locator('[data-retry]').wait_for()
        assert 'Tempo' in page.locator('#trace-detail').inner_text()
        page.locator('[data-close]').click()
        bulk = True
        page.set_viewport_size({'width': 1920, 'height': 1080})
        page.locator('#tx-refresh').click()
        page.wait_for_function("document.querySelectorAll('#trace-results [data-trace]').length === 45")
        assert page.locator('#workspace-traces .tx-table-scroll').first.evaluate('(el)=>el.scrollHeight > el.clientHeight')
        assert page.locator('#workspace-traces .tx-facets').first.evaluate('(el)=>el.scrollHeight > el.clientHeight')
        page.locator('#workspace-traces .tx-table-scroll').first.hover()
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(100)
        assert page.locator('#workspace-traces .tx-table-scroll').first.evaluate('(el)=>el.scrollTop') > 0
        assert page.evaluate('scrollY === 0 && document.documentElement.scrollHeight === innerHeight')
        page.locator('#workspace-traces .tx-table-scroll').first.evaluate('(el)=>el.scrollTop=0')
        page.screenshot(path=str(out.with_name('seckill-trace-list.png')))
        page.locator('#tx-time-button').click()
        page.wait_for_timeout(100)
        page.screenshot(path=str(out.with_name('seckill-trace-time-menu.png')))
        page.locator('#tx-time-button').click()
        page.locator('#tx-query').focus()
        page.wait_for_timeout(100)
        page.screenshot(path=str(out.with_name('seckill-trace-query-menu.png')))
        page.locator('#tx-query').press('Escape')
        page.locator('[data-trace] .tx-record-name').first.click()
        page.locator('#tx-node-header h2').wait_for()
        expand_tree()
        page.wait_for_timeout(230)
        assert page.locator('#tx-tree').evaluate('(el)=>el.scrollHeight > el.clientHeight')
        page.emulate_media(reduced_motion='reduce')
        collapse_tree()
        assert page.locator('[data-span]:visible').count() == 2
        assert page.locator('#workspace-traces .tx-tree-branch').first.evaluate('el=>getComputedStyle(el).transitionDuration') == '0s'
        assert not errors, errors
        print('PASS: equal control heights, transparent icon buttons, accessible labels/focus, valid Lucide symbols, layout, local scroll, centered white checkbox, official icons, 10 time presets, relative/custom calendar, query validation, filters and URL restore, saved views/storage failure, columns, animated tree/details/reduced motion, request navigation, related trace return, log return, responsive layout, stale response and backend failure; no browser errors')
        browser.close()


if __name__ == '__main__':
    main()
