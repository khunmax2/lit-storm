"""See the Trash, the test buttons and Usage on screen.

    LITSTORM_E2E_URL=http://localhost:5173 uv run python tests/e2e_step4.py <screenshot dir>

Needs the admin that e2e_walkthrough.py created. The model test button
makes one tiny real call to the default model (a fraction of a cent).
"""

import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

import ui
from e2e_walkthrough import ADMIN_EMAIL, ADMIN_PASSWORD, BASE


def main(out):
    os.makedirs(out, exist_ok=True)
    shot = lambda page, name: page.screenshot(path=os.path.join(out, f"{name}.png"), full_page=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="th-TH")
        ui.login(page, BASE, ADMIN_EMAIL, ADMIN_PASSWORD)

        # The Trash: delete a project, find it, restore it.
        name = f"จะลบทิ้ง {os.getpid()}"
        project_id = ui.new_project(page, BASE, name)
        ui.delete_project(page, BASE, project_id)
        expect(page.get_by_role("link", name=re.compile(re.escape(name)))).to_have_count(0)
        row = ui.trash_row(page, BASE, name)
        expect(row.get_by_text(re.compile("เหลือ (29|30) วัน"))).to_be_visible()
        shot(page, "s1-trash")
        row.get_by_role("button", name="กู้คืน").click()
        expect(row).to_have_count(0)
        page.goto(f"{BASE}/projects")
        expect(page.get_by_role("link", name=re.compile(re.escape(name)))).to_be_visible()

        # Test buttons.
        page.goto(f"{BASE}/settings/models")
        ui.test_button_toast(page)
        shot(page, "s2-model-test")
        page.goto(f"{BASE}/settings/search")
        ui.test_button_toast(page)
        shot(page, "s3-search-test")

        # Usage.
        page.goto(f"{BASE}/settings/usage")
        expect(page.get_by_text("Run ล่าสุด")).to_be_visible()
        expect(page.locator("table").first.get_by_text(ADMIN_EMAIL).first).to_be_visible()
        page.wait_for_timeout(500)
        shot(page, "s4-usage")
        print("step 4 walkthrough passed")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
