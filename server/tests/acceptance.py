"""First-release acceptance, run against a freshly installed Docker stack.

    uv run python tests/acceptance.py <output dir>

Wipes its own stack (Compose project `litstorm-accept` on port 8091, never
the one in daily use; `docker compose down -v`), installs it again under
/litstorm as on the host, and checks
every criterion in docs/web-app-design.md (เกณฑ์รับงานรุ่นแรก), writing
<output dir>/acceptance.md with a verdict and the evidence for each, plus
screenshots. Runs real research (costs money, well under a dollar) and
reads the OpenRouter key from stack/.env.

Two things cannot be shown on a live stack without moving its clock: the
month rolling over, and a Run booked in one month finishing in the next.
Those are marked as verified by the automated tests that pin them.
"""

import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field

import httpx
from playwright.sync_api import expect, sync_playwright

import ui

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# A stack of its own, so the wipe never touches the one in daily use: its
# own Compose project (and volumes) and port, set up as it runs on host
# 203 — behind an nginx at /litstorm (stack/compose.mirror.yml).
PROJECT = os.environ.get("LITSTORM_ACCEPT_PROJECT", "litstorm-accept")
PORT = os.environ.get("LITSTORM_ACCEPT_PORT", "8091")
COMPOSE = [
    "docker", "compose", "-p", PROJECT,
    "-f", os.path.join(ROOT, "stack", "compose.yml"),
    "-f", os.path.join(ROOT, "stack", "compose.mirror.yml"),
]
os.environ["LITSTORM_PORT"] = PORT  # read by the Compose files
BASE = f"http://127.0.0.1:{PORT}/litstorm"
# The Search Provider the acceptance Runs use: arXiv, or another kind when
# arXiv is rate-limiting this address (it answered 429 after a day of
# benchmarks on 2026-09-30); TCI-ThaiJO is seeded at setup and needs no key.
SEARCH_KIND = os.environ.get("LITSTORM_ACCEPT_SEARCH", "arxiv")
MODEL = "google/gemini-3.5-flash-lite"
ADMIN = ("admin@example.org", "acceptance admin pw")
ALICE = ("alice@example.org", "alice password 1")
BOB = ("bob@example.org", "bob password 12")
FINAL = {"succeeded", "failed", "cancelled", "interrupted"}
SMALL = {"max_perspective": 1, "max_conv_turn": 1, "search_top_k": 2}


# --- plumbing ----------------------------------------------------------------------


def sh(*args, check=True):
    print("$", " ".join(args), flush=True)
    return subprocess.run(args, check=check, capture_output=True, text=True)


def compose(*args, check=True):
    return sh(*COMPOSE, *args, check=check)


def psql(sql):
    return compose("exec", "-T", "db", "psql", "-U", "litstorm", "-tAc", sql).stdout.strip()


