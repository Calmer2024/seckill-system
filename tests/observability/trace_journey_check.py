"""Real Orders table/panel checks and paging/failure fixtures. No writes."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright
from trace_ui_check import SPANS, OTHER, START

BASE='http://127.0.0.1:8100'
OLD_ORDER='364761032851329024'


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1920,'height':1080})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/?trace_range=7d&trace_view=orders#traces')
        page.locator('#tx-order-results [data-order]').first.wait_for()
        assert page.get_by_role('button',name='Orders',exact=True).get_attribute('aria-pressed')=='true'
        assert page.locator('#tx-orders-layout .tx-table-scroll').evaluate("e=>getComputedStyle(e).overflowY")=='auto'
        assert page.evaluate('document.scrollingElement.scrollHeight <= innerHeight + 2')
        newest=page.locator('#tx-order-results [data-order]').first.get_attribute('data-order')
        page.locator('#tx-order-results [data-order] .tx-record-name').first.click()
        page.locator('#tx-order-node-header h2').wait_for()
        assert page.locator('#tx-order-detail .tx-detail-grid').evaluate("e=>getComputedStyle(e).display")=='grid'
        assert page.locator('#tx-order-detail .tx-node-detail').evaluate("e=>getComputedStyle(e).overflowY")=='auto'
        actual_navigation=False
        if page.locator('#tx-order-tree [data-order-node^="trace:"]').count():
            key=page.locator('#tx-order-tree [data-order-node^="trace:"]').first.get_attribute('data-order-node')
            page.locator(f'[data-order-fold="{key}"]').click()
            page.locator('#tx-order-tree [data-order-node^="span:"]').first.click()
            span_id=page.locator('[data-order-trace]').get_attribute('data-order-span')
            page.locator('[data-order-trace]').click()
            page.locator('#tx-node-header h2').wait_for()
            assert parse_qs(urlparse(page.url).query)['span']==[span_id]
            page.locator('#trace-detail [data-fold][aria-expanded=true]').first.click()
            assert page.locator('#tx-order-tree [data-order-fold="order"]').get_attribute('aria-expanded')=='true'
            assert page.locator('#tx-order-tree .is-selected').count()==1
            page.locator('[data-return-order]').click()
            page.locator('#trace-detail').wait_for(state='hidden')
            assert page.locator('#tx-order-detail').is_visible()
            actual_navigation=True
        screenshot=Path(os.environ['TEMP'])/'seckill-orders-panel.png'
        page.screenshot(path=str(screenshot))
        page.locator('[data-order-close]').click()
        page.locator('#tx-order-id').fill(OLD_ORDER)
        page.locator('#tx-order-search').evaluate('e=>e.requestSubmit()')
        page.locator(f'#tx-order-results [data-order="{OLD_ORDER}"]').wait_for()
        assert page.locator('#tx-order-results [data-order]').count()==1
        page.locator('#tx-order-results [data-order] .tx-record-name').click()
        page.locator('#tx-order-node-body').get_by_text('PAID',exact=True).wait_for()
        page.reload()
        page.locator('#tx-order-node-body').get_by_text('PAID',exact=True).wait_for()
        assert page.locator('#tx-order-id').input_value()==OLD_ORDER
        page.locator('[data-order-close]').click()
        page.locator('#tx-order-clear').click()
        page.locator('#tx-order-id').fill('product_id:899999999')
        page.locator('#tx-order-id').press('Enter')
        page.locator('#tx-order-results').get_by_text('没有匹配的订单').wait_for()
        page.locator('#tx-order-clear').click()
        page.locator('#tx-order-results [data-order]').first.wait_for()
        page.set_viewport_size({'width':390,'height':844})
        assert page.locator('[data-workspace-view=orders]').is_visible()
        page.set_viewport_size({'width':1920,'height':1080})
        page.locator('[data-workspace-view=traces]').click()
        page.locator('#trace-results [data-trace]').first.wait_for()
        assert page.locator('#tx-orders-layout').is_hidden()

        mode=['normal']
        def fixture(route):
            parsed=urlparse(route.request.url)
            if parsed.path.endswith('/orders'):
                if mode[0]=='failure':
                    route.fulfill(status=503,body='{}');return
                before=parse_qs(parsed.query).get('before')
                ids=[950] if before else list(range(1000,950,-1))
                route.fulfill(content_type='application/json',body=json.dumps({'orders':[{'order_id':str(i),'product_id':'4','quantity':1,'status':'PAID','created_at':'2026-10-08T01:00:00Z','updated_at':'2026-10-08T01:00:01Z'} for i in ids],
                    'limit':50,'has_more':not before,'next_cursor':None if before else '951','sampled_at':START/1e9}))
            elif parsed.path.endswith('/lifecycle'):
                route.fulfill(content_type='application/json',body=json.dumps({'trace_count':1,'sampling_note':'sampled',
                    'business_evidence':{'availability':'available','found':True,'sampled_at':START/1e9,'order':{'order_id':'1000','status':'PAID'},'outbox':[]},
                    'timeline':[{'trace_id':OTHER,'span_id':SPANS[1]['span_id'],'time_ns':str(START),'name':'payment.apply_result','service':'order-worker','duration_ms':10,'state':'PAID'}]}))
            elif parsed.path.endswith('/'+OTHER):
                route.fulfill(content_type='application/json',body=json.dumps({'trace_id':OTHER,'spans':SPANS,'summary':{'business':{'order_id':'1000'}}}))
            else: route.continue_()
        page.route('**/api/observability/**',fixture)
        page.goto(BASE+'/?trace_range=7d&trace_view=orders#traces')
        page.locator('#tx-order-results [data-order="1000"]').wait_for()
        page.locator('#tx-order-next').click()
        page.locator('#tx-order-results [data-order="950"]').wait_for()
        assert page.locator('#tx-order-next').is_disabled()
        page.locator('#tx-order-prev').click()
        page.locator('#tx-order-results [data-order="1000"] .tx-record-name').click()
        page.locator('#tx-order-node-header h2').wait_for()
        page.locator('#tx-order-tree [data-order-fold^="trace:"]').click()
        assert page.locator('#tx-order-tree .tx-tree-branch').first.evaluate("e=>getComputedStyle(e).transitionDuration.includes('0.18s')")
        page.locator('#tx-order-tree [data-order-node^="span:"]').click()
        page.locator('[data-order-trace]').click()
        page.locator('#tx-node-header h2').wait_for()
        assert parse_qs(urlparse(page.url).query)['span']==[SPANS[1]['span_id']]
        page.keyboard.press('Escape')
        assert page.locator('#tx-order-detail').is_visible()
        assert page.locator('#tx-order-node-header').get_by_text('payment.apply_result').is_visible()
        page.locator('[data-order-close]').click()
        mode[0]='failure'
        page.locator('#tx-refresh').click()
        page.locator('[data-order-retry]').wait_for()
        mode[0]='normal'
        page.locator('[data-order-retry]').click()
        page.locator('#tx-order-results [data-order="1000"]').wait_for()
        assert not errors,errors
        report={'passed':True,'real_orders_table':True,'real_database_state':'PAID','real_cross_trace_span_navigation':actual_navigation,
                'newest_order_id':newest,'paging_and_failure_fixtures':True,'filters_and_url_restore':True,
                'shared_panel_layout':True,'local_scroll':True,'mobile_tabs':True,'data_modified':False,'screenshot':str(screenshot)}
        output=Path(__file__).resolve().parents[2]/'docs/observability/trace-journey-validation.json'
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__=='__main__':main()
