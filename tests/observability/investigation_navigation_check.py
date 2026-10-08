"""Read-only cross-workspace navigation with real Trace evidence and explicit log fixture."""
import json
import os
import time
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BASE=os.getenv('TRACE_UI_URL','http://127.0.0.1:8100')

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1920,'height':1080})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        orders=page.request.get(BASE+'/api/observability/orders?window=7d').json()['orders']
        order_id=orders[0]['order_id']
        lifecycle=page.request.get(BASE+'/api/observability/traces/lifecycle?window=7d&order_id='+order_id).json()
        execution=lifecycle['executions'][0]
        span=next(s for s in execution['spans'] if s['attributes'].get('seckill.order_id'))
        timestamp=span['start_time_ns']
        log={'timestamp_ns':timestamp,'service':span['service'],'instance':'navigation-fixture','fields':{'message':'Explicit navigation fixture','level':'INFO','trace_id':execution['trace_id'],'span_id':span['span_id'],'order_id':order_id,'event_id':'11111111-1111-4111-8111-111111111111','causation_id':'22222222-2222-4222-8222-222222222222'}}
        log_requests=[]
        def fixture(route):
            log_requests.append(parse_qs(urlparse(route.request.url).query))
            route.fulfill(content_type='application/json',body=json.dumps({'logs':[log],'sampled_at':int(time.time()),'window_minutes':60,'limit':200,'truncated':False}))
        page.route('**/api/observability/logs?**',fixture)
        page.goto(BASE+'/#logs',wait_until='networkidle')
        page.locator('[data-log-row] .tx-record-name').first.click()
        page.locator('#ui-log-detail [aria-label="查看关联订单"]').click()
        page.locator('#tx-order-node-header h2').wait_for()
        assert parse_qs(urlparse(page.url).query)['trace_order']==[order_id]
        page.locator('.ui-investigation-return button').click()
        page.locator('#ui-log-detail [aria-label="查看关联 Trace"]').wait_for()
        page.locator('#ui-log-detail [aria-label="查看关联 Trace"]').click()
        page.locator('#tx-node-header h2').wait_for()
        assert parse_qs(urlparse(page.url).query)['span']==[span['span_id']]
        page.locator('#tx-node-header [aria-label="查看关联订单"]').click()
        page.locator('#tx-order-node-header h2').wait_for()
        page.locator('.ui-investigation-return button').click()
        page.locator('#tx-node-header h2').wait_for()
        assert parse_qs(urlparse(page.url).query)['span']==[span['span_id']]
        page.locator('.ui-investigation-return button').click()
        page.locator('#ui-log-detail [aria-label="查看后续事件执行"]').wait_for()
        page.locator('#ui-log-detail [aria-label="查看后续事件执行"]').click()
        page.locator('#tx-query').wait_for()
        assert 'causation_id:' in page.locator('#tx-query').input_value()
        assert page.locator('#tx-query-scope').input_value()=='all'
        page.locator('.ui-investigation-return button').click()
        page.locator('#ui-log-detail [aria-label="查看来源事件执行"]').wait_for()
        assert not page.evaluate('document.documentElement.scrollHeight>innerHeight')
        page.goto(BASE+'/#runs',wait_until='networkidle')
        page.locator('#runs-body [data-select-run]').first.click()
        page.locator('#report-links [aria-label="运行时段 Traces"]').wait_for()
        source=page.url
        page.locator('#report-links [aria-label="运行时段 Traces"]').click()
        page.locator('#tx-query').wait_for()
        query=parse_qs(urlparse(page.url).query)
        assert query['trace_range']==['custom']
        start,end=query['trace_start'][0],query['trace_end'][0]
        assert int(end)>int(start)
        page.locator('.ui-investigation-return button').click()
        page.locator('#report-links [aria-label="运行时段日志"]').wait_for()
        page.locator('#report-links [aria-label="运行时段日志"]').click()
        page.locator('#log-results .tx-record-name').first.wait_for()
        assert log_requests[-1]['start']==[start] and log_requests[-1]['end']==[end]
        page.locator('.ui-investigation-return button').click()
        page.locator('#report-links [aria-label="运行时段监控"]').wait_for()
        page.locator('#report-links [aria-label="运行时段监控"]').click()
        page.locator('#environment-charts .signal-chart').first.wait_for()
        assert parse_qs(urlparse(page.url).query)['monitor_start']==[start]
        assert '历史指标证据' in page.locator('#metrics-message').inner_text()
        page.locator('#environment-charts [data-expand-chart]').first.click()
        page.locator('#ui-chart-detail [aria-label="查看此时段 Traces"]').click()
        page.locator('#tx-query').wait_for()
        assert parse_qs(urlparse(page.url).query)['trace_start']==[start]
        page.locator('.ui-investigation-return button').click()
        page.locator('#ui-chart-detail').wait_for(state='visible')
        assert not errors,errors
        print(json.dumps({'passed':True,'logs_order_trace_span_roundtrip':True,'event_causation_candidates':True,'run_time_ranges':True,'chart_time_range_and_return':True,'real_order_id':order_id,'log_fixture':True,'data_modified':False}))
        browser.close()

if __name__=='__main__':main()
