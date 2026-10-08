"""Read-only checks for copy feedback and per-execution waterfall controls."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.getenv('TRACE_UI_URL', 'http://127.0.0.1:8100')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width':1920,'height':1080}, permissions=['clipboard-read','clipboard-write'])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(BASE+'/?trace_range=7d&trace_view=orders#traces', wait_until='networkidle')
        row = page.locator('#tx-order-results [data-order]').first
        row.wait_for()
        order_id = row.get_attribute('data-order')
        assert row.locator('[data-value-copy]').count() == 1
        assert row.locator('td').nth(1).locator('[data-value-copy]').get_attribute('aria-label') == '复制 Order ID'
        # Copying a table cell must not open the row's detail panel.
        copy_button = row.locator('td').nth(1).locator('[data-value-copy]')
        copy_button.click()
        page.wait_for_function("document.querySelector('#ui-copy-feedback').textContent.includes('已复制')")
        assert page.evaluate('navigator.clipboard.readText()') == order_id
        assert page.locator('#tx-order-detail').is_hidden()
        assert copy_button.get_attribute('aria-label') == '已复制'
        assert copy_button.locator('use').get_attribute('href') == '/icons.svg#check'
        row.locator('.tx-record-name').click()
        page.locator('#tx-order-node-header h2').wait_for()
        page.locator('[data-order-view=waterfall]').click()
        assert page.locator('[data-order-expand],[data-order-collapse],[data-expand-all],[data-collapse-all]').count() == 0
        while page.locator('[data-order-fold^="trace:"][aria-expanded=false]').count():
            page.locator('[data-order-fold^="trace:"][aria-expanded=false]').first.click()
        page.wait_for_timeout(220)
        assert page.locator('.order-wf-axis').count() == page.locator('.order-wf-execution').count()
        assert page.locator('.order-wf-run:visible').count() > 3
        page.locator('[data-order-zoom="1"]').first.click()
        assert page.locator('.order-wf-canvas').first.get_attribute('style') == 'width:200%'
        page.locator('[data-order-zoom="0"]').first.click()
        assert page.locator('.order-wf-canvas').first.get_attribute('style') == 'width:100%'
        node = page.locator('.order-wf-node').first
        node.click()
        assert page.locator('#tx-order-node-header h2').is_visible()
        for label in ['服务','类型','开始时间','耗时','原始 Span 状态','步骤业务状态','步骤执行结果']:
            assert page.locator('#tx-order-node-body .tx-fields div').filter(has=page.get_by_text(label,exact=True)).locator('[data-value-copy]').count() == 0
        assert page.locator('#tx-order-node-body .tx-fields div').filter(has=page.get_by_text('Trace ID',exact=True)).locator('[data-value-copy]').count() == 1
        page.locator('[data-order-tab=attributes]').click()
        assert page.locator('#tx-order-node-body pre [data-value-copy]').count() == 0
        page.locator('[data-order-tab=overview]').click()
        page.screenshot(path=str(Path(os.environ['TEMP'])/'order-waterfall-copy.png'))
        # Clipboard denial exposes selectable original text and permits retry.
        button = page.locator('#tx-order-node-body [data-value-copy]').first
        expected = button.locator('..').evaluate("el=>{const c=el.cloneNode(true);c.querySelectorAll('[data-value-copy]').forEach(b=>b.remove());return c.textContent.trim()}")
        page.evaluate("() => {window.originalClipboardWrite=navigator.clipboard.writeText.bind(navigator.clipboard);navigator.clipboard.writeText=()=>Promise.reject(new Error('denied'));}")
        button.click()
        manual = page.locator('#ui-copy-feedback textarea')
        manual.wait_for()
        assert manual.input_value() == expected
        assert manual.evaluate('el=>el.selectionEnd-el.selectionStart') == len(expected)
        assert button.get_attribute('data-copy-state') == 'error'
        page.evaluate('() => {navigator.clipboard.writeText=window.originalClipboardWrite;}')
        button.click()
        page.wait_for_function("document.querySelector('#ui-copy-feedback').textContent==='已复制到剪贴板'")
        assert page.evaluate('navigator.clipboard.readText()') == expected
        page.wait_for_timeout(2300)
        page.locator('#ui-copy-feedback').wait_for(state='hidden')
        assert button.get_attribute('data-copy-state') is None
        assert button.locator('use').get_attribute('href') == '/icons.svg#copy'
        page.goto(BASE+'/#runs',wait_until='networkidle')
        page.locator('#runs-body [data-select-run]').first.click()
        page.locator('#run-context-id [data-value-copy]').wait_for()
        assert page.locator('#run-context-id [data-value-copy]').count() == 1
        assert page.locator('#run-context-scenario [data-value-copy]').count() == 0
        assert page.locator('.ui-run-detail .metric-card [data-value-copy]').count() == 0
        assert not errors, errors
        print(json.dumps({'passed':True,'table_copy_without_navigation':True,'clipboard_readback':True,'success_feedback':True,'failure_manual_copy_and_retry':True,'per_trace_waterfall_axes':True,'zoom_reset':True,'bulk_controls_removed':True,'data_modified':False}))
        browser.close()


if __name__ == '__main__': main()
