"""Browser regression for the limited recovery release; run with a served base URL."""
import json, os, unittest
from playwright.sync_api import sync_playwright

class ReleaseRenderTest(unittest.TestCase):
    def test_financial_snapshot_is_explicitly_not_current(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1080})
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(os.environ.get('TCS_TEST_URL','http://127.0.0.1:8876/'),wait_until='networkidle')
            headings=page.locator('h3').all_text_contents()
            self.assertEqual(headings[0].strip(),'Company Tort priorities')
            self.assertEqual(headings[-1].strip(),'Needs Attention')
            notice=page.locator('#financial-repair-notice')
            self.assertEqual(notice.count(),1,'Missing prominent financial repair warning')
            self.assertIn('not current financials',notice.inner_text())
            self.assertIn('underlying sources may be older',notice.inner_text())
            self.assertNotIn('auto-refresh hourly (LP/BP/Meta/SR)', page.locator('#footer').inner_text())
            self.assertFalse(errors,errors)
            page.screenshot(path=os.environ.get('TCS_SCREENSHOT','/tmp/tcs-recovery-local.png'),full_page=True)
            print(json.dumps({'headings':headings,'errors':errors,'warning':notice.inner_text()}))
            browser.close()

if __name__=='__main__': unittest.main()
