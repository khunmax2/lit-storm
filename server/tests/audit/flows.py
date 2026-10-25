"""Task 9 of the 2026-10-24 audit: the real user flows, walked in the browser. Not part of pytest. No paid calls.

    cd server && uv run python tests/audit/failure_cases.py prep      # stub model + search (stub_provider.py running on :9099)
    cd server && uv run python tests/audit/flows.py FLOW [--arg X]    # invite | run (--arg reuse,searx) | report | discussion | discussion2 | trash | admin
    cd server && uv run python tests/audit/failure_cases.py restore   # switch the stubs off again

Each flow drives the Thai interface in Edge, counts clicks and typed fields, times each step, and prints
the numbers plus the page text it saw, so friction can be judged from evidence. Screenshots go to the
scratch dir (shots/t9); none is taken on a page that shows a set-password link, a session or a token.
Passwords come from creds.json (the invitee's is generated here and saved there); nothing is printed.

Tied to the 2026-10-24 audit stack, which is gone now: `discussion2` defaults to a Discussion id that
existed only there (pass `--arg <session id>` on any other stack), `run --arg reuse` looks for a Project
whose name has "audit flow", and creds.json, the stub model "AUDIT stub model" and "AUDIT stub search"
come from live_runs.py and failure_cases.py prep. Rerunning it needs those set up again.
"""

import argparse
import json
import re
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_runs as L  # noqa: E402
import ui  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

SHOTS = L.SCRATCH / "shots" / "t9"
INVITEE = "audit-invitee@example.org"


class Flow:
    """Counts what a person would have to do: clicks, typed fields, key presses, seconds."""

    def __init__(self, name, page):
        self.name, self.page = name, page
        self.clicks = self.types = self.keys = 0
        self.t0 = time.time()
        self.steps = []
        SHOTS.mkdir(parents=True, exist_ok=True)

    def click(self, loc, label=""):
        self.clicks += 1
        loc.click()
        if label:
            self.steps.append(f"click {label}")

    def fill(self, loc, text, label=""):
        self.types += 1
        loc.fill(text)
        if label:
            self.steps.append(f"type {label}")

    def press(self, key):
        self.keys += 1
        self.page.keyboard.press(key)

    def shot(self, name):
        self.page.screenshot(path=str(SHOTS / f"{self.name}-{name}.png"))

    def text(self, sel="body", limit=700):
        try:
            t = self.page.locator(sel).first.inner_text(timeout=3000)
        except Exception as e:  # noqa: BLE001
            t = f"<{type(e).__name__}>"
        return re.sub(r"\s+", " ", t)[:limit]

    def toasts(self):
        return [re.sub(r"\s+", " ", x) for x in self.page.locator("[data-sonner-toast]").all_inner_texts()]

    def done(self):
        print(f"== {self.name}: {self.clicks} clicks, {self.types} fields typed, {self.keys} keys, {time.time() - self.t0:.0f}s")


def browser_page(p, w=1280, h=860):
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": w, "height": h}, locale="th-TH")
    return b, ctx, ctx.new_page()


def ensure_invitee_password():
    c = L.creds()
    if "invitee" not in c:
        c["invitee"] = {"email": INVITEE, "password": secrets.token_urlsafe(14) + "aA1!"}
        L.CREDS.write_text(json.dumps(c), encoding="utf-8")
    return c["invitee"]


