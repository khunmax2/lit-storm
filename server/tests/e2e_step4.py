"""See the Trash, the test buttons and Usage on screen.

    LITSTORM_E2E_URL=http://localhost:5173 uv run python tests/e2e_step4.py <screenshot dir>

Needs the admin that e2e_walkthrough.py created. The model test button
makes one tiny real call to the default model (a fraction of a cent).
"""

import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

from e2e_walkthrough import ADMIN_EMAIL, ADMIN_PASSWORD, BASE


def main(out):
    os.makedirs(out, exist_ok=True)
    shot = lambda page, name: page.screenshot(path=os.path.join(out, f"{name}.png"), full_page=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="th-TH")
        page.goto(f"{BASE}/login")
        page.locator("input").nth(0).fill(ADMIN_EMAIL)
        page.locator("input").nth(1).fill(ADMIN_PASSWORD)
        page.get_by_role("button").last.click()
        page.wait_for_url(re.compile(r"/$"))

        # The Trash: delete a project, find it, restore it.
        name = f"จะลบทิ้ง {os.getpid()}"
        page.get_by_placeholder(re.compile("ทบทวน")).fill(name)
        page.get_by_role("button", name="โปรเจกต์ใหม่").click()
        page.get_by_role("link", name=re.compile(re.escape(name))).click()
        page.once("dialog", lambda d: d.accept())
        page.get_by_role("button", name="ลบโปรเจกต์").click()
        page.wait_for_url(re.compile(r"/$"))
        expect(page.get_by_role("link", name=re.compile(re.escape(name)))).to_have_count(0)
        page.get_by_role("link", name="ถังขยะ").click()
        row = page.locator("li", has_text=name)
        expect(row.get_by_text(re.compile("เหลือ (29|30) วัน"))).to_be_visible()
        shot(page, "s1-trash")
        row.get_by_role("button", name="กู้คืน").click()
        expect(page.get_by_text(name)).to_have_count(0)
        page.get_by_role("link", name="โปรเจกต์").first.click()
        expect(page.get_by_role("link", name=re.compile(re.escape(name)))).to_be_visible()

        # Test buttons.
        page.get_by_role("link", name="ดูแลระบบ").click()
        page.get_by_role("button", name="โมเดล").first.click()
        page.get_by_role("button", name="ทดสอบ").first.click()
        expect(page.get_by_text(re.compile(r"[✓✕] .* · [\d.]+s")).first).to_be_visible(timeout=60_000)
        shot(page, "s2-model-test")
        page.get_by_role("button", name="บริการค้นหา").first.click()
        page.get_by_role("button", name="ทดสอบ").first.click()
        expect(page.get_by_text(re.compile(r"[✓✕] .* · [\d.]+s")).first).to_be_visible(timeout=60_000)
        shot(page, "s3-search-test")

        # Usage.
        page.get_by_role("button", name="การใช้งาน").click()
        expect(page.get_by_text("Run ล่าสุด")).to_be_visible()
        expect(page.locator("table").first.get_by_text(ADMIN_EMAIL).first).to_be_visible()
        page.wait_for_timeout(500)
        shot(page, "s4-usage")
        print("step 4 walkthrough passed")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
