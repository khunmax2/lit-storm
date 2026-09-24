"""Screenshots of every page, light and dark, for reviewing the design.

    LITSTORM_E2E_URL=http://localhost:5173 uv run python tests/e2e_screens.py <dir>

Signs in as the admin e2e_walkthrough.py created; changes nothing.
"""

import os
import re
import sys

from playwright.sync_api import sync_playwright

from e2e_walkthrough import ADMIN_EMAIL, ADMIN_PASSWORD, BASE


def main(out):
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="th-TH", color_scheme=scheme)
            shot = lambda name, full=False: page.screenshot(path=os.path.join(out, f"{scheme}-{name}.png"), full_page=full)
            page.goto(f"{BASE}/login")
            page.wait_for_timeout(600)
            shot("00-login")
            page.locator("#email").fill(ADMIN_EMAIL)
            page.locator("#password").fill(ADMIN_PASSWORD)
            page.get_by_role("button", name=re.compile("เข้าสู่ระบบ|Sign in")).click()
            page.wait_for_url(re.compile(r"/$"))
            page.wait_for_timeout(1200)
            shot("01-home")
            page.goto(f"{BASE}/projects")
            page.wait_for_timeout(900)
            shot("02-projects")
            page.locator("a[href^='/projects/']").first.click()
            page.wait_for_timeout(1200)
            shot("03-project", full=True)
            # A topic that has a finished report.
            page.goto(f"{BASE}/")
            page.wait_for_timeout(800)
            done = page.locator("a[href^='/sessions/']").filter(has_text=re.compile("เสร็จแล้ว|Done")).first
            done.click()
            page.wait_for_timeout(1200)
            shot("04-session", full=True)
            page.get_by_role("link", name=re.compile("อ่านรายงาน|Read report")).first.click()
            page.wait_for_timeout(1500)
            shot("05-report")
            page.locator("button.cite").first.click()
            page.wait_for_timeout(700)
            shot("06-citation")
            page.keyboard.press("Escape")
            page.goto(f"{BASE}/trash")
            page.wait_for_timeout(800)
            shot("07-trash")
            page.goto(f"{BASE}/admin")
            page.wait_for_timeout(1000)
            shot("08-admin-users")
            page.get_by_role("tab", name=re.compile("โมเดล|Models")).click()
            page.wait_for_timeout(800)
            shot("09-admin-models", full=True)
            page.get_by_role("tab", name=re.compile("การใช้งาน|Usage")).click()
            page.wait_for_timeout(1000)
            shot("10-admin-usage", full=True)
            if scheme == "light":
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"{BASE}/")
                page.wait_for_timeout(1000)
                shot("11-mobile-home")
            page.close()
        browser.close()
    print("screens saved")


if __name__ == "__main__":
    main(sys.argv[1])