def flow_invite(a):
    c, inv = L.creds(), ensure_invitee_password()
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        f = Flow("invite", page)
        ui.login(page, L.BASE, c["admin"]["email"], c["admin"]["password"])
        page.goto(f"{L.BASE}/settings/users")
        f.shot("1-users")
        print("users page:", f.text("main", 400))
        f.click(page.get_by_role("button", name="ผู้ใช้ใหม่"), "ผู้ใช้ใหม่")
        d = page.get_by_role("dialog")
        f.shot("2-dialog")
        print("dialog:", f.text("[role=dialog]", 500))
        f.fill(d.locator("#u-email"), INVITEE, "email")
        f.fill(d.locator("#u-name"), "ผู้ถูกเชิญทดสอบ", "name")
        f.click(d.get_by_role("button", name="สร้าง"), "สร้าง")
        link = d.locator("input[readonly]")
        expect(link).to_have_value(re.compile(r"/set-password#"))
        print("after create:", re.sub(r"https?://\S+", "<url>", f.text("[role=dialog]", 600)))
        url = link.input_value()  # never printed
        f.click(d.get_by_role("button", name="เสร็จ"), "เสร็จ")
        print("after close:", f.text("main", 500))
        f.done()
        ctx.close()
        # the invitee, in a fresh browser context
        b2, ctx2, pg = browser_page(p)
        g = Flow("setpw", pg)
        t = time.time()
        pg.goto(url)
        pg.wait_for_selector("#password")
        print(f"set-password page loaded in {time.time() - t:.1f}s:", re.sub(r"\s+", " ", pg.locator("body").inner_text())[:400])
        g.fill(pg.locator("#password"), "short", "weak password")
        g.click(pg.get_by_role("button", name=re.compile("บันทึก|ตั้งรหัส|ยืนยัน")).first, "submit weak")
        pg.wait_for_timeout(1500)
        print("weak password ->", g.text("body", 500), "| url has hash:", "#" in pg.url)
        g.shot("1-weak")
        g.fill(pg.locator("#password"), inv["password"], "password")
        g.click(pg.get_by_role("button", name=re.compile("บันทึก|ตั้งรหัส|ยืนยัน")).first, "submit")
        pg.wait_for_url(re.compile(r"/$"), timeout=15000)
        pg.wait_for_timeout(1500)
        print("landed:", pg.url.split("/litstorm")[-1], "|", g.text("main", 500))
        g.shot("2-landed")
        g.done()
        # back button after set-password: does the link still work?
        pg.go_back()
        pg.wait_for_timeout(2500)
        print("back ->", pg.url.split("/litstorm")[-1].split("#")[0], "| hash kept:", "#" in pg.url, "|", g.text("body", 300))
        pg.screenshot(path=str(SHOTS / "setpw-3-back.png"))
        ctx2.close()
        # wrong password 3x then right
        b3, ctx3, lp = browser_page(p)
        h = Flow("login", lp)
        lp.goto(f"{L.BASE}/login")
        for i in range(3):
            t = time.time()
            h.fill(lp.locator("#email"), INVITEE, "email")
            h.fill(lp.locator("#password"), "wrong-" + secrets.token_hex(4), "wrong password")
            h.click(lp.get_by_role("button", name="เข้าสู่ระบบ"), "login")
            lp.wait_for_timeout(1200)
            print(f"try {i + 1}: {time.time() - t:.1f}s |", h.text("form", 300), "| fields kept: email=",
                  lp.locator("#email").input_value() == INVITEE, "password=", bool(lp.locator("#password").input_value()),
                  "| focus:", lp.evaluate("document.activeElement && (document.activeElement.id || document.activeElement.tagName)"))
            if i == 2:
                h.shot("1-third-wrong")
        print("forgot link:", h.text("body", 600))
        h.fill(lp.locator("#email"), INVITEE)
        h.fill(lp.locator("#password"), inv["password"], "right password")
        h.click(lp.get_by_role("button", name="เข้าสู่ระบบ"), "login")
        lp.wait_for_url(re.compile(r"/$"), timeout=15000)
        print("right password ->", lp.url.split("/litstorm")[-1], "|", h.text("main", 300))
        h.done()
        ctx3.close()


def pick(f, chip, option, label=""):
    """Open a chip on the composer and choose an option; counts two clicks."""
    f.click(chip, label or f"chip -> {option}")
    f.click(f.page.get_by_role("option", name=re.compile(option)).first, option)


def login_as(page, who):
    c = L.creds()[who]
    ui.login(page, L.BASE, c["email"], c["password"])


def state_probe(f, tag):
    print(f"[{tag}] url={f.page.url.split('/litstorm')[-1]} | {f.text('main', 450)}")