def wait_healthy(timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/health", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("stack did not become healthy")


class Api:
    """One signed-in User, talking to the API the way the web app does."""

    def __init__(self, email, password):
        self.c = httpx.Client(base_url=BASE, timeout=120)
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

    def delete(self, path, **kw):
        return self.c.delete(path, headers=self._h(), **kw)

    def research(self, topic, language="th", project=None, **choice):
        if project is None:
            project = self.post("/api/projects", json={"name": f"P {topic[:20]}"}).json()
        r = self.post(
            f"/api/projects/{project['id']}/sessions", json={"topic": topic, "language": language, **choice}
        )
        assert r.status_code == 201, r.text
        return project, r.json()

    def again(self, session_id, topic, language="th", **choice):
        r = self.post(f"/api/sessions/{session_id}/runs", json={"topic": topic, "language": language, **choice})
        return r

    def run(self, run_id):
        return self.get(f"/api/runs/{run_id}").json()

    def wait(self, run_id, until=FINAL, timeout=900, stage=None):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.run(run_id)
            if r["status"] in until or (stage and r.get("stage") == stage):
                return r
            time.sleep(5)
        raise TimeoutError(f"run {run_id} still {r['status']}/{r.get('stage')} after {timeout}s")


def standard_depth(admin, storm):
    """The limits' depth levels with the standard level's STORM knobs replaced."""
    levels = admin.get("/api/admin/limits").json()["depth_levels"]
    levels["standard"] = {**levels["standard"], "storm": storm}
    return levels


def set_limits(admin, **changes):
    current = admin.get("/api/admin/limits").json()
    r = admin.put("/api/admin/limits", json={**current, **changes})
    assert r.status_code == 200, r.text
    return current


def openrouter_key():
    for line in open(os.path.join(ROOT, "stack", ".env"), encoding="utf-8"):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("no OPENROUTER_API_KEY in stack/.env")


@dataclass
class Criterion:
    text: str
    verdict: str = "not run"  # "pass" | "fail" | "pass (automated tests)"
    evidence: list = field(default_factory=list)


# --- the run -------------------------------------------------------------------------------


class Acceptance:
    def __init__(self, out):
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.c = {}
        self.ctx = {}

    def criterion(self, key, text):
        self.c[key] = Criterion(text)
        return self.c[key]

    def note(self, key, line):
        print(f"  [{key}] {line}", flush=True)
        self.c[key].evidence.append(line)

    def check(self, key, ok, line):
        self.note(key, ("✓ " if ok else "✗ ") + line)
        if not ok:
            self.c[key].verdict = "fail"
        return ok

    def done(self, key, verdict="pass"):
        if self.c[key].verdict != "fail":
            self.c[key].verdict = verdict

    def shot(self, page, name, full=True):
        page.screenshot(path=os.path.join(self.out, f"{name}.png"), full_page=full)
        return f"{name}.png"

    # 1 -------------------------------------------------------------------------------------
    def install(self, pw):
        k = "install"
        self.criterion(k, "ติดตั้งบน local ด้วย Docker Compose ใหม่ สร้าง Admin คนแรก และสร้างบัญชีผู้ใช้พร้อมตั้งรหัสผ่านได้")
        compose("down", "-v")
        sh("sh", os.path.join(ROOT, "stack", "init-secrets.sh"))
        compose("up", "-d", "--build")
        wait_healthy()
        services = compose("ps", "--format", "{{.Service}} {{.State}}").stdout.split("\n")
        self.check(k, all("running" in s for s in services if s), f"services: {', '.join(s for s in services if s)}")
        self.check(k, psql("select count(*) from users") == "0", "fresh database: no users")

        code = open(os.path.join(ROOT, "stack", "secrets", "bootstrap_code"), encoding="utf-8").read().strip()
        page = pw.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")
        ui.setup(page, BASE, code, "ผู้ดูแล", *ADMIN)
        self.note(k, f"first Administrator created through the setup page ({self.shot(page, 'a1-after-setup')})")
        page.close()
        r = httpx.post(f"{BASE}/api/setup", json={"code": code, "email": "x@y.org", "name": "X", "password": "long enough 1"})
        self.check(k, r.status_code == 409, f"setup refuses a second time: {r.status_code}")

        admin = Api(*ADMIN)
        for email, password in (ALICE, BOB):
            link = admin.post("/api/admin/users", json={"email": email, "name": email.split("@")[0]}).json()["link"]
            r = httpx.post(f"{BASE}/api/auth/password", json={"token": link.split("#", 1)[1], "password": password})
            self.check(k, r.status_code == 200, f"{email} set a password from their one-time link")
        self.ctx["admin"] = admin
        self.done(k)

    # 2 -------------------------------------------------------------------------------------
    def configure(self):
        k = "reports"
        self.criterion(k, "ผู้ดูแลตั้งค่า LLM และ Search Provider ผ่านเว็บ แล้วผู้ใช้สร้างรายงานจริงได้ทั้งภาษาไทยและอังกฤษ")
        admin = self.ctx["admin"]
        admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": openrouter_key()})
        model = admin.post(
            "/api/admin/llm-models",
            json={"label": "Gemini 3.5 Flash Lite", "provider": "openrouter", "model": MODEL,
                  "reasoning": "effort:minimal", "max_tokens": {"conversation": 1500, "writing": 4000},
                  "is_default": True},
        ).json()
        spare = admin.post(
            "/api/admin/llm-models",
            json={"label": "Gemini (spare)", "provider": "openrouter", "model": MODEL,
                  "reasoning": "effort:minimal", "max_tokens": {"conversation": 1500, "writing": 4000}},
        ).json()
        providers = admin.get("/api/admin/search-providers").json()
        searxng = next(p for p in providers if p["kind"] == "searxng")
        self.check(k, searxng["is_default"], "the stack's SearXNG is seeded as the default Search Provider")
        # SearXNG depends on outside engines that throttle an address after
        # heavy use; the acceptance Runs use arXiv (or SEARCH_KIND) instead.
        search = _use_search(admin)
        self.note(k, f"{search['label']} made the default Search Provider for these Runs")
        t = admin.post(f"/api/admin/llm-models/{model['id']}/test").json()
        self.check(k, t["ok"], f"model test button: {t['message']} in {t['seconds']}s")
        t = admin.post(f"/api/admin/search-providers/{searxng['id']}/test").json()
        self.note(k, f"SearXNG test button (outside engines, not scored): {'ok' if t['ok'] else 'no'} — {t['message']}")
        t = admin.post(f"/api/admin/search-providers/{search['id']}/test").json()
        self.check(k, t["ok"], f"{search['label']} test button: {t['message']}")
        self.ctx.update(model=model, spare=spare, searxng=searxng, search=search)

    # 2 + 6 ----------------------------------------------------------------------------------
    def real_reports(self, pw):
        k, k6 = "reports", "close"
        self.criterion(k6, "ปิดหน้าเว็บแล้วงานทำต่อ และกลับมาดูสถานะกับผลลัพธ์ได้")
        # Alice starts a Thai report in the browser, then closes it at once.
        browser = pw.new_context(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page = browser.new_page()
        login(page, *ALICE)
        ui.new_project(page, BASE, "ตรวจรับ")
        ui.start_research(page, "โมเดลภาษาขนาดใหญ่สำหรับภาษาไทย")
        session_url = page.url
        self.shot(page, "b1-thai-started")
        browser.close()
        self.note(k6, "Alice started a Thai report in the browser and closed it straight away")

        bob = Api(*BOB)
        _, bob_session = bob.research("Retrieval-augmented generation for question answering", language="en")
        alice = Api(*ALICE)
        alice_session = alice.get(f"/api/sessions/{session_url.rstrip('/').split('/')[-1]}").json()
        a_run, b_run = alice_session["runs"][0], bob_session["runs"][0]
        started = time.time()
        a = alice.wait(a_run["id"])
        b = bob.wait(b_run["id"])
        self.check(k, a["status"] == "succeeded", f"Thai report: {a['status']}, {a['source_count']} sources")
        self.check(k, b["status"] == "succeeded", f"English report: {b['status']}, {b['source_count']} sources")
        if a["status"] != "succeeded" or b["status"] != "succeeded":
            raise RuntimeError(f"no reports to read: {a['reason']} / {b['reason']}")
        th = alice.get(f"/api/runs/{a_run['id']}/report").json()
        en = bob.get(f"/api/runs/{b_run['id']}/report").json()
        thai_chars = sum(1 for ch in th["lead"] if "฀" <= ch <= "๿")
        self.check(k, th["language"] == "th" and thai_chars > 50, f"Thai report is written in Thai ({thai_chars} Thai letters in the lead)")
        self.check(k, en["language"] == "en" and not re.search("[฀-๿]", en["lead"]), "English report is written in English")
        self.note(k, f"both finished within {int(time.time() - started)}s of each other starting")
        self.ctx.update(alice=alice, bob=bob, a_run=a, b_run=b, a_session=alice_session, session_url=session_url)

        # Coming back later, in a new browser.
        browser = pw.new_context(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page = browser.new_page()
        login(page, *ALICE)
        page.goto(session_url)
        expect(page.get_by_role("link", name="อ่านรายงาน").first).to_be_visible()
        self.check(k6, True, f"back in a new browser, the Run is done and its report is there ({self.shot(page, 'b2-back-later')})")
        self.ctx["alice_page"] = page
        self.done(k)
        self.done(k6)

    # 10 + 11 ------------------------------------------------------------------------------------
    def reading(self):
        k10, k11 = "citation", "export"
        self.criterion(k10, "คลิก citation แล้วอ่านหลักฐานของแหล่งที่ถูกอ้างอิงจากแผงด้านข้างได้")
        self.criterion(k11, "export HTML, Markdown และ PDF ได้ตามตัวเลือกแนบหลักฐาน โดย HTML เปิดอ่านออฟไลน์ได้ตามขอบเขตที่กำหนด")
        page = self.ctx["alice_page"]
        ui.open_report(page)
        self.shot(page, "c1-report")
        url_before = page.url
        panel = ui.open_citation(page)
        self.check(k10, page.url == url_before, "the Source panel opens beside the report; the page does not change")
        has_evidence = panel.get_by_text("ข้อความหลักฐาน").count() > 0
        self.check(k10, has_evidence, f"the panel shows the Source and its evidence ({self.shot(page, 'c2-citation-panel', full=False)})")
        self.done(k10)

        run_id = self.ctx["a_run"]["id"]
        for fmt in ("html", "md", "pdf"):
            for evidence in (False, True):
                r = page.request.get(f"{BASE}/api/runs/{run_id}/export?format={fmt}&evidence={str(evidence).lower()}")
                name = f"report{'-evidence' if evidence else ''}.{fmt}"
                with open(os.path.join(self.out, name), "wb") as f:
                    f.write(r.body())
                self.check(k11, r.ok and len(r.body()) > 1000, f"{name}: {r.status}, {len(r.body()):,} bytes")
        html_plain = open(os.path.join(self.out, "report.html"), encoding="utf-8").read()
        html_ev = open(os.path.join(self.out, "report-evidence.html"), encoding="utf-8").read()
        self.check(k11, "ข้อความบางส่วนที่ระบบใช้จริง" in html_ev and "ข้อความบางส่วนที่ระบบใช้จริง" not in html_plain,
                   "evidence appears only when asked for, marked as excerpts")
        external = re.findall(r'<(?:script|link|img)[^>]+(?:src|href)="https?://', html_ev)
        self.check(k11, not external, "the HTML loads nothing from the network (no scripts, stylesheets or images)")
        offline = self.ctx["pw"].new_context(offline=True)
        p = offline.new_page()
        p.goto("file:///" + os.path.join(self.out, "report-evidence.html").replace("\\", "/"))
        expect(p.locator("h1")).to_be_visible()
        p.locator("a.cite").first.click()
        self.check(k11, "#src-" in p.url, f"opened offline, a citation jumps to its source ({self.shot(p, 'c3-offline-html', full=False)})")
        offline.close()
        pdf = open(os.path.join(self.out, "report-evidence.pdf"), "rb").read(5)
        self.check(k11, pdf == b"%PDF-", "the PDF is a PDF")
        self.done(k11)

    # 8 ------------------------------------------------------------------------------------
    def isolation(self):
        k = "privacy"
        self.criterion(k, "ผู้ใช้เข้าถึงข้อมูลของผู้อื่นไม่ได้ และผู้ดูแลอ่านเนื้อหางานวิจัยของผู้อื่นไม่ได้ (Support Access Grant อยู่ในรุ่นสอง)")
        admin, bob, a = self.ctx["admin"], self.ctx["bob"], self.ctx["a_run"]
        s = self.ctx["a_session"]
        for who, api in (("Bob", bob), ("the Administrator", admin)):
            codes = [
                api.get(f"/api/runs/{a['id']}").status_code,
                api.get(f"/api/runs/{a['id']}/report").status_code,
                api.get(f"/api/runs/{a['id']}/export", params={"format": "html"}).status_code,
                api.get(f"/api/sessions/{s['id']}").status_code,
                api.get(f"/api/projects/{s['project_id']}").status_code,
            ]
            self.check(k, set(codes) == {404}, f"{who} asking for Alice's Run, report, export, Session and Project: {codes}")
        self.check(k, bob.delete(f"/api/projects/{s['project_id']}").status_code == 404, "Bob cannot delete Alice's Project")
        usage = json.dumps(admin.get("/api/admin/usage").json()) + json.dumps(admin.get("/api/admin/runs").json())
        self.check(k, "ภาษาไทย" not in usage and "Retrieval-augmented" not in usage,
                   "the Administrator's usage pages show owners, statuses and costs, never topics")
        self.check(k, bob.get("/api/admin/users").status_code == 403, "a User cannot open the admin API")
        self.done(k)

    # 3 + 4 ----------------------------------------------------------------------------------------
    def queue_and_quota(self):
        k3, k4 = "queue", "quota"
        self.criterion(k3, "คิวทำงานตามเพดานและการสลับผู้ใช้ รวมถึงกรณีรอเลือกโมเดลหรือ provider ใหม่")
        self.criterion(k4, "โควตาจอง นับ คืน และเปลี่ยนรอบเดือนตามกติกา รวมถึงงานข้ามเดือน")
        admin, alice, bob = self.ctx["admin"], self.ctx["alice"], self.ctx["bob"]
        spare, model = self.ctx["spare"], self.ctx["model"]
        saved = set_limits(admin, max_concurrent_total=1, max_concurrent_per_user=1,
                           depth_levels=standard_depth(admin, SMALL))
        self.ctx["limits"] = saved

        compose("stop", "worker")
        q0 = alice.get("/api/me/quota").json()
        _, s1 = alice.research("Graph neural networks")
        a1 = s1["runs"][0]
        a2 = alice.again(s1["id"], "Diffusion models for image generation", llm_model_id=spare["id"]).json()
        _, sb = bob.research("Speech recognition for low-resource languages", language="en")
        b1 = sb["runs"][0]
        q1 = alice.get("/api/me/quota").json()
        self.check(k4, q1["reserved"] == q0["reserved"] + 2 and q1["remaining"] == q0["remaining"] - 2,
                   f"submitting reserves quota: reserved {q0['reserved']}→{q1['reserved']}, remaining {q0['remaining']}→{q1['remaining']}")

        # The spare model is turned off: Alice's second Run waits for a choice.
        admin.put(f"/api/admin/llm-models/{spare['id']}", json={**spare, "enabled": False})
        parked = alice.run(a2["id"])
        self.check(k3, parked["status"] == "needs_selection", f"turning a model off parks the Run that chose it: {parked['status']}")
        q2 = alice.get("/api/me/quota").json()
        self.check(k4, q2["reserved"] == q1["reserved"], "a parked Run keeps its reservation")
        r = alice.post(f"/api/runs/{a2['id']}/selection",
                       json={"llm_model_id": model["id"], "search_provider_id": self.ctx["search"]["id"]})
        self.check(k3, r.status_code == 200 and r.json()["status"] == "queued",
                   "choosing again puts the same Run back in the queue")
        self.check(k4, alice.get("/api/me/quota").json()["reserved"] == q1["reserved"], "choosing again charges nothing twice")

        compose("start", "worker")
        runs = {"A1": a1["id"], "A2": a2["id"], "B1": b1["id"]}
        for name, run_id in runs.items():
            owner = bob if name == "B1" else alice
            done = owner.wait(run_id)
            self.note(k3, f"{name}: {done['status']}, started {done['started_at']}")
        order = psql(
            "select string_agg(id::text, ',' order by started_at) from runs where id in ("
            + ",".join(f"'{i}'" for i in runs.values()) + ")"
        ).split(",")
        named = [next(n for n, i in runs.items() if i == x) for x in order]
        # Whoever started longest ago goes first, so B1 may lead; what must
        # not happen is Bob waiting behind both of Alice's.
        self.check(k3, named[-1] != "B1" and named.index("A1") < named.index("A2"),
                   f"with one slot, Alice's two Runs and Bob's one started in the order {named} — Bob did not wait for both of Alice's")
        overlap = psql(
            "select count(*) from runs a join runs b on a.id < b.id and a.started_at < b.finished_at "
            "and b.started_at < a.finished_at where a.id in (" + ",".join(f"'{i}'" for i in runs.values())
            + ") and b.id in (" + ",".join(f"'{i}'" for i in runs.values()) + ")"
        )
        self.check(k3, overlap == "0", "with a system ceiling of 1, no two of them ran at the same time")

        q3 = alice.get("/api/me/quota").json()
        self.check(k4, q3["used"] == q0["used"] + 2 and q3["reserved"] == q0["reserved"],
                   f"started Runs count as used: used {q0['used']}→{q3['used']}")
        # Full quota refuses, in the UI's words.
        uid = alice.get("/api/me").json()["id"]
        admin.patch(f"/api/admin/users/{uid}", json={"monthly_run_quota": q3["used"]})
        r = alice.again(s1["id"], "เกินโควตา")
        self.check(k4, r.status_code == 429 and r.json()["detail"] == "quota_exhausted", "a full month refuses a new Run")
        admin.patch(f"/api/admin/users/{uid}", json={"monthly_run_quota": None})
        self.note(k4, "the month rolling over (Bangkok time) and a Run booked in one month counting there after it ends: "
                      "tests/test_queue_rules.py::test_a_new_month_starts_from_zero_in_bangkok_time and "
                      "::test_a_run_counts_against_the_month_it_was_booked_in (real Postgres)")
        self.done(k3)
        self.done(k4, "pass (the month change: automated tests)")

    # 5 ---------------------------------------------------------------------------------------------
    def cancel_and_retry(self):
        k = "cancel"
        self.criterion(k, "ยกเลิกงานในคิวและงานที่กำลังทำได้ตามกติกา และกดลองใหม่แล้วสร้าง Run ใหม่ที่เชื่อมกับรอบเดิม")
        alice, bob = self.ctx["alice"], self.ctx["bob"]
        compose("stop", "worker")
        _, s = bob.research("Quantum error correction", language="en")
        waiting = s["runs"][0]
        q0 = bob.get("/api/me/quota").json()
        r = bob.post(f"/api/runs/{waiting['id']}/cancel").json()
        self.check(k, r["status"] == "cancelled" and r["quota_refunded"], "a waiting Run stops at once and its quota comes back")
        self.check(k, bob.get("/api/me/quota").json()["reserved"] == q0["reserved"] - 1, "the reservation is released")
        compose("start", "worker")

        _, s = alice.research("Reinforcement learning from human feedback")
        running = alice.wait(s["runs"][0]["id"], until={"running"}, timeout=120)
        alice.wait(running["id"], until=FINAL, stage="research", timeout=120)
        r = alice.post(f"/api/runs/{running['id']}/cancel").json()
        self.check(k, r["status"] == "cancelling", f"a running Run is asked to stop: {r['status']}")
        final = alice.wait(running["id"])
        self.check(k, final["status"] == "cancelled" and not final["quota_refunded"],
                   f"it stops ({final['status']}) and, having started, still counts against quota")

        again = alice.post(f"/api/runs/{running['id']}/retry").json()
        self.check(k, again["parent_run_id"] == running["id"] and again["id"] != running["id"],
                   "retry makes a new Run linked to the old one, whose history stays")
        alice.post(f"/api/runs/{again['id']}/cancel")
        alice.wait(again["id"])
        self.done(k)

    # 7 ----------------------------------------------------------------------------------------------
    def worker_crash(self):
        k = "crash"
        self.criterion(k, "จำลอง Worker ล่มแล้วระบบตรวจพบ Run ที่ถูกขัดจังหวะ เก็บผลที่บันทึกไว้ และรอผู้ใช้ลองใหม่ โดยไม่เริ่มทั้งรอบอัตโนมัติ")
        bob = self.ctx["bob"]
        _, s = bob.research("Privacy in federated learning", language="en")
        run_id = s["runs"][0]["id"]
        at_kill = bob.wait(run_id, until=FINAL, stage="outline", timeout=300)
        if not self.check(k, at_kill["status"] == "running", f"the Run is running ({at_kill['stage']}) when the Worker dies"):
            return
        compose("kill", "worker")
        self.note(k, "the worker container was killed while the Run was in its outline stage")
        time.sleep(75)  # past the 60-second lease
        self.check(k, bob.run(run_id)["status"] in ("running", "cancelling"), "with no Worker, nothing has marked it yet")
        compose("start", "worker")
        final = bob.wait(run_id, timeout=120)
        self.check(k, final["status"] == "interrupted" and final["quota_refunded"],
                   f"a Worker coming back marks it {final['status']}, quota refunded")
        files = compose("exec", "-T", "worker", "sh", "-c", f"ls /data/runs/{run_id} /data/runs/{run_id}/work/storm/article", check=False).stdout
        self.check(k, "conversation_log.json" in files, "what the finished stages wrote is kept (research output on disk)")
        time.sleep(15)
        self.check(k, bob.run(run_id)["status"] == "interrupted", "it is not started again on its own")
        again = bob.post(f"/api/runs/{run_id}/retry").json()
        self.check(k, again["parent_run_id"] == run_id, "the owner can try again, as a new linked Run")
        bob.post(f"/api/runs/{again['id']}/cancel")
        bob.wait(again["id"])
        self.done(k)

    # 9 -------------------------------------------------------------------------------------------------
    def deadline(self):
        k = "deadline"
        self.criterion(k, "Run ที่เกินเพดานเวลารวมถูกหยุด และคืนโควตาตามตาราง")
        admin, bob = self.ctx["admin"], self.ctx["bob"]
        # arXiv answers one request every three seconds; a deep research
        # plan through it takes well over the shortest ceiling allowed.
        set_limits(admin, run_deadline_minutes=5,
                   depth_levels=standard_depth(admin, {"max_perspective": 8, "max_conv_turn": 8, "search_top_k": 5}))
        _, s = bob.research("Deadline test: retrieval augmented generation", language="en",
                            search_provider_id=self.ctx["search"]["id"])
        started = time.time()
        final = bob.wait(s["runs"][0]["id"], timeout=600)
        took = int(time.time() - started)
        self.check(k, final["status"] == "failed" and final["reason"] == "timed_out",
                   f"a Run past its 5-minute ceiling ends {final['status']}/{final['reason']} after {took}s")
        self.check(k, final["quota_refunded"], "and its quota comes back")
        set_limits(admin, **self.ctx["limits"])
        self.done(k)

    # 12 ------------------------------------------------------------------------------------------------
    def trash(self, pw):
        k = "trash"
        self.criterion(k, "ลบแล้วเข้าถังขยะ กู้คืนภายใน 30 วันได้ และจัดการงานที่เกี่ยวข้องก่อนลบไฟล์ถาวร")
        alice, a = self.ctx["alice"], self.ctx["a_run"]
        project_id = self.ctx["a_session"]["project_id"]
        page = self.ctx["alice_page"]
        ui.delete_project(page, BASE, project_id)
        self.check(k, alice.get(f"/api/runs/{a['id']}/report").status_code == 404, "deleted: its report is gone from view")
        row = ui.trash_row(page, BASE, "ตรวจรับ")
        expect(row).to_be_visible()
        self.note(k, f"it is in the Trash with its days left ({self.shot(page, 'd1-trash')})")
        row.get_by_role("button", name="กู้คืน").click()
        expect(page.get_by_text("ถังขยะว่าง")).to_be_visible()
        self.check(k, alice.get(f"/api/runs/{a['id']}/report").status_code == 200, "restored: the report is back")

        # Work inside is stopped when something goes to the Trash.
        compose("stop", "worker")
        _, s = alice.research("Knowledge distillation")
        inside = s["runs"][0]
        alice.delete(f"/api/projects/{s['project_id']}")
        alice.post(f"/api/trash/project/{s['project_id']}/restore")
        stopped = alice.run(inside["id"])
        self.check(k, stopped["status"] == "cancelled" and stopped["quota_refunded"],
                   "deleting a Project stops the work waiting inside it first")
        compose("start", "worker")

        # 30 days later.
        q0 = alice.get("/api/me/quota").json()
        alice.delete(f"/api/projects/{project_id}")
        psql(f"update projects set trashed_at = now() - interval '31 days' where id = '{project_id}'")
        compose("restart", "worker")  # it purges on start, then every 10 minutes
        time.sleep(15)
        row = psql(f"select coalesce(purged_at::text,''), topic, coalesce(session_id::text,'') from runs where id = '{a['id']}'")
        purged_at, topic, session_id = row.split("|")
        self.check(k, purged_at and topic == "" and session_id == "", "after 30 days the content is deleted for good")
        files = compose("exec", "-T", "worker", "sh", "-c", f"ls /data/runs/{a['id']} 2>&1 || true").stdout
        self.check(k, "No such file" in files, "and its files are gone from the volume")
        self.check(k, alice.get("/api/me/quota").json() == q0, "deleting did not give quota back; the month's figures stand")
        self.check(k, psql(f"select count(*) from projects where id = '{project_id}'") == "0", "the Project row is gone")
        self.done(k)

    # restart --------------------------------------------------------------------------------------
    def restart(self):
        k = "install"
        bob, b = self.ctx["bob"], self.ctx["b_run"]
        compose("down")
        compose("up", "-d")
        wait_healthy()
        self.check(k, httpx.get(f"{BASE}/api/setup").json()["needed"] is False, "after down/up the setup page stays closed")
        again = Api(*BOB)
        self.check(k, again.get(f"/api/runs/{b['id']}/report").status_code == 200, "and data survives in the volumes")

    # ------------------------------------------------------------------------------------------------
    def write_report(self):
        order = ["install", "reports", "queue", "quota", "cancel", "close", "crash", "privacy", "deadline",
                 "citation", "export", "trash"]
        where = ("บน stack เดิมที่ติดตั้งไว้ (`--rerun`)" if self.ctx.get("rerun")
                 else "กับ stack ที่ติดตั้งใหม่จากศูนย์ (`docker compose down -v`)")
        lines = ["# ผลตรวจรับรุ่นแรก", "", f"รันเมื่อ {time.strftime('%Y-%m-%d %H:%M')} {where}", ""]
        for key in order:
            c = self.c.get(key)
            if c is None:
                continue
            mark = {"pass": "✅"}.get(c.verdict, "✅" if c.verdict.startswith("pass") else "❌")
            lines += [f"## {mark} {c.text}", "", f"**{c.verdict}**", ""]
            lines += [f"- {e}" for e in c.evidence] + [""]
        with open(os.path.join(self.out, "acceptance.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def login(page, email, password):
    ui.login(page, BASE, email, password)


def _use_search(admin):
    """The provider of SEARCH_KIND, added if the stack has none, made the default."""
    found = next((p for p in admin.get("/api/admin/search-providers").json() if p["kind"] == SEARCH_KIND), None)
    body = {"label": {"arxiv": "arXiv", "tci": "TCI-ThaiJO"}.get(SEARCH_KIND, SEARCH_KIND), "kind": SEARCH_KIND,
            "enabled": True, "is_default": True}
    if found is None:
        return admin.post("/api/admin/search-providers", json=body).json()
    return admin.put(f"/api/admin/search-providers/{found['id']}", json={**found, **body, "label": found["label"]}).json()


def attach(acc):
    """Pick up the stack a full run left behind, for --rerun."""
    admin = Api(*ADMIN)
    models = admin.get("/api/admin/llm-models").json()
    acc.ctx.update(
        admin=admin,
        alice=Api(*ALICE),
        bob=Api(*BOB),
        model=next(m for m in models if m["is_default"]),
        spare=next(m for m in models if not m["is_default"]),
        search=_use_search(admin),
        limits=admin.get("/api/admin/limits").json(),
    )
    # A Run parked by an earlier attempt still holds its reservation.
    admin.put(f"/api/admin/llm-models/{acc.ctx['spare']['id']}", json={**acc.ctx["spare"], "enabled": True})


RERUN = {"queue": "queue_and_quota", "cancel": "cancel_and_retry", "crash": "worker_crash", "deadline": "deadline"}


def rerun(out, keys):
    """Re-check the API-only criteria on the installed stack, without wiping it."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    acc = Acceptance(out)
    acc.ctx["rerun"] = True
    try:
        attach(acc)
        for key in keys:
            getattr(acc, RERUN[key])()
        set_limits(acc.ctx["admin"], **acc.ctx["limits"])
    except Exception:
        traceback.print_exc()
        for c in acc.c.values():
            if c.verdict == "not run":
                c.verdict = "fail"
                c.evidence.append("stopped: " + traceback.format_exc().strip().splitlines()[-1])
    finally:
        compose("start", "worker", check=False)
        acc.write_report()
    failed = [k for k, c in acc.c.items() if not c.verdict.startswith("pass")]
    print("FAILED:" if failed else "ALL PASSED", failed or "")
    return 1 if failed else 0


def main(out):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    acc = Acceptance(out)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None)
        acc.ctx["pw"] = browser
        steps = [
            lambda: acc.install(browser),
            acc.configure,
            lambda: acc.real_reports(browser),
            acc.reading,
            acc.isolation,
            acc.queue_and_quota,
            acc.cancel_and_retry,
            acc.worker_crash,
            acc.deadline,
            lambda: acc.trash(browser),
            acc.restart,
        ]
        try:
            for step in steps:
                step()
        except Exception:
            traceback.print_exc()
            for c in acc.c.values():
                if c.verdict == "not run":
                    c.verdict = "fail"
                    c.evidence.append("stopped: " + traceback.format_exc().strip().splitlines()[-1])
        finally:
            acc.write_report()
            browser.close()
    failed = [k for k, c in acc.c.items() if not c.verdict.startswith("pass")]
    print("FAILED:" if failed else "ALL PASSED", failed or "")
    return 1 if failed else 0


if __name__ == "__main__":
    # --rerun queue,cancel,crash re-checks those on the stack as it stands.
    if len(sys.argv) > 3 and sys.argv[2] == "--rerun":
        sys.exit(rerun(sys.argv[1], sys.argv[3].split(",")))
    sys.exit(main(sys.argv[1]))
