"""Read-only browser checks of the real local observability workspaces."""
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

BASE = os.getenv('TRACE_UI_URL', 'http://127.0.0.1:8100')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def visit(name):
            page.goto(BASE + '/#' + name, wait_until='networkidle')
            assert not page.evaluate('document.documentElement.scrollHeight > innerHeight')
            if name in ['monitoring','logs','runs']:
                assert page.locator('#workspace-'+name+' .ui-section-header').count() == 0

        def select(id_, value):
            root = page.locator(id_).locator('..')
            root.locator('.select-trigger').click()
            root.locator('[data-value="' + value + '"]').click()

        visit('traces')
        page.locator('[data-trace]').first.wait_for()
        page.locator('[data-workspace-view="spans"]').click()
        page.locator('#tx-observed-view [data-related]').first.wait_for()
        assert page.locator('#workspace-traces .tx-facets').first.is_visible()
        page.locator('#tx-observed-view [data-related] .tx-record-name').first.click()
        page.locator('#tx-node-header h2').wait_for()
        page.locator('#trace-detail [data-close]').click()
        page.locator('[data-workspace-view="services"]').click()
        page.locator('#tx-observed-view [data-inspect-service]').first.click()
        page.locator('#tx-service-detail').wait_for(state='visible')
        page.locator('#tx-service-detail [data-related]').first.click()
        page.locator('#tx-node-header h2').wait_for()
        page.locator('#trace-detail [data-close]').click()
        assert page.locator('#tx-service-detail').is_visible()
        page.locator('#tx-service-detail [data-service-close]').click()

        visit('monitoring')
        page.locator('#environment-charts .signal-chart').first.wait_for()
        page.wait_for_function("document.querySelector('#metrics-message').textContent.includes('60')")
        page.locator('#ui-monitor-query').fill('http_rate')
        assert page.locator('#environment-charts .signal-chart').count() == 1
        page.locator('#ui-monitor-clear').click()
        select('#metrics-window select', '10080')
        page.wait_for_function("document.querySelector('#metrics-message').textContent.includes('10080')")
        page.locator('[data-chart-category="http"]').click()
        assert page.locator('#environment-charts .signal-chart').count() == 2
        select('#ui-chart-view', 'table')
        assert page.locator('#ui-metric-table').is_visible()
        page.locator('#ui-metric-table [data-expand-chart]').first.click()
        page.locator('#ui-chart-detail').wait_for(state='visible')
        assert page.locator('#ui-chart-detail .tx-detail-grid').count() == 1
        page.locator('#ui-chart-detail [data-ui-close]').click()
        page.reload(wait_until='networkidle')
        assert page.locator('#ui-chart-view').input_value() == 'table'
        assert page.locator('#metrics-window select').input_value() == '10080'
        page.locator('[data-monitor-tab="services"]').click()
        page.locator('#p0-service-status td').first.wait_for()
        assert page.locator('#p0-service-status').is_visible()
        page.locator('[data-monitor-tab="alerts"]').click()
        page.locator('#active-alerts table').wait_for()
        page.screenshot(path=os.path.join(os.environ['TEMP'], 'radix-monitor-alerts.png'))

        visit('logs')
        page.locator('#log-results [data-log-row]').first.wait_for()
        assert page.locator('#log-search').is_hidden()
        page.locator('#ui-log-query').fill('level:INFO')
        page.locator('#ui-log-query').press('Enter')
        page.wait_for_function("document.querySelector('#logs-message').textContent.includes('条') && [...document.querySelectorAll('#log-results .ui-log-level')].every(el=>el.textContent==='INFO')")
        page.locator('#log-results [data-log-row]').first.click()
        page.locator('#ui-log-detail').wait_for(state='visible')
        page.locator('#ui-log-detail summary').first.click()
        page.wait_for_timeout(230)
        assert page.locator('#ui-log-detail details').first.get_attribute('data-expanded') == 'false'
        page.screenshot(path=os.path.join(os.environ['TEMP'], 'radix-log-detail.png'))
        page.locator('#ui-log-detail [data-ui-close]').click()
        page.locator('#ui-log-query').fill('workspace-check-no-matching-log')
        page.locator('#ui-log-query').press('Enter')
        page.wait_for_function("document.querySelectorAll('#log-results [data-log-row]').length === 0")

        visit('runs')
        assert page.locator('#workspace-runs .list-toolbar').is_hidden()
        page.locator('#run-search').fill('status:completed')
        assert page.locator('#runs-body .status-completed').count() > 0
        assert page.locator('#runs-body .status-badge:not(.status-completed)').count() == 0
        page.locator('#ui-run-facets [data-run-facet=status][value=completed]').uncheck()
        assert 'status:' not in page.locator('#run-search').input_value()
        page.locator('#runs-body [data-select-run]').first.click()
        page.locator('.ui-run-detail').wait_for(state='visible')
        assert page.locator('.ui-run-detail .tx-detail-grid').count() == 1
        assert page.locator('.ui-run-detail .tx-chain').count()==0
        assert page.locator('.ui-run-header-context #run-context-id').is_visible()
        assert page.locator('.ui-run-detail .metric-grid').evaluate("el=>getComputedStyle(el).gridTemplateColumns.split(' ').length>1")
        page.locator('[data-detail-tab="run"]').click()
        assert page.locator('[data-detail-view="run"]').is_visible()
        page.screenshot(path=os.path.join(os.environ['TEMP'], 'radix-run-detail.png'))
        page.locator('#close-run-detail').click()
        page.locator('.ui-run-detail').wait_for(state='hidden')
        assert 'run=' not in page.url
        page.locator('#open-new-run').click()
        assert page.locator('#new-run-dialog').is_visible()
        page.locator('#close-new-run').click()
        assert not page.evaluate('document.documentElement.scrollHeight > innerHeight')

        page.locator('#current-location').click()
        page.wait_for_url('**/#runs')
        assert page.locator('.ui-run-detail').is_hidden()
        page.locator('.breadcrumb a').first.click()
        page.wait_for_url('**/#runs')
        visit('monitoring')
        page.locator('#environment-charts .signal-chart').first.wait_for()
        page.route('**/api/observability/metrics?**', lambda route: route.fulfill(status=503, body='{}'))
        page.locator('#metrics-window>button').click()
        page.wait_for_function("document.querySelectorAll('#environment-charts .signal-empty').length === 8")
        assert page.locator('#environment-charts svg[role=img]').count() == 0
        page.unroute('**/api/observability/metrics?**')
        page.route('**/api/observability/alerts', lambda route: route.fulfill(content_type='application/json', body=json.dumps({
            'sampled_at': 1791450000, 'alert_status': 'ok', 'notification_status': 'ok', 'notifications': [],
            'alerts': [{'labels': {'alertname': 'Fixture alert', 'service': 'order-api', 'severity': 'warning'},
                        'annotations': {'summary': 'Collection delayed'}, 'starts_at': '2026-10-08T12:00:00Z'}]})))
        page.locator('[data-monitor-tab="alerts"]').click()
        page.locator('#refresh-alerts').click()
        page.locator('[data-alert-row]').first.click()
        page.locator('#ui-alert-detail').wait_for(state='visible')
        page.locator('#ui-alert-detail [data-ui-close]').click()
        page.unroute('**/api/observability/alerts')
        page.route('**/api/observability/traces?**', lambda route: route.fulfill(status=503, body='{}'))
        visit('traces')
        page.locator('[data-workspace-view="spans"]').click()
        page.wait_for_function("document.querySelector('#tx-observed-note').textContent.includes('不可用')")
        assert page.locator('#tx-observed-view [data-related]').count() == 0
        page.unroute('**/api/observability/traces?**')

        sprite = ET.fromstring(page.request.get(BASE + '/icons.svg').text())
        assert sprite.get('data-icon-library') == 'lucide'
        assert all(node.get('viewBox') == '0 0 24 24' for node in sprite if node.tag.endswith('symbol'))
        page.set_viewport_size({'width': 390, 'height': 844})
        for name in ['monitoring', 'logs', 'runs']:
            visit(name)
            assert page.locator('#workspace-' + name).evaluate('el=>el.getBoundingClientRect().width <= innerWidth')
        assert not errors, errors
        result = {'passed': True, 'lucide': True, 'spans_services_drawers': True,
                  'real_monitoring_charts_and_table': True, 'time_and_url_restore': True,
                  'logs_table_and_drawer': True, 'runs_table_and_drawer': True,
                  'local_scroll': True, 'mobile_layout': True, 'failure_and_alert_fixtures': True, 'data_modified': False}
        (Path(__file__).resolve().parents[2] / 'docs/observability/workspace-unified-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
        browser.close()


if __name__ == '__main__':
    main()