def flow_run(a):
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "invitee")
        f = Flow("run", page)
        # 1. a Project
        t = time.time()
        page.goto(f"{L.BASE}/projects")
        proj = ""
        if "reuse" in a.arg:
            page.get_by_text("audit flow").first.click()
            page.wait_for_url(re.compile(r"/projects/[0-9a-f-]+$"))
        else:
            f.click(page.get_by_role("button", name="โปรเจกต์ใหม่").first, "โปรเจกต์ใหม่")
            d = page.get_by_role("dialog")
            print("new project dialog:", f.text("[role=dialog]", 300))
            f.fill(d.locator("#project-name"), "ทดสอบการนอนหลับ (audit flow)", "project name")
            f.click(d.get_by_role("button", name="สร้าง"), "สร้าง")
            page.wait_for_url(re.compile(r"/projects/[0-9a-f-]+$"))
            page.wait_for_timeout(1000)
            proj = page.url.rstrip("/").split("/")[-1]
        print(f"project created in {time.time() - t:.1f}s")
        state_probe(f, "project page")
        f.shot("1-project")
        # 2. the composer: stub model and search, fast depth
        topic = "ผลของการนอนหลับต่อความจำ"
        f.fill(page.get_by_placeholder(re.compile("พิมพ์หัวข้อ")), topic, "topic")
        print("composer controls:", page.evaluate("[...document.querySelectorAll('main button, main [role=combobox]')].map(e=>(e.getAttribute('aria-label')||e.innerText||'').trim().slice(0,40)).filter(Boolean)"))
        pick(f, page.get_by_role("combobox", name=re.compile("^โมเดล")).first, "AUDIT stub model")
        if "searx" not in a.arg:
            f.click(page.get_by_role("button", name=re.compile("บริการค้นหา")).first, "chip บริการค้นหา")
            page.wait_for_timeout(500)
            print("search popover:", f.text("[role=dialog],[data-radix-popper-content-wrapper]", 400))
            f.shot("2a-search-popover")
            f.click(page.get_by_text("AUDIT stub search").first, "AUDIT stub search")
            f.click(page.locator("[role=menuitemcheckbox][aria-checked=true]", has_text="SearXNG").first, "untick SearXNG (it stays the main source until unticked)")
            print("after pick:", f.text("[data-radix-popper-content-wrapper]", 300))
            page.keyboard.press("Escape")
        f.click(page.get_by_role("button", name=re.compile("ระดับความลึก")).first, "chip ความลึก")
        page.wait_for_timeout(400)
        print("depth popover:", f.text("[data-radix-popper-content-wrapper]", 500))
        f.click(page.get_by_text(re.compile("^เร็ว")).first, "เร็ว")
        f.shot("2-composer")
        print("composer before start:", f.text("main", 500))
        t_start = time.time()
        f.click(page.get_by_role("button", name="เริ่มค้นคว้า"), "เริ่มค้นคว้า")
        page.wait_for_url(re.compile(r"/sessions/"), timeout=30000)
        print(f"-> session page after {time.time() - t_start:.1f}s")
        seen, last = [], ""
        for i in range(120):
            page.wait_for_timeout(2500)
            cur = f.text("main", 600)
            if cur != last:
                seen.append((round(time.time() - t_start), cur))
                last = cur
            if ui.FINAL_BADGE.search(cur) and "อ่านรายงาน" in cur or (ui.FINAL_BADGE.search(cur) and i > 3):
                break
        for s, tx in seen:
            print(f"  +{s}s: {tx[:350]}")
        f.shot("3-session-final")
        print(f"run finished after {time.time() - t_start:.0f}s")
        # 3. the report
        rl = page.get_by_role("link", name="อ่านรายงาน")
        print("link to report present:", rl.count())
        if rl.count():
            f.click(rl.first, "อ่านรายงาน")
            page.wait_for_url(re.compile(r"/runs/"), timeout=15000)
            page.wait_for_timeout(2500)
            state_probe(f, "report")
            f.shot("4-report")
            page.go_back()
            page.wait_for_timeout(1500)
            state_probe(f, "back from report")
        f.done()
        # remember ids for later flows
        print("project", proj, "session", page.url.rstrip("/").split("/")[-1])
        b.close()


