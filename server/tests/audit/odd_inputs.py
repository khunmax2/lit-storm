"""Task 7 of the 2026-10-24 audit: limits and odd inputs on the audit stack. Not part of pytest. No paid calls.

    cd server && uv run python tests/audit/stub_provider.py &       # the stand-in provider, :9099 (from Task 6)
    cd server && uv run python tests/audit/odd_inputs.py stub-on    # the stub model and search ON, the stub as the openai-compatible base
    cd server && uv run python tests/audit/odd_inputs.py api        # odd values over the real HTTP API (status + a short body)
    cd server && uv run python tests/audit/odd_inputs.py queue      # queue_full and max_concurrent_total with slow stub Runs
    cd server && uv run python tests/audit/odd_inputs.py blank      # a Run whose topic is only spaces, followed to its end
    cd server && uv run python tests/audit/odd_inputs.py xss        # script text in names/topics/report/discussion, looked at in Edge
    cd server && uv run python tests/audit/odd_inputs.py stub-off   # stubs off again, limits and edited files put back

Every Run uses the stub model (failure_cases.py prep made it) and the stub search, so nothing is billed.
The XSS step edits report.json / discussion.json of two Runs the audit already has and puts them back.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_runs as L  # noqa: E402

STATE = L.SCRATCH / "failure_state.json"
ODD = L.SCRATCH / "odd_state.json"
SHOTS = L.SCRATCH / "shots"
STUB = "http://host.docker.internal:9099"
PAYLOAD = '<img src=x onerror=alert(1)>"><svg onload=alert(1)>'
REPORT_RUN = "0a688d71-d7dc-488e-96af-65378822ddc8"  # a finished STORM Run of Task 5
DISC_RUNS = ("9b54aaa0-f338-4702-8a71-66d244c5e990", "680f05a1-a644-42ce-9d66-df18c02b5e6e", "59a10409-3400-4e2a-b2a3-240bc9e082f7")  # the finished Turns of a Co-STORM Discussion of Task 5 (the page shows the latest one's view)


def st():
    return json.loads(STATE.read_text(encoding="utf-8"))


def odd():
    return json.loads(ODD.read_text(encoding="utf-8")) if ODD.exists() else {}


def keep(d):
    ODD.write_text(json.dumps(d), encoding="utf-8")


def model_body(m, enabled):
    body = {k: m[k] for k in ("label", "provider", "model", "reasoning", "max_tokens", "enabled", "is_default")}
    body["enabled"] = enabled
    return body


def search_body(mode, enabled):
    return {"label": "AUDIT stub search", "kind": "searxng", "endpoint": f"{STUB}/{mode}/search", "enabled": enabled, "is_default": False}


def set_stubs(admin, on, mode="ok"):
    s = st()
    admin.put("/admin/llm-credentials/openai-compatible", json={"api_key": "stub-key", "api_base": f"{STUB}/{mode}/v1"})
    for m in admin.get("/admin/llm-models").json():
        if m["id"] == s["model"]:
            print("model", admin.put(f"/admin/llm-models/{m['id']}", json=model_body(m, on)).status_code)
    print("search", admin.put(f"/admin/search-providers/{s['search']}", json=search_body(mode, on)).status_code)


def short(r, n=150):
    return f"{r.status_code} {r.text[:n]!r}"


def raw(api, method, path, body):
    """Send JSON text exactly as given (NUL and lone surrogates are legal JSON escapes)."""
    csrf = api.s.cookies.get("litstorm_csrf")
    return api.s.request(method, f"{L.BASE}/api{path}", data=body.encode(), timeout=60,
                         headers={"X-CSRF-Token": csrf or "", "Content-Type": "application/json"})


def cmd_stub_on(_):
    set_stubs(L.Api("admin"), True)


def cmd_stub_off(_):
    admin = L.Api("admin")
    set_stubs(admin, False)
    o = odd()
    if "limits" in o:
        print("limits restored", admin.put("/admin/limits", json=o["limits"]).status_code)
    for run, name in ((REPORT_RUN, "report.json"), *((r, "work/discussion.json") for r in DISC_RUNS)):
        if run + name in o.get("edited", {}):
            put_file(run, name, o["edited"][run + name])
            print("restored", run[:8], name)


def get_file(run, name):
    return subprocess.run(["docker", "exec", "litstorm-audit-api-1", "cat", f"/data/runs/{run}/{name}"],
                          capture_output=True, check=True).stdout.decode("utf-8")


def put_file(run, name, text):
    subprocess.run(["docker", "exec", "-i", "litstorm-audit-api-1", "sh", "-c", f"cat > /data/runs/{run}/{name}"],
                   input=text.encode("utf-8"), check=True)


def cmd_api(_):
    u = L.Api("user")
    admin = L.Api("admin")
    s = st()
    o = odd()
    cur = admin.get("/admin/limits").json()
    o.setdefault("limits", cur)  # stub-off puts these back
    keep(o)
    print("quota before:", u.get("/me/quota").json())
    admin.put("/admin/limits", json={**cur, "monthly_run_quota": 200, "max_queued_per_user": 30})
    base = {"language": "th", "depth": "fast", "engine": "storm", "llm_model_id": s["model"], "search_provider_id": s["search"]}
    made = []

    def start(label, topic, **extra):
        r = u.post("/sessions", json={**base, "topic": topic, **extra})
        print(f"topic {label:14} -> {short(r)}")
        if r.status_code == 201:
            made.append(r.json())
        return r

    print("-- topics (nothing is waiting yet; the first accepted ones start on the stub)")
    start("10000 chars", "ก" * 10000)
    start("501 chars", "x" * 501)
    start("mixed", "Songkran สงกรานต์ 🎉🇹🇭 שלום עולם مرحبا ‮evil‬ end")
    start("empty", "")
    start("5 spaces", "     ")
    start("newlines", "\n\n\n")
    start("html", PAYLOAD)
    r = raw(u, "POST", "/sessions", json.dumps({**base, "topic": "abc\u0000def"}))
    print(f"topic NUL            -> {r.status_code} {r.text[:80]!r}")
    r = raw(u, "POST", "/sessions", json.dumps({**base, "topic": "abc\ud800def"}))
    print(f"topic lone surrogate -> {r.status_code} {r.text[:80]!r}")
    print("-- project names")
    for label, name in (("empty", ""), ("5 spaces", "     "), ("duplicate 1", "AUDIT dup"), ("duplicate 2", "AUDIT dup"),
                        ("html", PAYLOAD), ("201 chars", "n" * 201)):
        r = u.post("/projects", json={"name": name})
        print(f"project {label:12} -> {short(r, 110)}")
        if r.status_code == 201:
            made.append(("project", r.json()["id"]))
    for label, name in (("NUL", "a\u0000b"), ("lone surrogate", "a\ud800b")):
        r = raw(u, "POST", "/projects", json.dumps({"name": name}))
        print(f"project {label:14} -> {r.status_code} {r.text[:60]!r}")
    print("-- other text fields with NUL")
    sid = made[0]["id"] if made and isinstance(made[0], dict) else None
    if sid:
        for label, body in (("section", {"sections": ["a\u0000b"]}), ("refinement answer", {"refinement": [{"question": "q", "answer": "a\u0000"}]}),
                            ("request_key", {"request_key": "k\u0000"})):
            r = raw(u, "POST", f"/sessions/{sid}/runs", json.dumps({**base, "topic": "valid topic", **body}))
            print(f"{label:18} NUL -> {r.status_code} {r.text[:60]!r}")
        r = raw(u, "POST", f"/sessions/{sid}/runs", json.dumps({**base, "topic": "valid topic", "sections": ["h" * 100000]}))
        print("section of 100000 chars ->", r.status_code, "(kept as", len(r.json().get("topic", "")) if r.ok else "-", ")")
        if r.ok:
            cfg = u.get(f"/runs/{r.json()['id']}").json()
            print("   stored section length:", [len(x) for x in (cfg.get("config", {}).get("sections") or [])] or "not in the API detail")
    print("-- list of sessions as the user sees it (titles)")
    print([x["title"][:20] for x in u.get("/sessions").json()][:10])
    keep({**odd(), "made": [m["id"] if isinstance(m, dict) else m[1] for m in made]})


def waiting_and_running(u):
    rows = []
    for s in u.get("/sessions").json():
        for run in u.get("/sessions/" + s["id"]).json()["runs"]:
            rows.append((run["id"], run["status"]))
    return rows


def cmd_queue(_):
    admin, u = L.Api("admin"), L.Api("user")
    s = st()
    o = odd()
    cur = admin.get("/admin/limits").json()
    o["limits"] = cur
    keep(o)
    set_stubs(admin, True, "slow")
    admin.put("/admin/llm-credentials/openai-compatible", json={"api_key": "stub-key", "api_base": f"{STUB}/slow/v1"})
    new = {**cur, "max_queued_per_user": 3, "max_concurrent_total": 1, "max_concurrent_per_user": 1, "monthly_run_quota": max(cur["monthly_run_quota"], 50)}
    print("limits ->", admin.put("/admin/limits", json=new).status_code)
    base = {"language": "th", "depth": "fast", "engine": "storm", "llm_model_id": s["model"], "search_provider_id": s["search"]}
    ids = []
    for i in range(7):
        r = u.post("/sessions", json={**base, "topic": f"queue probe {i}"})
        print(f"start {i} -> {short(r, 90)}")
        if r.status_code == 201:
            ids.append(r.json()["runs"][0]["id"])
        time.sleep(1.5 if i == 0 else 0.2)
    time.sleep(20)
    print("statuses:", [u.get(f"/runs/{i}").json()["status"] for i in ids])
    q = u.get("/me/quota").json()
    print("quota:", q)
    for i in ids:
        u.post(f"/runs/{i}/cancel")
    time.sleep(8)
    print("after cancel:", [u.get(f"/runs/{i}").json()["status"] for i in ids])
    print("quota after cancel:", u.get("/me/quota").json())
    admin.put("/admin/limits", json=cur)
    admin.put("/admin/llm-credentials/openai-compatible", json={"api_key": "stub-key", "api_base": f"{STUB}/ok/v1"})
    set_stubs(admin, True, "ok")


def cmd_blank(_):
    u = L.Api("user")
    s = st()
    r = u.post("/sessions", json={"language": "th", "depth": "fast", "engine": "storm", "llm_model_id": s["model"],
                                  "search_provider_id": s["search"], "topic": "     "})
    print(short(r))
    rid, sid = r.json()["runs"][0]["id"], r.json()["id"]
    L.follow(u, rid)
    d = u.get(f"/runs/{rid}").json()
    print({k: d.get(k) for k in ("status", "reason", "stage", "message", "topic", "quota_refunded")})
    print("session title:", repr(u.get("/sessions/" + sid).json()["title"]))
    print("quota:", u.get("/me/quota").json())


def alerts_page(page, url, found):
    page.goto(url)
    page.wait_for_timeout(2500)
    return page.evaluate("""() => ({
        img: document.querySelectorAll('img[src="x"]').length,
        svg: document.querySelectorAll('svg[onload]').length,
        onerr: document.querySelectorAll('[onerror],[onload]').length,
        title: document.title,
        text: document.body.innerText.includes('onerror=alert(1)'),
    })""")


def saved_export(u, fmt):
    """An export downloads in a browser, so save it and open the file (it is our own output, with the test text in it)."""
    r = u.get(f"/runs/{REPORT_RUN}/export", params={"format": fmt})
    out = L.SCRATCH / "exports" / f"t7-{fmt}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(r.content)
    return out.as_uri()


def cmd_xss(_):
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(exist_ok=True)
    u, admin = L.Api("user"), L.Api("admin")
    s = st()
    o = odd()
    o.setdefault("edited", {})
    # 1. names: a Project and a Session whose topic is the payload (the stub Run it queues needs no model)
    proj = u.post("/projects", json={"name": PAYLOAD}).json()
    sess = u.post(f"/projects/{proj['id']}/sessions", json={"topic": PAYLOAD, "language": "th", "depth": "fast", "engine": "storm",
                                                              "llm_model_id": s["model"], "search_provider_id": s["search"]}).json()
    run_id = sess["runs"][0]["id"]
    L.follow(u, run_id)  # the stub finds no sources: a failed Run named by the payload, which System status lists
    # a trashed copy, for the Trash page
    p2 = u.post("/projects", json={"name": PAYLOAD + " trashed"}).json()
    u.call("DELETE", f"/projects/{p2['id']}")
    # 2. the report of a finished Run: markdown, sources
    original = get_file(REPORT_RUN, "report.json")
    o["edited"][REPORT_RUN + "report.json"] = original
    keep(o)
    rep = json.loads(original)
    body = "[x](javascript:alert(1)) <img src=x onerror=alert(1)> ![t [1] onerror=alert(1)](https://example.org/a.png) <script>alert(1)</script>"
    rep["sections"][0]["body"] = body
    rep["sections"][0]["heading"] = PAYLOAD
    rep["lead"] = body
    rep["title"] = PAYLOAD
    rep["sources"][0]["url"] = "javascript:alert(document.domain)"
    rep["sources"][0]["title"] = PAYLOAD
    put_file(REPORT_RUN, "report.json", json.dumps(rep, ensure_ascii=False))
    # 3. the Co-STORM view
    for drun in DISC_RUNS:
        d_original = get_file(drun, "work/discussion.json")
        o["edited"][drun + "work/discussion.json"] = d_original
        keep(o)
        dj = json.loads(d_original)
        dj["turns"].append({"role": "User", "role_description": "", "type": "Original Question", "text": PAYLOAD + " [1](javascript:alert(1))", "cited": [], "warmup": False})
        dj["turns"][1]["role"] = PAYLOAD
        dj["turns"][1]["text"] = PAYLOAD
        dj["experts"] = [PAYLOAD] + list(dj.get("experts", []))
        put_file(drun, "work/discussion.json", json.dumps(dj, ensure_ascii=False))
    disc_session = None
    for x in u.get("/sessions").json():
        if x["title"].startswith("การออกกำลังกายกับสุขภาพจิต"):
            if any(r["id"] in DISC_RUNS for r in u.get("/sessions/" + x["id"]).json()["runs"]):
                disc_session = x["id"]
    print("discussion session", disc_session)
    sess_report = [x["id"] for x in u.get("/sessions").json() if x["id"] and any(r["id"] == REPORT_RUN for r in u.get("/sessions/" + x["id"]).json()["runs"])]
    print("report session", sess_report)

    c = L.creds()["user"]
    cc = L.creds()["admin"]
    results = {}
    outside = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")

        def login(creds_):
            ctx = b.new_context(viewport={"width": 1280, "height": 860}, locale="th-TH")
            pg = ctx.new_page()
            fired = []
            pg.on("dialog", lambda dlg: (fired.append(dlg.message), dlg.dismiss()))
            # nothing leaves the machine: a request to another host is only noted, then dropped
            pg.route("**/*", lambda route: (outside.append(route.request.url), route.abort())
                     if not route.request.url.startswith(("http://127.0.0.1", "file://", "data:", "blob:")) else route.continue_())
            pg.goto(f"{L.BASE}/login")
            pg.locator("#email").fill(creds_["email"])
            pg.locator("#password").fill(creds_["password"])
            pg.get_by_role("button", name="เข้าสู่ระบบ").click()
            pg.wait_for_url(re.compile(r"/$"))
            return ctx, pg, fired

        ctx, page, fired = login(c)
        pages = {
            "home": f"{L.BASE}/",
            "projects": f"{L.BASE}/projects",
            "project": f"{L.BASE}/projects/{proj['id']}",
            "research": f"{L.BASE}/research",
            "session": f"{L.BASE}/sessions/{sess['id']}",
            "run-failed": f"{L.BASE}/runs/{run_id}",
            "trash": f"{L.BASE}/trash",
            "report": f"{L.BASE}/runs/{REPORT_RUN}",
            "discussion": f"{L.BASE}/sessions/{disc_session}",
            "observatory-live": f"{L.BASE}/api/runs/{REPORT_RUN}/observatory",
            "export-html": saved_export(u, "html"),
            "export-interactive": saved_export(u, "interactive"),
            "export-observatory": saved_export(u, "observatory"),
            "interactive-frame": f"{L.BASE}/api/runs/{REPORT_RUN}/interactive",
        }
        for name, url in pages.items():
            try:
                results[name] = alerts_page(page, url, fired)
                if name == "discussion":  # open the folded warm-up too
                    page.get_by_text("การเตรียมพื้นหลัง").first.click()
                    page.wait_for_timeout(800)
                    results["discussion-warmup-open"] = page.evaluate("""() => ({text: document.body.innerText.includes('onerror=alert(1)'), count: document.body.innerText.split('onerror=alert(1)').length - 1, img: document.querySelectorAll('img[src="x"]').length, onerr: document.querySelectorAll('[onerror],[onload]').length})""")
            except Exception as e:  # noqa: BLE001
                results[name] = f"EXC {type(e).__name__}: {str(e)[:100]}"
            page.screenshot(path=str(SHOTS / f"t7-xss-{name}.png"))
        # the report page: links
        page.goto(pages["report"])
        page.wait_for_timeout(2500)
        results["report-links"] = page.evaluate("""() => [...document.querySelectorAll('a')].map(a => a.getAttribute('href') || '').filter(h => /^javascript/i.test(h))""")
        # export html: every href
        page.goto(pages["export-html"])
        results["export-html-js-hrefs"] = page.evaluate("""() => [...document.querySelectorAll('a')].map(a => a.getAttribute('href') || '').filter(h => /^javascript/i.test(h))""")
        # the interactive page in its frame and opened directly: fetch and cookie
        page.goto(pages["report"])
        page.wait_for_timeout(1500)
        for fr in page.frames:
            if fr is not page.main_frame:
                try:
                    results.setdefault("frames", []).append(fr.evaluate("""async () => { let f; try { f = (await fetch('/litstorm/api/me')).status } catch (e) { f = 'blocked: ' + e.name } return {origin: location.origin, fetch: f, cookie: (() => { try { return document.cookie.length } catch (e) { return 'blocked: ' + e.name } })()} }"""))
                except Exception as e:  # noqa: BLE001
                    results.setdefault("frames", []).append(f"EXC {str(e)[:80]}")
        page.goto(pages["interactive-frame"])
        page.wait_for_timeout(1500)
        results["interactive-direct"] = page.evaluate("""async () => { let f; try { f = (await fetch('/litstorm/api/me')).status } catch (e) { f = 'blocked: ' + e.name } return {origin: String(location.origin), fetch: f, cookie: (() => { try { return document.cookie.length } catch (e) { return 'blocked: ' + e.name } })()} }""")
        # live observatory: a request to another origin is blocked by CSP
        page.goto(pages["observatory-live"])
        page.wait_for_timeout(1500)
        results["observatory-fetch"] = page.evaluate("""async () => { try { await fetch('https://example.org'); return 'allowed' } catch (e) { return 'blocked: ' + e.name } }""")
        results["dialogs-user"] = fired
        results["requests-to-other-hosts"] = sorted(set(outside))
        ctx.close()
        # admin pages: the status page, the Settings > users? (names are the payload only where the user typed them)
        ctx, apage, fired2 = login(cc)
        for name, url in (("status", f"{L.BASE}/status"), ("home-admin", f"{L.BASE}/"),
                          ("observatory-failed", f"{L.BASE}/api/runs/{run_id}/observatory")):
            try:
                results["admin-" + name] = alerts_page(apage, url, fired2)
            except Exception as e:  # noqa: BLE001
                results["admin-" + name] = f"EXC {str(e)[:100]}"
            apage.screenshot(path=str(SHOTS / f"t7-xss-admin-{name}.png"))
        results["dialogs-admin"] = fired2
        ctx.close()
        b.close()
    print(json.dumps(results, ensure_ascii=False, indent=1))
    # put the edited files back right away
    for key, text in o["edited"].items():
        run, name = key[:36], key[36:]
        put_file(run, name, text)
    o["edited"] = {}
    keep(o)
    print("files restored")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["stub-on", "stub-off", "api", "queue", "blank", "xss"])
    a = p.parse_args()
    try:
        {"stub-on": cmd_stub_on, "stub-off": cmd_stub_off, "api": cmd_api, "queue": cmd_queue, "blank": cmd_blank, "xss": cmd_xss}[a.cmd](a)
    finally:
        if a.cmd == "xss":  # whatever happened, the two edited files go back
            o = odd()
            for key, text in o.get("edited", {}).items():
                put_file(key[:36], key[36:], text)
            o["edited"] = {}
            keep(o)
