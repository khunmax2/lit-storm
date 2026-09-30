"""Acceptance for the interactive report (litstorm.visuals, render/interactive),
on a freshly installed stack of its own.

    uv run python tests/acceptance_visuals.py <output dir> <report.json>

Wipes and installs Compose project `litstorm-visuals` on port 8094 (never the
one in daily use), under /litstorm as on host 203. No research is run: a Run
is handed the test Engine (engines/fake.py), then given `report.json` — a
real report with evidence — as its result. The one real model call is the
drawing itself (fractions of a cent); the OpenRouter key is read from
stack/.env, as tests/acceptance.py reads it.

Writes <output dir>/acceptance.md with each check and its evidence, plus
screenshots.
"""

import json
import os
import re
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

import ui

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = "litstorm-visuals"
PORT = "8094"
COMPOSE = [
    "docker", "compose", "-p", PROJECT,
    "-f", os.path.join(ROOT, "stack", "compose.yml"),
    "-f", os.path.join(ROOT, "stack", "compose.mirror.yml"),
]
os.environ["LITSTORM_PORT"] = PORT
BASE = f"http://127.0.0.1:{PORT}/litstorm"
MODEL = "google/gemini-3.1-flash-lite"
ADMIN = ("admin@example.org", "visuals acceptance admin")
ALICE = ("alice@example.org", "visuals acceptance alice")


def sh(*args, check=True):
    print("$", " ".join(args), flush=True)
    return subprocess.run(args, check=check, capture_output=True, text=True, encoding="utf-8")


def compose(*args, check=True):
    return sh(*COMPOSE, *args, check=check)


def psql(sql):
    return compose("exec", "-T", "db", "psql", "-U", "litstorm", "-tAc", sql).stdout.strip()


def openrouter_key():
    for line in open(os.path.join(ROOT, "stack", ".env"), encoding="utf-8"):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("no OPENROUTER_API_KEY in stack/.env")


class Api:
    def __init__(self, email, password):
        self.c = httpx.Client(base_url=BASE, timeout=180)
        r = self.c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text

    def _h(self):
        return {"X-CSRF-Token": self.c.cookies.get("litstorm_csrf")}

    def get(self, path, **kw):
        return self.c.get(path, **kw)

    def post(self, path, **kw):
        return self.c.post(path, headers=self._h(), **kw)

    def put(self, path, **kw):
        return self.c.put(path, headers=self._h(), **kw)

    def patch(self, path, **kw):
        return self.c.patch(path, headers=self._h(), **kw)


class Log:
    def __init__(self, out):
        self.out, self.lines, self.failed = out, [], 0

    def check(self, ok, text):
        self.lines.append(f"- {'✓' if ok else '✗ **FAILED**'} {text}")
        self.failed += 0 if ok else 1
        print(("ok   " if ok else "FAIL ") + text, flush=True)

    def note(self, text):
        self.lines.append(f"- {text}")
        print("     " + text, flush=True)

    def head(self, text):
        self.lines.append(f"\n## {text}\n")

    def shot(self, page, name):
        page.screenshot(path=os.path.join(self.out, f"{name}.png"))
        return f"![{name}]({name}.png)"


def install(log):
    log.head("A fresh stack")
    compose("down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/health", timeout=5).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(2)
    log.check(psql("select version_num from alembic_version") == "0011", "migrations up to 0011 (visuals_requests)")
    code = open(os.path.join(ROOT, "stack", "secrets", "bootstrap_code"), encoding="utf-8").read().strip()
    r = httpx.post(f"{BASE}/api/setup", json={"code": code, "email": ADMIN[0], "name": "ผู้ดูแล", "password": ADMIN[1]})
    assert r.status_code in (200, 201), r.text
    admin = Api(*ADMIN)
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": openrouter_key()})
    admin.post("/api/admin/llm-models", json={
        "label": "Gemini 3.1 Flash Lite", "provider": "openrouter", "model": MODEL, "reasoning": "effort:minimal",
        "max_tokens": {"conversation": 1500, "writing": 4000}, "is_default": True})
    link = admin.post("/api/admin/users", json={"email": ALICE[0], "name": "alice"}).json()["link"]
    r = httpx.post(f"{BASE}/api/auth/password", json={"token": link.split("#", 1)[1], "password": ALICE[1]})
    assert r.status_code == 200, r.text
    limits = admin.get("/api/admin/limits").json()
    log.check(limits.get("visuals_per_day") == 10, f"the Administrator's limits carry visuals_per_day ({limits.get('visuals_per_day')})")
    return admin


