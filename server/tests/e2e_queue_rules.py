"""See the queue rules on screen: quota, a Run parked for a new model, retry.

    LITSTORM_E2E_URL=http://localhost:5173 uv run python tests/e2e_queue_rules.py <screenshot dir>

Needs the admin that e2e_walkthrough.py created, and no Worker running
(so the new Run stays queued). Costs nothing: no Run is executed.
"""

import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

import ui
from e2e_walkthrough import ADMIN_EMAIL, ADMIN_PASSWORD, BASE
from ui import csrf


def main(out):
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="th-TH")
        ui.login(page, BASE, ADMIN_EMAIL, ADMIN_PASSWORD)

        api = lambda method, path, **kw: page.request.fetch(
            f"{BASE}{path}", method=method, headers={"X-CSRF-Token": csrf(page)}, **kw
        )
        models = api("GET", "/api/admin/llm-models").json()
        default = next(m for m in models if m["is_default"])
        other = next((m for m in models if m["label"] == "Spare model"), None) or api(
            "POST", "/api/admin/llm-models",
            data={"label": "Spare model", "provider": "openrouter", "model": "a/spare"},
        ).json()
        limits = api("GET", "/api/admin/limits").json()
        api("PUT", "/api/admin/limits", data={**limits, "monthly_run_quota": 5})

        # A queued Run, then its model is turned off.
        session = api(
            "POST", "/api/sessions", data={"topic": "ทดสอบการเลือกโมเดลใหม่", "language": "th"}
        ).json()
        api("PUT", f"/api/admin/llm-models/{other['id']}", data={**other, "is_default": True, "enabled": True})
        api("PUT", f"/api/admin/llm-models/{default['id']}", data={**default, "enabled": False, "is_default": False})

        page.goto(f"{BASE}/sessions/{session['id']}")
        queue_again = page.get_by_role("button", name="เข้าคิวอีกครั้ง")
        expect(queue_again).to_be_visible()
        expect(page.get_by_text(re.compile("เหลือ \\d+ จาก 5 รอบ")).first).to_be_visible()
        page.screenshot(path=os.path.join(out, "q1-needs-selection.png"), full_page=True)

        queue_again.click()
        expect(page.get_by_text("รอคิว").first).to_be_visible()
        page.screenshot(path=os.path.join(out, "q2-queued-again.png"), full_page=True)

        # Cancel it, then try again: a new Run linked to the old one.
        ui.cancel_latest(page)
        page.get_by_role("button", name="ลองใหม่").first.click()
        expect(page.get_by_text("ลองใหม่จากรอบก่อน")).to_be_visible()
        page.screenshot(path=os.path.join(out, "q3-retried.png"), full_page=True)

        page.goto(f"{BASE}/settings/users")
        page.locator("tbody tr").first.get_by_role("button").last.click()
        page.get_by_role("menuitem", name=re.compile("ขีดจำกัดของผู้ใช้นี้")).click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.screenshot(path=os.path.join(out, "q4-admin-quota.png"), full_page=True)

        # Put the settings back for the next walkthrough.
        api("PUT", f"/api/admin/llm-models/{default['id']}", data={**default, "enabled": True, "is_default": True})
        api("PUT", "/api/admin/limits", data=limits)
        print("queue rules walkthrough passed")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
