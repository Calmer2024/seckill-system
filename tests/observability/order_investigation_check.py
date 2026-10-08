"""Read-only live validation of complete order trees and same-panel navigation."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BASE = os.getenv('TRACE_UI_URL', 'http://127.0.0.1:8100')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        orders = page.request.get(BASE+'/api/observability/orders?window=7d').json()['orders']
        order_id = orders[0]['order_id']
        data = page.request.get(BASE+'/api/observability/traces/lifecycle?window=7d&order_id='+order_id).json()
        assert data['executions']
        starts = [int(e['start_time_ns']) for e in data['executions']]
        assert starts == sorted(starts)
        count = sum(len(e['spans']) for e in data['executions'])
        assert count > len(data['timeline'])
        page.goto(BASE+'/?trace_range=7d&trace_view=orders#traces', wait_until='networkidle')
        page.locator(f'[data-order="{order_id}"]').click()
        page.locator('#tx-order-node-header h2').wait_for()
        assert page.locator('#tx-order-tree .order-sequence').all_text_contents() == [str(i+1) for i in range(len(data['executions']))]
        assert page.locator('[data-order-expand],[data-order-collapse]').count()==0
        for button in page.locator('[data-order-fold^="trace:"]').all(): button.click()
        page.wait_for_timeout(220)
        assert page.locator('#tx-order-tree [data-order-node^="span:"]').count() == count
        db = page.locator('#tx-order-tree .tx-node-select:has(.tx-kind-db)').first
        db.click()
        key = db.get_attribute('data-order-node')
        assert page.locator('#trace-detail').is_hidden()
        page.locator('[data-order-tab=input]').click()
        assert 'db.system' in page.locator('#tx-order-node-body').inner_text()
        assert parse_qs(urlparse(page.url).query)['order_node'] == [key]
        page.reload(wait_until='networkidle')
        page.locator('#tx-order-node-body').get_by_text('db.system', exact=True).wait_for()
        assert page.locator('#tx-order-tree [aria-pressed=true][data-order-node]').get_attribute('data-order-node') == key
        page.locator('[data-order-view=waterfall]').click()
        assert page.locator('.order-wf-run').count() == count
        assert page.locator('.order-wf-execution').count()==len(data['executions'])
        page.locator('[data-order-zoom="1"]').first.click()
        assert page.locator('.order-wf-canvas').first.get_attribute('style')=='width:200%'
        page.locator('[data-order-zoom="0"]').first.click()
        assert page.locator('.order-wf-bar').count() > 0
        page.reload(wait_until='networkidle')
        page.locator('.order-wf-execution').first.wait_for()
        assert page.locator('[data-order-view=waterfall]').get_attribute('aria-pressed') == 'true'
        page.locator('[data-order-view=tree]').click()
        page.locator('[data-order-tab=overview]').click()
        screenshot = Path(os.environ['TEMP'])/'order-investigation-final.png'
        page.screenshot(path=str(screenshot))
        page.locator('[data-order-logs]').click()
        page.locator('#workspace-logs').wait_for(state='visible')
        page.locator('#tx-return-order').click()
        page.locator('#tx-order-node-header h2').wait_for()
        assert page.locator('#tx-order-tree [aria-pressed=true][data-order-node]').get_attribute('data-order-node') == key
        page.set_viewport_size({'width':390, 'height':844})
        assert not page.evaluate('document.documentElement.scrollHeight > innerHeight')
        assert page.locator('#tx-order-node-body').is_visible()
        assert page.locator('#tx-order-tree').is_visible()
        # Parent cycles must become visible roots, and shared-order context remains distinct.
        graph = page.evaluate("""() => {
          const payload={executions:[{trace_id:'fixture',start_time_ns:'1',spans:[
            {span_id:'a',parent_span_id:'b',name:'a',start_time_ns:'1',attributes:{},identifier_match:false},
            {span_id:'b',parent_span_id:'a',name:'b',start_time_ns:'2',attributes:{},identifier_match:true}]}]};
          const nodes=orderInvestigation.build(payload);
          return {count:orderInvestigation.flat(nodes).length,html:orderInvestigation.tree(nodes,'order',new Set(),'','tree')};
        }""")
        assert graph['count'] == 4
        assert 'order-context' in graph['html']
        assert '父节点缺失或关系异常' in graph['html']
        page.set_viewport_size({'width':1920,'height':1080})
        # Explicit fixture: follow an actual-shape Span Link across executions in the same panel.
        fixture = json.loads(json.dumps(data))
        source_trace, source_span = key.split(':')[1:]
        target = next(e for e in fixture['executions'] if e['trace_id'] != source_trace)
        target_span = target['spans'][0]
        source = next(s for e in fixture['executions'] if e['trace_id']==source_trace for s in e['spans'] if s['span_id']==source_span)
        source['links']=[{'trace_id':target['trace_id'],'span_id':target_span['span_id'],'reason':'fixture message correlation'}]
        page.route('**/api/observability/traces/lifecycle?**',lambda route:route.fulfill(content_type='application/json',body=json.dumps(fixture)))
        page.reload(wait_until='networkidle')
        page.locator('[data-order-tab=links]').click()
        page.locator('[data-order-link]').click()
        assert page.locator('#trace-detail').is_hidden()
        assert parse_qs(urlparse(page.url).query)['order_node']==['span:'+target['trace_id']+':'+target_span['span_id']]
        page.unroute('**/api/observability/traces/lifecycle?**')
        assert not errors, errors
        result={'passed':True,'loaded_spans':count,'order_matching_spans':len(data['timeline']),
                'complete_parent_tree':True,'same_panel_database_detail':True,'node_url_restore':True,
                'aligned_waterfall':True,'cycle_and_context_handling':True,'mobile_local_scroll':True,
                'logs_return':True,'cross_execution_link_fixture':True,'data_modified':False}
        Path('docs/observability/order-investigation-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
        browser.close()


if __name__ == '__main__':
    main()