def finished_run(log, report_path):
    """A Run of Alice's, finished by the test Engine, with a real report."""
    alice = Api(*ALICE)
    compose("stop", "worker")
    project = alice.post("/api/projects", json={"name": "Visuals"}).json()
    r = alice.post(f"/api/projects/{project['id']}/sessions", json={"topic": "การปลูกทุเรียนในไทย", "language": "th"})
    assert r.status_code == 201, r.text
    run = r.json()["runs"][0]
    script = json.dumps({"script": [{"stage": "research"}, {"stage": "polish"}]}).replace("'", "''")
    psql(f"update runs set engine = 'fake', config = jsonb_set(config, '{{params}}', '{script}'::jsonb) where id = '{run['id']}'")
    compose("start", "worker")
    deadline = time.time() + 180
    while time.time() < deadline and alice.get(f"/api/runs/{run['id']}").json()["status"] != "succeeded":
        time.sleep(2)
    log.check(alice.get(f"/api/runs/{run['id']}").json()["status"] == "succeeded", "a Run finished (test Engine, no model)")
    compose("cp", report_path, f"api:/data/runs/{run['id']}/report.json")
    report = alice.get(f"/api/runs/{run['id']}/report").json()
    log.note(f"its report replaced by a real one: “{report['title']}”, {len(report['sources'])} sources with evidence")
    return alice, run


def api_checks(log, alice, run):
    log.head("Drawing, once, through the API")
    rid = run["id"]
    before = alice.get(f"/api/runs/{rid}/visuals").json()
    log.check(before["ready"] is False, "before: no figures drawn")
    tokens_before = int(psql(f"select coalesce(tokens_in, 0) from runs where id = '{rid}'"))
    t = time.time()
    r = alice.post(f"/api/runs/{rid}/visuals")
    drawn = r.json()
    log.check(r.status_code == 200 and drawn["ready"], f"drawn in {time.time() - t:.1f}s by {drawn.get('model')}")
    log.check(len(drawn["blocks"]) >= 1, "figures kept: " + ", ".join(f"{b['type']} “{b['title']}”" for b in drawn["blocks"]))
    log.note(f"{drawn['dropped']} left out by the checks")
    tokens_after = int(psql(f"select coalesce(tokens_in, 0) from runs where id = '{rid}'"))
    cost = psql(f"select cost_usd from runs where id = '{rid}'")
    log.check(tokens_after > tokens_before, f"the Run's tokens grew by {tokens_after - tokens_before} (cost now {cost or 'unpriced'})")
    again = alice.post(f"/api/runs/{rid}/visuals").json()
    log.check(again["created_at"] == drawn["created_at"] and int(psql(f"select tokens_in from runs where id = '{rid}'")) == tokens_after,
              "asked again: the kept figures, no second model call")
    log.check(int(psql("select count(*) from visuals_requests")) == 1, "one request counted against Alice's daily cap")

    other = httpx.Client(base_url=BASE)
    log.check(other.get(f"/api/runs/{rid}/interactive").status_code == 401, "signed out: the interactive page is refused")

    static = alice.get(f"/api/runs/{rid}/export", params={"format": "interactive"})
    full = alice.get(f"/api/runs/{rid}/export", params={"format": "interactive", "charts": "full"})
    log.check(static.status_code == 200 and "attachment" in static.headers["content-disposition"],
              f"download, static charts: {len(static.content) // 1024} KB")
    log.check(full.status_code == 200 and 'id="ls-charts"' in full.text, f"download, live charts: {len(full.content) // 1024} KB")
    policy = re.search(r'Content-Security-Policy" content="([^"]+)"', static.text).group(1)
    log.check("default-src 'none'" in policy and "sha256-" in policy, f"the page's own policy: `{policy[:90]}…`")
    shown = alice.get(f"/api/runs/{rid}/interactive")
    log.check(shown.headers.get("content-security-policy", "").startswith("sandbox allow-scripts")
              and "allow-same-origin" not in shown.headers["content-security-policy"],
              f"served for the app's frame with `{shown.headers.get('content-security-policy')}`")
    for fmt in ("html", "pdf", "md"):
        r = alice.get(f"/api/runs/{rid}/export", params={"format": fmt})
        log.check(r.status_code == 200, f"the other downloads still work: {fmt} ({len(r.content) // 1024} KB)")
    return drawn