def flow_report(a):
    """Read a finished STORM report as the User (the stub cannot write one) and click a citation."""
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "user")
        f = Flow("report", page)
        page.goto(f"{L.BASE}/")
        t = time.time()
        f.click(page.get_by_role("link", name=re.compile("งานวิจัยทั้งหมด")).first, "งานวิจัยทั้งหมด (sidebar)")
        page.wait_for_timeout(1500)
        print("all research:", f.text("main", 500))
        f.shot("1-all")
        row = page.locator("tbody tr", has_text="ผลของการนอนหลับต่อความจำของนักเรียน").filter(has_text="เสร็จแล้ว").first
        f.click(row.locator("td").first, "a finished row")
        page.wait_for_url(re.compile(r"/sessions/"))
        page.wait_for_timeout(1500)
        print("session:", f.text("main", 500))
        f.shot("2-session")
        f.click(page.get_by_role("link", name="อ่านรายงาน").first, "อ่านรายงาน")
        page.wait_for_url(re.compile(r"/runs/"))
        expect(page.locator("article h1")).to_be_visible()
        print(f"report open after {time.time() - t:.1f}s |", f.text("article", 400))
        f.shot("3-report")
        print("toolbar:", page.evaluate("[...document.querySelectorAll('#page-toolbar button, #page-toolbar a')].map(e=>(e.getAttribute('aria-label')||e.innerText||'').trim()).filter(Boolean)"))
        print("cite buttons:", page.locator("button.cite").count())
        f.click(page.locator("button.cite").first, "a citation")
        panel = page.get_by_role("dialog")
        expect(panel).to_be_visible()
        page.wait_for_timeout(600)
        print("citation panel:", f.text("[role=dialog]", 700))
        print("source links:", page.evaluate("[...document.querySelectorAll('[role=dialog] a')].map(a=>[a.target,a.rel,(a.getAttribute('href')||'').slice(0,0)+'<href>'])"))
        f.shot("4-citation")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        print("Esc closes panel:", page.get_by_role("dialog").count() == 0, "| scroll kept:", page.evaluate("window.scrollY"))
        # back button leaves the report: is the place kept?
        page.evaluate("window.scrollTo(0, 1500)")
        page.wait_for_timeout(300)
        page.go_back()
        page.wait_for_timeout(1200)
        print("back ->", page.url.split("/litstorm")[-1][:40])
        page.go_forward()
        page.wait_for_timeout(1500)
        print("forward: scrollY", page.evaluate("window.scrollY"), "(was 1500)")
        f.done()
        b.close()


def wait_idle(f, secs=150):
    """Wait until the Co-STORM buttons are enabled again; returns seconds waited."""
    t = time.time()
    btn = f.page.get_by_role("button", name=re.compile("คุยต่อ 1 รอบ"))
    while time.time() - t < secs:
        f.page.wait_for_timeout(1500)
        try:
            if btn.count() and btn.first.is_enabled():
                return time.time() - t
        except Exception:  # noqa: BLE001
            pass
    return -1


def flow_discussion(a):
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "invitee")
        f = Flow("disc", page)
        page.goto(f"{L.BASE}/")
        t0 = time.time()
        f.click(page.get_by_role("tab", name="Co-STORM"), "mode Co-STORM")
        page.wait_for_timeout(500)
        print("composer in Co-STORM:", f.text("main", 400))
        f.fill(page.get_by_placeholder(re.compile("พิมพ์หัวข้อ")), "ประโยชน์ของการเดินต่อสุขภาพหัวใจ", "topic")
        pick(f, page.get_by_role("combobox", name=re.compile("^โมเดล")).first, "AUDIT stub model")
        f.click(page.get_by_role("button", name="เริ่มค้นคว้า"), "เริ่มค้นคว้า")
        page.wait_for_url(re.compile(r"/sessions/"), timeout=30000)
        print(f"opened after {time.time() - t0:.1f}s")
        seen, last = [], ""
        for i in range(10):
            page.wait_for_timeout(1500)
            cur = f.text("main", 500)
            if cur != last:
                seen.append(cur)
                last = cur
        for x in seen[:4]:
            print("  open:", x[:450])
        f.shot("1-opening")
        w = wait_idle(f)
        print(f"opening turn done after {w:.0f}s |", f.text("main", 900))
        f.shot("2-opened")
        f.click(page.get_by_role("button", name="ลองใหม่"), "ลองใหม่ (stub fails again)")
        page.wait_for_timeout(8000)
        print("after retry:", f.text("main", 500))
        f.done()
        b.close()


