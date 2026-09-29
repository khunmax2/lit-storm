"""Walk the whole first-release path through the web UI, with screenshots.

    LITSTORM_E2E_URL=http://localhost:5173 LITSTORM_E2E_SETUP_CODE=... \
    LITSTORM_E2E_OPENROUTER_KEY_FILE=../deploy/.env \
    uv run python tests/e2e_walkthrough.py <screenshot dir>

Setup → admin configures a model and a Search Provider → creates a User →
a Project and a Session → a real Run (costs money) → the Report, a citation,
and the exports. Not part of pytest: it needs a running stack and a key.
The screens' selectors are in ui.py.
"""

import os
import re
import sys
import time

from playwright.sync_api import expect, sync_playwright

import ui

BASE = os.environ.get("LITSTORM_E2E_URL", "http://localhost:5173")
CODE = os.environ.get("LITSTORM_E2E_SETUP_CODE", "")
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.org", "e2e admin password"
MODEL = os.environ.get("LITSTORM_E2E_MODEL", "google/gemini-3.5-flash-lite")
TOPIC = os.environ.get("LITSTORM_E2E_TOPIC", "Retrieval-Augmented Generation (RAG)")


def openrouter_key():
    path = os.environ["LITSTORM_E2E_OPENROUTER_KEY_FILE"]
    for line in open(path, encoding="utf-8"):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("no OPENROUTER_API_KEY in " + path)


def read_report(page, out, run_id=None):
    """Step 5: the Report, a citation, the exports."""
    shot = lambda name: page.screenshot(path=os.path.join(out, f"{name}.png"), full_page=True)
    if run_id:
        page.goto(f"{BASE}/runs/{run_id}")
        expect(page.locator("article h1")).to_be_visible()
    else:
        ui.open_report(page)
    shot("08-report")
    panel = ui.open_citation(page)
    expect(panel.get_by_text("ข้อความหลักฐาน")).to_be_visible()
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
        ui.login(page, BASE, ADMIN_EMAIL, ADMIN_PASSWORD)
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
        ui.setup(page, BASE, CODE, "ผู้ดูแล", ADMIN_EMAIL, ADMIN_PASSWORD)

        # 2. The key goes through the API; the model and provider through the UI
        r = page.request.put(
            f"{BASE}/api/admin/llm-credentials/openrouter",
            data={"api_key": openrouter_key()},
            headers={"X-CSRF-Token": ui.csrf(page)},
        )
        assert r.ok, r.text()
        ui.add_model(page, BASE, "Gemini 3.5 Flash Lite", MODEL, "effort:minimal", "1500", "4000", default=True)
        shot(page, "02-admin-models")

        if os.environ.get("LITSTORM_E2E_KEEP_SEARXNG"):
            # The stack seeds its own SearXNG as the default; use that.
            page.goto(f"{BASE}/settings/search")
            expect(page.get_by_text("searxng", exact=False).first).to_be_visible()
        else:
            ui.add_search(page, BASE, "arXiv", default=True)
        shot(page, "03-admin-search")

        # 3. A User gets a one-time link
        link = ui.new_user(page, BASE, "reader@example.org", "ผู้อ่าน")
        assert "/set-password#" in link, link
        shot(page, "04-admin-users")

        # 4. A Project, a Session, and a real Run
        ui.new_project(page, BASE, "ทดสอบระบบ")
        page.get_by_placeholder(re.compile("พิมพ์หัวข้อ")).fill(TOPIC)
        shot(page, "05-new-research")
        ui.start_research(page, TOPIC)
        time.sleep(20)
        shot(page, "06-running")

        badge = ui.run_badge(page)
        expect(badge).to_be_visible(timeout=20 * 60_000)
        if badge.inner_text().strip() != "เสร็จแล้ว":
            shot(page, "07-failed")
            raise SystemExit(f"the Run ended {badge.inner_text()!r}; see 07-failed.png")
        shot(page, "07-done")

        # 5. The Report, a citation, the exports
        read_report(page, out)
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 2:
        resume(sys.argv[1], sys.argv[2])
    else:
        main(sys.argv[1])
