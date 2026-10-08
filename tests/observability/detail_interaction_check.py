"""Read-only real drawer dismissal, shared row geometry, and Lucide provenance checks."""
import json
import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BASE=os.getenv('TRACE_UI_URL','http://127.0.0.1:8100')

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1920,'height':1080})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        order=page.request.get(BASE+'/api/observability/orders?window=7d').json()['orders'][0]['order_id']
        execution=page.request.get(BASE+'/api/observability/traces/lifecycle?window=7d&order_id='+order).json()['executions'][0]
        sprite=ET.fromstring(page.request.get(BASE+'/icons.svg').text())
        assert sprite.get('data-icon-library')=='lucide'
        assert all(s.get('data-lucide') and s.get('viewBox')=='0 0 24 24' and s.get('fill')=='none' for s in sprite)
        def outside(pane):
            page.mouse.click(1200,25)
            page.locator(pane).wait_for(state='hidden')
        page.goto(BASE+'/?trace_range=7d&trace='+execution['trace_id']+'#traces',wait_until='domcontentloaded')
        page.locator('#tx-node-header h2').wait_for()
        page.locator('#tx-tree [data-span]').first.click()
        assert page.locator('#trace-detail').is_visible()
        outside('#trace-detail')
        assert 'trace' not in parse_qs(urlparse(page.url).query)
        page.goto(BASE+'/?trace_range=7d&trace_view=orders&trace_order='+order+'#traces',wait_until='domcontentloaded')
        page.locator('#tx-order-node-header h2').wait_for()
        summary=page.locator('#tx-order-detail .tx-summary>span').last
        geometry=summary.evaluate("el=>{const r=el.getBoundingClientRect(),g=el.querySelector('svg').getBoundingClientRect();return {width:g.width,height:g.height,offset:Math.abs(g.y+g.height/2-r.y-r.height/2),display:getComputedStyle(el).display}}")
        assert geometry['width']==geometry['height']==14 and geometry['offset']==0 and geometry['display'] in ['flex','inline-flex'],geometry
        page.locator('[data-order-view=waterfall]').click()
        page.locator('[data-order-fold^="trace:"]').first.click()
        node=page.locator('#tx-order-tree .order-wf-node:visible').first
        node.click()
        row=node.locator('..')
        assert row.evaluate("el=>getComputedStyle(el).backgroundColor")=='rgb(229, 244, 255)'
        assert row.locator('.order-wf-label strong').evaluate('el=>getComputedStyle(el).fontSize')==row.locator('.order-wf-label small').evaluate('el=>getComputedStyle(el).fontSize')=='12px'
        assert row.locator('.tx-kind svg').evaluate('el=>el.getBoundingClientRect().width')==16
        page.locator('[data-order-trace]').click()
        page.locator('#tx-node-header h2').wait_for()
        outside('#trace-detail')
        assert page.locator('#tx-order-detail').is_visible()
        outside('#tx-order-detail')
        assert 'trace_order' not in parse_qs(urlparse(page.url).query)
        page.goto(BASE+'/#runs',wait_until='domcontentloaded')
        page.locator('#runs-body [data-select-run]').first.click()
        page.locator('.ui-run-detail').wait_for(state='visible')
        outside('.ui-run-detail')
        assert 'run' not in parse_qs(urlparse(page.url).query)
        page.goto(BASE+'/#monitoring',wait_until='domcontentloaded')
        page.locator('#environment-charts [data-expand-chart]').first.click()
        page.locator('#ui-chart-detail').wait_for(state='visible')
        outside('#ui-chart-detail')
        assert 'monitor_chart' not in parse_qs(urlparse(page.url).query)
        # Explicit log fixture supplies a readable record without writing business data.
        page.route('**/api/observability/logs?**',lambda route:route.fulfill(content_type='application/json',body=json.dumps({'sampled_at':1791470000,'window_minutes':60,'limit':200,'logs':[{'timestamp_ns':'1791470000000000000','service':'order-api','instance':'fixture','fields':{'message':'dismissal fixture','level':'INFO'}}]})))
        page.goto(BASE+'/#logs',wait_until='domcontentloaded')
        page.locator('#log-results .tx-record-name').first.click()
        page.locator('#ui-log-detail').wait_for(state='visible')
        page.locator('#ui-log-detail .ui-sample-list .is-selected').wait_for()
        outside('#ui-log-detail')
        assert 'log_record' not in parse_qs(urlparse(page.url).query)
        assert not errors,errors
        print(json.dumps({'passed':True,'lucide_only':True,'row_alignment':True,'whole_row_selection':True,'outside_close_trace_orders_runs_charts_logs':True,'nested_drawer_close':True,'url_cleanup':True,'data_modified':False}))
        browser.close()

if __name__=='__main__':main()