def flow_discussion2(a):
    """The rest of the Co-STORM flow on a Discussion that is already open (real model, nano: about $0.01)."""
    sid = a.arg or "f705285d-91ae-430a-b294-a8ecc043dd00"
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "user")
        f = Flow("disc2", page)
        L.gate()
        page.goto(f"{L.BASE}/sessions/{sid}")
        page.wait_for_timeout(2500)
        print("open discussion:", f.text("main", 700))
        f.shot("0-open")
        print("waiting for any turn in progress:", wait_idle(f))
        # type, send
        box = page.locator("form textarea").last
        f.fill(box, "ช่วยอธิบายความเสี่ยงสำหรับผู้สูงอายุด้วย", "say")
        L.gate()
        f.click(page.get_by_role("button", name="ส่ง"), "ส่ง")
        page.wait_for_timeout(1200)
        print("just after send:", f.text("main", 500), "| box cleared:", box.input_value() == "")
        f.shot("3-sending")
        # draft while busy, then leave and come back
        box = page.locator("form textarea").last
        f.fill(box, "ข้อความที่ยังไม่ได้ส่ง (ฉบับร่าง)", "draft while busy")
        sid = page.url
        f.click(page.get_by_role("link", name="หน้าแรก").first, "หน้าแรก (leave)")
        page.wait_for_timeout(800)
        page.go_back()
        page.wait_for_timeout(2500)
        box = page.locator("form textarea").last
        print("back to the discussion; draft kept:", repr(box.input_value()) if box.count() else "<no box>", "| url same:", page.url == sid)
        w = wait_idle(f)
        print(f"turn done after {w:.0f}s |", f.text("main", 900))
        # auto 3 turns
        L.gate()
        f.click(page.get_by_role("button", name=re.compile("ให้คุยเอง 3 รอบ")), "ให้คุยเอง 3 รอบ")
        page.wait_for_timeout(1500)
        print("auto started:", f.text("main", 400))
        f.shot("4-auto")
        w = wait_idle(f, 240)
        print(f"auto done after {w:.0f}s |", f.text("main", 700))
        f.shot("5-after-auto")
        # report
        L.gate()
        f.click(page.get_by_role("button", name="สร้างรายงาน"), "สร้างรายงาน")
        page.wait_for_timeout(1500)
        print("report started:", f.text("main", 400))
        w = wait_idle(f, 240)
        print(f"report turn done after {w:.0f}s |", f.text("main", 900))
        f.shot("6-report-turn")
        print("side panel:", f.text("aside", 500))
        f.done()
        print("total_usd", L.spend())
        b.close()


