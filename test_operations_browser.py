"""Browser acceptance checks for the synthetic-only Operations page."""
import os, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).parent
BASE = os.environ.get('TCS_OPS_URL','http://127.0.0.1:8878').rstrip('/')
class OperationsBrowser(unittest.TestCase):
    def test_demo_layout_metrics_navigation_and_no_live_requests(self):
        self.assertTrue((ROOT/'operations.html').exists(), 'Operations page not implemented')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1050})
            errors=[]; requests=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            page.on('request',lambda r: requests.append(r.url))
            page.goto(BASE+'/operations.html'); page.locator('#ops-content').wait_for(state='visible')
            self.assertIn('EXAMPLE DATA ONLY',page.inner_text('body'))
            self.assertEqual(page.locator('#live-programs tbody tr').count(),5)
            atlas=page.locator('[data-program="atlas"]')
            self.assertIn('180',atlas.inner_text()); self.assertIn('300',atlas.inner_text()); self.assertIn('Behind',atlas.inner_text())
            self.assertIn('Data unavailable',page.locator('[data-program="cedar"]').inner_text())
            self.assertIn('No target',page.locator('[data-program="harbor"]').inner_text())
            self.assertEqual(page.locator('.ops-controls, .ops-kpis').count(),0)
            self.assertEqual(page.locator('#buyer-filter, #platform-filter, #phase-filter, #search-filter, #reset-filters').count(),0)
            self.assertEqual(page.locator('#upcoming-launches .ops-launch').count(),2)
            self.assertEqual(page.locator('#prospects .ops-prospect').count(),1)
            page.locator('[data-program="atlas"] summary').click()
            self.assertIn('225',page.locator('[data-program="atlas"] details').inner_text())
            page.locator('[data-program="atlas"] summary').click()
            page.screenshot(path=os.environ.get('TCS_OPS_SCREENSHOT','/tmp/tcs-operations-demo.png'),full_page=True)
            self.assertIn('Volume coverage 3/3 · Commitment coverage 3/3',page.locator('#buyer-health').inner_text())
            self.assertLess(page.locator('#buyer-health').bounding_box()['y'],page.locator('#needs-attention').bounding_box()['y'])
            page.set_viewport_size({'width':390,'height':844})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'))
            allowed=('operations.html','operations-demo.json','operations.js','operations-model.js','operations.css','styles.css','assets/logo.png')
            allowed_urls={BASE+'/'+path for path in allowed}
            self.assertTrue(all(r.split('?')[0] in allowed_urls for r in requests),requests)
            self.assertFalse(errors,errors)
            page.route('**/data.json*',lambda r:r.abort())  # Never load financial records for a nav test.
            page.goto(BASE+'/index.html')
            self.assertEqual(page.locator('a[href="operations.html"]').count(),1)
            page.locator('a[href="operations.html"]').click()
            page.locator('#ops-content').wait_for(state='visible')
            self.assertTrue(page.url.endswith('/operations.html'))
            browser.close()
    def test_missing_fixture_fails_closed(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True); page=browser.new_page()
            page.route('**/operations-demo.json*',lambda r:r.fulfill(status=503,body='unavailable'))
            page.goto(BASE+'/operations.html')
            page.get_by_text('Example scenario unavailable',exact=False).wait_for()
            self.assertFalse(page.locator('#ops-content').is_visible())
            browser.close()
if __name__=='__main__': unittest.main()
