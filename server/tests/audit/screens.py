"""Task 8 of the 2026-10-24 audit: a screenshot of every page in its states, and an axe-core scan of each.

Not part of pytest. It needs a running stack (default: the throwaway audit stack), a creds file with
the accounts (see live_runs.py) and axe-core installed in a scratch folder (`npm i axe-core` there).
It changes nothing in the data: it only reads, opens dialogs (never saves them) and, for the account
you sign in as, sets the interface language the way the language switch does.

    cd server && uv run python tests/audit/screens.py --who user --viewport 1440x900 --theme light --lang th

    --base URL         default http://127.0.0.1:8098/litstorm (env AUDIT_BASE)
    --who NAME         key in creds.json: user (default), admin, empty
    --viewport WxH     repeatable; default 1440x900 1024x768 390x844
    --theme T          repeatable; light / dark; default both
    --lang L           repeatable; th / en; default both
    --out DIR          screenshots + axe.jsonl; default <scratch>/shots/t8
    --axe FILE         axe.min.js; default <scratch>/axe/node_modules/axe-core/axe.min.js
    --only SUBSTR      only pages whose name contains it
    --extra            also the loading and error states (a delayed / failing API), light th only

Screenshots hold no key, link or token: the pages shown never display one (the Agent report shows an
OpenRouter account id in a source line; those shots stay in the scratch folder).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_runs as L  # noqa: E402  (the creds, the API client, the scratch folder)

from playwright.sync_api import sync_playwright  # noqa: E402

VIEWPORTS = ["1440x900", "1024x768", "390x844"]
SETTINGS = ["users", "models", "search", "modes", "limits", "usage", "mcp"]


def pick(api, kind, engine=None, status=None, title=None, no_xss=True):
    """First session (and its latest run) that matches; None if there is none."""
    for s in api.get("/sessions").json():
        if no_xss and "onerror" in s["title"]:
            continue
        if kind and s["kind"] != kind:
            continue
        if status and s["last_status"] != status:
            continue
        if title and not re.search(title, s["title"]):
            continue
        runs = api.get(f"/sessions/{s['id']}").json()["runs"]
        if engine and not any(r["engine"] == engine for r in runs):
            continue
        run = next((r for r in runs if (not engine or r["engine"] == engine) and (not status or r["status"] == status)), runs[0])
        return s["id"], run["id"]
    return None


def targets(api, who):
    """(name, path, extra-steps) for every page the account can open."""
    t = [("home", "/", None), ("research", "/research", None), ("projects", "/projects", None),
         ("trash", "/trash", None), ("status", "/status", None), ("connections", "/connections", None)]
    projects = api.get("/projects").json()
    if projects:
        named = [p for p in projects if "onerror" not in p["name"]]
        busy = max(projects, key=lambda p: len([s for s in api.get("/sessions").json() if s["project_id"] == p["id"]]))
        t.append(("project-busy", f"/projects/{busy['id']}", None))
        if named:
            t.append(("project-named", f"/projects/{named[0]['id']}", None))
    cases = {
        "storm-th-ok": dict(kind="research", engine="storm", status="succeeded", title="[ก-๙]"),
        "storm-en-ok": dict(kind="research", engine="storm", status="succeeded", title="^[A-Za-z]"),
        "deep-ok": dict(kind="research", engine="deep", status="succeeded"),
        "medical-ok": dict(kind="research", engine="medical", status="succeeded"),
        "agent-ok": dict(kind="research", engine="agent", status="succeeded"),
        "storm-failed": dict(kind="research", engine="storm", status="failed", title="[ก-๙]"),
        "storm-interrupted": dict(kind="research", engine="storm", status="interrupted"),
        "storm-cancelled": dict(kind="research", engine="storm", status="cancelled"),
        "costorm-ok": dict(kind="discussion", status="succeeded"),
        "costorm-failed": dict(kind="discussion", status="failed"),
    }
    for name, kw in cases.items():
        found = pick(api, **kw)
        if not found:
            continue
        sid, rid = found
        t.append((f"session-{name}", f"/sessions/{sid}", None))
        if kw.get("status") == "succeeded" and kw["kind"] == "research":
            t.append((f"report-{name}", f"/runs/{rid}", "report"))
    if who == "admin":
        for s in SETTINGS:
            t.append((f"settings-{s}", f"/settings/{s}", "settings"))
    return t


def run_axe(page, axe_js):
    page.add_script_tag(path=axe_js)
    return page.evaluate(
        """async () => {
          const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});
          return r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical').map(v => ({
            id: v.id, impact: v.impact, help: v.help,
            nodes: v.nodes.length,
            samples: v.nodes.slice(0, 3).map(n => ({target: n.target.join(' '), html: n.html.slice(0, 160), why: (n.any[0] || n.all[0] || n.none[0] || {}).message}))
          }));
        }"""
    )


def settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    page.wait_for_timeout(900)


def states(page, name, kind, shot):
    """Dialogs and panels worth a picture; all closed again, nothing saved."""
    def attempt(label, fn):
        try:
            fn()
            page.wait_for_timeout(500)
            shot(f"{name}~{label}")
        except Exception as e:  # a state that is not there is just not photographed
            print(f"   (no {label} on {name}: {type(e).__name__})")
        finally:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    if name == "projects":
        attempt("new-project", lambda: page.get_by_role("button", name=re.compile("โปรเจกต์ใหม่|New project")).first.click())
    if name == "home":
        attempt("account-menu", lambda: page.locator("[data-sidebar=footer] button").first.click())
        attempt("search", lambda: page.keyboard.press("Control+k"))
    if kind == "report":
        attempt("citation", lambda: page.locator("button.cite").first.click())
    if name == "settings-models":
        attempt("add-model", lambda: page.get_by_role("button", name=re.compile("เพิ่มโมเดล|Add model")).first.click())
    if name == "settings-users":
        attempt("new-user", lambda: page.get_by_role("button", name=re.compile("ผู้ใช้ใหม่|New user")).first.click())
    if name == "settings-search":
        attempt("add-search", lambda: page.get_by_role("button", name=re.compile("เพิ่มบริการค้นหา|Add search")).first.click())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("AUDIT_BASE", "http://127.0.0.1:8098/litstorm"))
    ap.add_argument("--who", default="user")
    ap.add_argument("--viewport", action="append")
    ap.add_argument("--theme", action="append")
    ap.add_argument("--lang", action="append")
    ap.add_argument("--out", default=str(L.SCRATCH / "shots" / "t8"))
    ap.add_argument("--axe", default=str(L.SCRATCH / "axe/node_modules/axe-core/axe.min.js"))
    ap.add_argument("--only", default="")
    ap.add_argument("--extra", action="store_true")
    a = ap.parse_args()
    L.BASE = a.base
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cred = L.creds()[a.who]
    api = L.Api(a.who)
    pages = [p for p in targets(api, a.who) if a.only in p[0]]
    axe_out = open(out / "axe.jsonl", "a", encoding="utf-8")
    count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        for lang in a.lang or ["th", "en"]:
            api.put("/me/language", json={"ui_language": lang})
            for theme in a.theme or ["light", "dark"]:
                for vp in a.viewport or VIEWPORTS:
                    w, h = map(int, vp.split("x"))
                    ctx = browser.new_context(viewport={"width": w, "height": h}, locale="th-TH" if lang == "th" else "en-US", color_scheme=theme)
                    ctx.add_init_script(f"try{{localStorage.setItem('litstorm.lang','{lang}')}}catch(e){{}}")
                    page = ctx.new_page()
                    tag = f"{a.who}-{vp}-{theme}-{lang}"

                    def shot(name, full=True):
                        page.screenshot(path=str(out / f"{tag}-{name}.png"), full_page=full)

                    def scan(name):
                        for v in run_axe(page, a.axe):
                            axe_out.write(json.dumps({"who": a.who, "page": name, "viewport": vp, "theme": theme, "lang": lang, **v}, ensure_ascii=False) + "\n")
                        axe_out.flush()

                    # the signed-out pages first (login and a dead set-password link)
                    if a.who == "user":
                        for name, path in (("login", "/login"), ("set-password-dead", "/set-password#not-a-real-token")):
                            if a.only in name:
                                page.goto(a.base + path)
                                settle(page)
                                shot(name)
                                scan(name)
                                count += 1
                    page.goto(a.base + "/login")
                    page.locator("#email").fill(cred["email"])
                    page.locator("#password").fill(cred["password"])
                    page.keyboard.press("Enter")
                    page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
                    for name, path, kind in pages:
                        page.goto(a.base + path)
                        settle(page)
                        shot(name)
                        scan(name)
                        count += 1
                        states(page, name, kind, shot)
                    if a.extra and (lang, theme, vp) == ("th", "light", "1440x900"):
                        # loading: every API answer held back until the picture is taken;
                        # error: every API call fails with a 500
                        held = []
                        rx = re.compile(r".*/api/(sessions|projects|trash|admin/monitor|admin/users).*")
                        for state in ("loading", "error"):
                            if state == "loading":
                                page.route(rx, lambda r: held.append(r))
                            else:
                                page.route(rx, lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"boom"}'))
                            for name, path, _ in pages:
                                if name in ("home", "projects", "trash", "status", "research"):
                                    page.goto(a.base + path, wait_until="commit")
                                    page.wait_for_timeout(1200 if state == "loading" else 2500)
                                    shot(f"{name}~{state}", full=False)
                            page.unroute(rx)
                            for r in held:
                                try:
                                    r.abort()
                                except Exception:
                                    pass
                            held.clear()
                    ctx.close()
                print(f"{a.who} {lang} {theme}: {count} pages so far")
        browser.close()
    axe_out.close()
    print("done", count)


if __name__ == "__main__":
    main()