def flow_trash(a):
    """export -> move into a Project -> trash -> restore -> move back, as the User, on a finished STORM report."""
    title = "ผลของการนอนหลับต่อความจำของนักเรียน"
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "user")
        f = Flow("trash", page)
        api = L.Api("user")
        sess = next(s for s in api.get("/sessions").json() if s["title"] == title and s["id"].startswith("b76a4f32"))
        sid = sess["id"]
        page.goto(f"{L.BASE}/sessions/{sid}")
        page.wait_for_timeout(2000)
        f.click(page.get_by_role("link", name="อ่านรายงาน").first, "อ่านรายงาน")
        page.wait_for_url(re.compile(r"/runs/"))
        page.wait_for_timeout(2000)
        # 1. export
        f.click(page.get_by_role("button", name=re.compile("ดาวน์โหลด")).first, "ดาวน์โหลด")
        page.wait_for_timeout(500)
        menu = f.text("[role=menu]", 600)
        print("download menu:", menu)
        f.shot("1-download-menu")
        items = page.get_by_role("menuitem")
        print("menu items:", [items.nth(i).inner_text().replace("\n", " / ") for i in range(items.count())])
        t = time.time()
        with page.expect_download(timeout=60000) as dl:
            f.click(items.filter(has_text=re.compile("Markdown", re.I)).first if items.filter(has_text=re.compile("Markdown", re.I)).count() else items.first, "export item")
        d = dl.value
        print(f"download '{Path(d.suggested_filename).suffix}' {time.time() - t:.1f}s; toasts:", f.toasts())
        page.wait_for_timeout(800)
        print("page after export click:", f.text("main", 200), "| toasts:", f.toasts())
        # 2. move into a Project
        page.go_back()
        page.wait_for_timeout(1500)
        f.click(page.get_by_role("button", name="เพิ่มเติม").first, "... เพิ่มเติม")
        page.wait_for_timeout(400)
        print("more menu:", f.text("[role=menu]", 300))
        f.click(page.get_by_role("menuitem", name=re.compile("ย้าย")).first, "ย้ายไปโปรเจกต์")
        dlg = page.get_by_role("dialog")
        f.click(dlg.get_by_role("combobox").first, "target select")
        page.wait_for_timeout(400)
        opts = page.get_by_role("option")
        print("targets:", [opts.nth(i).inner_text() for i in range(min(opts.count(), 8))], "total", opts.count())
        f.shot("2-move-targets")
        f.click(opts.filter(has_text="audit").first if opts.filter(has_text="audit").count() else opts.nth(1), "choose a project")
        f.click(dlg.get_by_role("button", name=re.compile("ย้าย|ตกลง|บันทึก")).last, "confirm move")
        page.wait_for_timeout(1000)
        print("after move: toasts", f.toasts(), "|", f.text("main", 250))
        f.shot("3-after-move")
        # 3. trash it
        f.click(page.get_by_role("button", name="เพิ่มเติม").first, "... เพิ่มเติม")
        f.click(page.get_by_role("menuitem", name=re.compile("ลบ")).first, "ลบ")
        ad = page.get_by_role("alertdialog")
        print("delete dialog:", f.text("[role=alertdialog]", 400))
        f.shot("4-delete-dialog")
        f.click(ad.get_by_role("button", name="ใช่"), "ใช่")
        page.wait_for_timeout(1500)
        print("after delete: url", page.url.split("/litstorm")[-1][:50], "| toasts:", f.toasts(), "|", f.text("main", 200))
        # 4. trash page and restore
        f.click(page.get_by_role("link", name="ถังขยะ").first, "ถังขยะ (sidebar)")
        page.wait_for_timeout(1500)
        print("trash:", f.text("main", 500))
        row = page.locator("tbody tr", has_text=title).first
        print("row:", row.inner_text().replace("\n", " | "))
        f.shot("5-trash")
        f.click(row.get_by_role("button", name=re.compile("กู้")), "กู้คืน")
        page.wait_for_timeout(1200)
        print("after restore: url", page.url.split("/litstorm")[-1][:50], "| toasts:", f.toasts(), "| rows left with title:", page.locator("tbody tr", has_text=title).count())
        f.shot("6-restored")
        # 5. where did it go? back to the session and out of the Project again
        page.goto(f"{L.BASE}/sessions/{sid}")
        page.wait_for_timeout(1800)
        print("restored session:", f.text("main", 300))
        f.click(page.get_by_role("button", name="เพิ่มเติม").first, "... เพิ่มเติม")
        f.click(page.get_by_role("menuitem", name=re.compile("ย้าย")).first, "ย้ายไปโปรเจกต์")
        dlg = page.get_by_role("dialog")
        f.click(dlg.get_by_role("combobox").first, "target select")
        f.click(page.get_by_role("option").filter(has_text=re.compile("ไม่อยู่ในโปรเจกต์|ไม่มี")).first, "none")
        f.click(dlg.get_by_role("button", name=re.compile("ย้าย|ตกลง|บันทึก")).last, "confirm move")
        page.wait_for_timeout(1000)
        print("moved back:", f.toasts(), "|", api.get(f"/sessions/{sid}").json().get("project_id"))
        f.done()
        b.close()


