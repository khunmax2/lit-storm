"""Walk the whole first-release path through the web UI, with screenshots.

    LITSTORM_E2E_URL=http://localhost:5173 LITSTORM_E2E_SETUP_CODE=... \
    LITSTORM_E2E_OPENROUTER_KEY_FILE=../deploy/.env \
    uv run python tests/e2e_walkthrough.py <screenshot dir>

Setup → admin configures a model and a Search Provider → creates a User →
a Project and a Session → a real Run (costs money) → the Report, a citation,
and the exports. Not part of pytest: it needs a running stack and a key.
"""

import os
import re
import sys
import time

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("LITSTORM_E2E_URL", "http://localhost:5173")
CODE = os.environ["LITSTORM_E2E_SETUP_CODE"]
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.org", "e2e admin password"
MODEL = os.environ.get("LITSTORM_E2E_MODEL", "google/gemini-3.5-flash-lite")
TOPIC = os.environ.get("LITSTORM_E2E_TOPIC", "Retrieval-Augmented Generation (RAG)")


def openrouter_key():
    path = os.environ["LITSTORM_E2E_OPENROUTER_KEY_FILE"]
    for line in open(path, encoding="utf-8"):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("no OPENROUTER_API_KEY in " + path)


def csrf(page):
    return next(c["value"] for c in page.context.cookies() if c["name"] == "litstorm_csrf")


def read_report(page, out, run_id=None):
    """Step 5: the Report, a citation, the exports."""
    shot = lambda name: page.screenshot(path=os.path.join(out, f"{name}.png"), full_page=True)
    if run_id:
        page.goto(f"{BASE}/runs/{run_id}")
    else:
        page.get_by_role("button", name="อ่านรายงาน").click()
    page.wait_for_url(re.compile(r"/runs/"))
    expect(page.locator("article h1")).to_be_visible()
    shot("08-report")
    page.locator("button.cite").first.click()
    expect(page.locator("aside")).to_be_visible()
    page.screenshot(path=os.path.join(out, "09-citation-panel.png"))
    run_id = page.url.rstrip("/").split("/")[-1]
    for fmt in ("pdf", "html", "md"):
        r = page.request.get(f"{BASE}/api/runs/{run_id}/export?format={fmt}&evidence=true")
        assert r.ok, (fmt, r.status)
        with open(os.path.join(out, f"report.{fmt}"), "wb") as f:
            f.write(r.body())
    print("walkthrough passed; run", run_id)


def resume(out, run_id):
    """Sign in as the walkthrough's admin and read an existing report."""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page.goto(f"{BASE}/login")
        page.locator("input").nth(0).fill(ADMIN_EMAIL)
        page.locator("input").nth(1).fill(ADMIN_PASSWORD)
        page.get_by_role("button").last.click()
        page.wait_for_url(re.compile(r"/$"))
        read_report(page, out, run_id)
        browser.close()


def main(out):
    os.makedirs(out, exist_ok=True)
    shot = lambda page, name: page.screenshot(path=os.path.join(out, f"{name}.png"), full_page=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")

        # 1. First-run setup
        page.goto(BASE)
        page.wait_for_url(re.compile(r"/setup"))
        shot(page, "01-setup")
        fields = page.locator("form input")
        fields.nth(0).fill(CODE)
        fields.nth(1).fill("ผู้ดูแล")
        fields.nth(2).fill(ADMIN_EMAIL)
        fields.nth(3).fill(ADMIN_PASSWORD)
        page.get_by_role("button").last.click()
        page.wait_for_url(re.compile(r"/admin"))

        # 2. The key goes through the API; the model and provider through the UI
        r = page.request.put(
            f"{BASE}/api/admin/llm-credentials/openrouter",
            data={"api_key": openrouter_key()},
            headers={"X-CSRF-Token": csrf(page)},
        )
        assert r.ok, r.text()
        page.get_by_role("button", name=re.compile("โมเดล")).first.click()
        page.get_by_role("button", name="เพิ่มโมเดล").click()
        form = page.locator("form").last
        inputs = form.locator("input")
        inputs.nth(0).fill("Gemini 3.5 Flash Lite")
        inputs.nth(1).fill(MODEL)
        inputs.nth(2).fill("effort:minimal")
        inputs.nth(3).fill("1500")
        inputs.nth(4).fill("4000")
        form.get_by_label("ค่าเริ่มต้น").check()
        form.get_by_role("button", name="บันทึก").click()
        expect(page.get_by_text(MODEL)).to_be_visible()
        shot(page, "02-admin-models")

        page.get_by_role("button", name="บริการค้นหา").first.click()
        page.get_by_role("button", name="เพิ่มบริการค้นหา").click()
        form = page.locator("form").last
        form.locator("input").first.fill("arXiv")
        form.locator("select").select_option("arxiv")
        form.get_by_label("ค่าเริ่มต้น").check()
        form.get_by_role("button", name="บันทึก").click()
        expect(page.get_by_text("arxiv", exact=False).first).to_be_visible()
        shot(page, "03-admin-search")

        # 3. A User gets a one-time link
        page.get_by_role("button", name="ผู้ใช้").first.click()
        form = page.locator("form").first
        form.locator("input").nth(0).fill("reader@example.org")
        form.locator("input").nth(1).fill("ผู้อ่าน")
        form.get_by_role("button", name="สร้าง").click()
        expect(page.get_by_text("ลิงก์ตั้งรหัสผ่าน")).to_be_visible()
        shot(page, "04-admin-user-link")

        # 4. A Project, a Session, and a real Run
        page.get_by_role("link", name="โปรเจกต์").click()
        page.get_by_placeholder(re.compile("ทบทวน")).fill("ทดสอบระบบ")
        page.get_by_role("button", name="โปรเจกต์ใหม่").click()
        page.get_by_role("link", name=re.compile("ทดสอบระบบ")).click()
        page.get_by_placeholder("ต้องการค้นคว้าเรื่องอะไร").fill(TOPIC)
        shot(page, "05-new-research")
        page.get_by_role("button", name="เริ่มค้นคว้า").click()
        page.wait_for_url(re.compile(r"/sessions/"))
        time.sleep(20)
        shot(page, "06-running")

        deadline = time.time() + 20 * 60
        while time.time() < deadline:
            if page.get_by_role("button", name="อ่านรายงาน").count():
                break
            if page.get_by_text(re.compile("ล้มเหลว|ถูกขัดจังหวะ")).count():
                shot(page, "07-failed")
                raise SystemExit("the Run failed; see 07-failed.png")
            time.sleep(10)
        else:
            raise SystemExit("no report within 20 minutes")
        shot(page, "07-done")

        # 5. The Report, a citation, the exports
        read_report(page, out)
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 2:
        resume(sys.argv[1], sys.argv[2])
    else:
        main(sys.argv[1])
