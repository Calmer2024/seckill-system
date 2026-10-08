"""Read-only browser checks for motion lifecycle, interruption, and accessibility."""
import os
from playwright.sync_api import sync_playwright

BASE = os.getenv('TRACE_UI_URL', 'http://127.0.0.1:8100')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 960})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/?trace_range=7d#traces', wait_until='networkidle')
        row = page.locator('#trace-results [data-trace]').first
        row.wait_for()
        # Real controls: menus animate both directions, while semantic state changes immediately.
        page.locator('#tx-time-button').click()
        menu = page.locator('#tx-time-menu')
        menu.wait_for(state='visible')
        assert float(menu.evaluate('el=>parseFloat(getComputedStyle(el).transitionDuration)')) > 0
        page.wait_for_timeout(230)
        close_state = page.evaluate("""async () => {
          document.querySelector('#tx-time-button').click();
          await new Promise(requestAnimationFrame);
          const menu=document.querySelector('#tx-time-menu');
          return {hidden:menu.hidden, pointer:getComputedStyle(menu).pointerEvents,
            expanded:document.querySelector('#tx-time-button').getAttribute('aria-expanded'),
            animating:menu.getAnimations().length>0};
        }""")
        assert close_state == {'hidden': True, 'pointer': 'none', 'expanded': 'false', 'animating': True}, close_state
        menu.wait_for(state='hidden')
        row.locator('.tx-record-name').click()
        page.locator('#tx-node-header h2').wait_for()
        drawer = page.locator('#trace-detail')
        page.wait_for_timeout(250)
        # Changing an explicit tab gets a bounded content animation.
        page.locator('[data-tab=attributes]').click()
        page.wait_for_function("document.querySelector('#tx-node-body').getAnimations().length>0")
        page.wait_for_timeout(200)
        assert page.locator('#tx-node-body').evaluate('el=>el.getAnimations().length') == 0
        # Closing clears URL and interaction before the visual exit completes.
        state = page.evaluate("""async () => {
          document.querySelector('#trace-detail [data-close]').click();
          await new Promise(requestAnimationFrame);
          const el=document.querySelector('#trace-detail');
          return {hidden:el.hidden,pointer:getComputedStyle(el).pointerEvents,
            cleared:!new URL(location.href).searchParams.has('trace'),animating:el.getAnimations().length>0};
        }""")
        assert state == {'hidden': True, 'pointer': 'none', 'cleared': True, 'animating': True}, state
        # Reopening during exit reverses it without a ghost overlay or stale hidden state.
        row.locator('.tx-record-name').evaluate('el=>el.click()')
        page.locator('#tx-node-header h2').wait_for()
        page.wait_for_timeout(260)
        assert drawer.evaluate("el=>!el.hidden&&getComputedStyle(el).opacity==='1'&&getComputedStyle(el).transform==='matrix(1, 0, 0, 1, 0, 0)'")
        page.emulate_media(reduced_motion='reduce')
        assert drawer.evaluate('el=>getComputedStyle(el).transitionDuration') == '0s'
        page.locator('[data-tab=input]').click()
        page.wait_for_timeout(35)
        assert page.locator('#tx-node-body').evaluate('el=>el.getAnimations().length') == 0
        page.locator('#trace-detail [data-close]').click()
        assert drawer.evaluate('el=>el.hidden&&getComputedStyle(el).display==="none"')
        page.locator('#tx-time-button').click()
        assert menu.evaluate('el=>el.getAnimations().length') == 0
        assert not errors, errors
        browser.close()
        print('PASS: menu/drawer entry and exit, immediate semantic dismissal, tab content motion, rapid reopen, reduced motion, no browser errors; no business writes')


if __name__ == '__main__':
    main()