def ui_checks(log, pw, run, drawn):
    log.head("In the web app")
    rid = run["id"]
    browser = pw.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
    page = browser.new_page(viewport={"width": 1360, "height": 900}, locale="th-TH")
    ui.login(page, BASE, *ALICE)
    page.goto(f"{BASE}/runs/{rid}")
    page.get_by_role("tab", name="มุมมองภาพ").click()
    frame_el = page.locator("iframe[title='มุมมองภาพ']")
    frame_el.wait_for()
    log.check(frame_el.get_attribute("sandbox") == "allow-scripts allow-popups allow-popups-to-escape-sandbox",
              f"the view is a sandboxed frame: sandbox=\"{frame_el.get_attribute('sandbox')}\"")
    frame = page.frame_locator("iframe[title='มุมมองภาพ']")
    frame.locator("figure.ix").first.wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    figures = frame.locator("figure.ix").count()
    log.check(figures >= len(drawn["blocks"]) + 2, f"{figures} figures in the frame (the model's {len(drawn['blocks'])}, the outline, the Sources cited most)")
    log.note(log.shot(page, "v1-visual-view"))

    inner = page.frames[-1]
    probe = inner.evaluate("""async () => {
      const out = {};
      try { out.parent = String(window.parent.document.title); } catch (e) { out.parent = "blocked"; }
      try { out.cookie = document.cookie; } catch (e) { out.cookie = "blocked"; }
      try { await fetch('/litstorm/api/auth/me'); out.fetch = "allowed"; } catch (e) { out.fetch = "blocked"; }
      out.js = document.documentElement.classList.contains("js");
      return out;
    }""")
    log.check(probe["parent"] == "blocked" and probe["fetch"] == "blocked" and probe["cookie"] in ("", "blocked"),
              f"from inside the frame: the app's page {probe['parent']}, its cookies {probe['cookie'] or 'none'}, the API {probe['fetch']}")
    log.check(probe["js"], "our script runs inside the frame")

    # Tabs and a citation's passage.
    first_chart = frame.locator("figure.ix [role=tab][data-tab=data]").first
    if first_chart.count():
        first_chart.click()
        log.check(frame.locator("figure.ix .panel[data-panel=data]:not([hidden])").count() >= 1, "a figure's data tab shows its table")
    cite = frame.locator("figure.ix a.cite[data-tip]").first
    if cite.count():
        cite.hover()
        page.wait_for_timeout(300)
        log.check(frame.locator(".ls-tip").count() == 1, "hovering a figure's source number shows the passage it came from")
        log.note(log.shot(page, "v2-citation-passage"))

    # Hiding a figure takes it out of the frame and the download.
    chip = page.locator("button[aria-pressed='true']").first
    title = chip.inner_text()
    chip.click()
    page.wait_for_timeout(2500)
    frame.locator("figure.ix").first.wait_for(timeout=60000)
    after = page.frame_locator("iframe[title='มุมมองภาพ']").locator("figure.ix").count()
    log.check(after == figures - 1, f"hiding “{title.strip()}” leaves {after} figures")
    log.note(log.shot(page, "v3-one-hidden"))

    page.get_by_role("button", name="ดาวน์โหลด").click()
    log.check(page.get_by_role("menuitem", name="HTML แบบโต้ตอบ").count() == 1, "the download menu offers the interactive HTML")
    log.check(page.get_by_role("menuitemcheckbox", name=re.compile("กราฟโต้ตอบเต็ม")).count() == 1, "…and live charts as an option")
    page.keyboard.press("Escape")

    page.emulate_media(color_scheme="dark")
    page.goto(f"{BASE}/runs/{rid}")
    page.get_by_role("tab", name="มุมมองภาพ").click()
    page.frame_locator("iframe").locator("figure.ix").first.wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    log.note("dark: " + log.shot(page, "v4-dark"))
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(800)
    log.note("phone: " + log.shot(page, "v5-phone"))
    browser.close()


def main(out, report_path):
    os.makedirs(out, exist_ok=True)
    log = Log(out)
    started = time.time()
    install(log)
    alice, run = finished_run(log, report_path)
    drawn = api_checks(log, alice, run)
    with sync_playwright() as pw:
        ui_checks(log, pw, run, drawn)
    verdict = "PASSED" if not log.failed else f"FAILED ({log.failed})"
    head = [
        "# Interactive report — acceptance",
        "",
        f"Stack `{PROJECT}` on port {PORT}, installed fresh; {time.strftime('%Y-%m-%d %H:%M')}; "
        f"{time.time() - started:.0f}s. Verdict: **{verdict}**.",
    ]
    with open(os.path.join(out, "acceptance.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(head + log.lines) + "\n")
    print(verdict)
    return 0 if not log.failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