def flow_admin(a):
    """Every settings page -> System status -> acknowledge -> create an MCP token, as the Administrator."""
    with sync_playwright() as p:
        b, ctx, page = browser_page(p)
        login_as(page, "admin")
        f = Flow("admin", page)
        errors = []
        page.on("console", lambda m: errors.append(m.text[:160]) if m.type == "error" else None)
        page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url.split('/litstorm')[-1][:60]}") if r.status >= 400 else None)
        page.wait_for_timeout(1000)
        f.click(page.get_by_role("link", name="ตั้งค่าระบบ").first, "ตั้งค่าระบบ")
        page.wait_for_url(re.compile(r"/settings/"))
        tabs = ["ผู้ใช้", "โมเดล", "บริการค้นหา", "โหมดวิจัย", "ขีดจำกัด", "การใช้งาน", "MCP"]
        for i, name in enumerate(tabs):
            if i:
                t = time.time()
                f.click(page.locator("main a, main [role=tab]").filter(has_text=re.compile(f"^{name}$")).first, f"tab {name}")
                page.wait_for_timeout(1200)
            print(f"[{name}] {page.url.split('/litstorm')[-1]} | {f.text('main', 380)}")
            f.shot(f"1-settings-{i}-{name}")
        print("console/HTTP errors on settings pages:", errors[:10])
        # System status
        f.click(page.get_by_role("link", name="สถานะระบบ").first, "สถานะระบบ")
        page.wait_for_url(re.compile(r"/status"))
        page.wait_for_timeout(2000)
        print("status:", f.text("main", 900))
        f.shot("2-status")
        btns = page.evaluate("[...document.querySelectorAll('main button')].map(b=>(b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean)")
        print("status buttons:", btns)
        ack = page.get_by_role("button", name=re.compile("รับทราบ"))
        print("acknowledge buttons:", ack.count())
        before = L.Api("admin").get("/admin/monitor/open").json()
        if ack.count():
            f.click(ack.first, "รับทราบ")
            page.wait_for_timeout(1500)
            print("after acknowledge: toasts", f.toasts(), "| ", f.text("main", 500))
            print("badge before/after:", before, L.Api("admin").get("/admin/monitor/open").json())
            f.shot("3-acknowledged")
            page.go_back()
            page.wait_for_timeout(800)
            page.go_forward()
            page.wait_for_timeout(1500)
        # MCP token
        f.click(page.get_by_text("audit-admin@example.org").first, "account menu")
        f.click(page.get_by_role("menuitem", name=re.compile("การเชื่อมต่อ")), "การเชื่อมต่อ (MCP)")
        page.wait_for_url(re.compile(r"/connections"))
        page.wait_for_timeout(1500)
        print("connections:", f.text("main", 900))
        f.shot("4-connections")
        print("connections buttons:", page.evaluate("[...document.querySelectorAll('main button')].map(b=>(b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean)"))
        f.click(page.get_by_role("button", name=re.compile("สร้าง.*token|token ใหม่|สร้างโทเค็น|สร้าง", re.I)).first, "create token")
        dlg = page.get_by_role("dialog")
        page.wait_for_timeout(600)
        print("token dialog:", f.text("[role=dialog]", 700))
        f.shot("5-token-dialog")
        f.fill(dlg.locator("input").first, "audit flow token", "token name")
        f.click(dlg.get_by_role("button", name="สร้าง token"), "สร้าง token")
        page.wait_for_timeout(1500)
        # the token itself is never printed or photographed: long strings are masked, no screenshot here
        shown = re.sub(r"\S{24,}", "<masked>", f.text("[role=dialog]", 900))
        print("after create (masked):", shown)
        print("dialog buttons:", page.evaluate("[...document.querySelectorAll('[role=dialog] button')].map(b=>(b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean)"))
        f.click(dlg.get_by_role("button", name=re.compile("เสร็จ|ปิด|Close")).first, "close")
        page.wait_for_timeout(800)
        print("tokens list:", re.sub(r"\S{24,}", "<masked>", f.text("main", 1500))[-600:])
        b.close()
    f.done()


FLOWS = {"invite": flow_invite, "run": flow_run, "report": flow_report, "discussion": flow_discussion, "discussion2": flow_discussion2, "trash": flow_trash, "admin": flow_admin}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("flow", choices=sorted(FLOWS))
    ap.add_argument("--arg", default="")
    a = ap.parse_args()
    FLOWS[a.flow](a)
