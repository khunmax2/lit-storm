"""Task 5 of the 2026-10-24 audit: live Runs of every mode on the throwaway audit stack.

Not part of pytest. It needs the audit stack (http://127.0.0.1:8098/litstorm), the key files and
a creds file; it spends real money, so every Run is gated by spend.py.

    cd server && uv run python tests/audit/live_runs.py <command> ...

    creds                      make creds.json with random test passwords (once)
    setup                      first-run setup of the Administrator and the User through the web UI (Playwright)
    configure [--mra-key-file F]   key, model, search, Medical settings (as the Administrator, over the API)
    run  ENGINE TOPIC LANG DEPTH [--medical quick|full] [--model ID]    one Run as the User, followed to its end
    disc TOPIC LANG [--turns N]                            Co-STORM: open + N Turns
    export RUN_ID              every export format of a finished Run, with a sanity check
    mcp  RUN_ID                the MCP tools of the research and medical servers, on a finished Run
    scan                       count key-like strings in logs, Run messages and stderr.log (counts only)
    spend                      the spend gate

Secrets: passwords live in CREDS (the scratch dir) only; the OpenRouter key is read from stack/.env
and sent to the API, never printed; screenshots are taken only of pages that show none.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = Path(os.environ.get(
    "AUDIT_SCRATCH",
    "C:/Users/khunc/AppData/Local/Temp/claude/d--Vscode-deep-research-lit-lit-storm/"
    "4b811a66-2162-416e-bff5-2b95cc46f858/scratchpad/audit",
))
CREDS = SCRATCH / "creds.json"
BASE = os.environ.get("AUDIT_BASE", "http://127.0.0.1:8098/litstorm")
ADMIN = "audit-admin@example.org"
USER = "audit-user@example.org"
MODEL = "google/gemini-2.5-flash-lite"
STOP_AT, NO_START_AT = 6.80, 6.75
FINAL = ("succeeded", "failed", "interrupted", "cancelled")
TIMEOUT = 25 * 60


def creds():
    return json.loads(CREDS.read_text(encoding="utf-8"))


def read_env(path, name):
    for line in open(path, encoding="utf-8"):
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"no {name} in {path}")


class Api:
    """A signed-in client; the CSRF header comes from the cookie."""

    def __init__(self, who):
        self.s = requests.Session()
        c = creds()[who]
        r = self.s.post(f"{BASE}/api/auth/login", json={"email": c["email"], "password": c["password"]}, timeout=30)
        r.raise_for_status()

    def call(self, method, path, **kw):
        csrf = self.s.cookies.get("litstorm_csrf")
        r = self.s.request(method, f"{BASE}/api{path}", headers={"X-CSRF-Token": csrf or ""}, timeout=120, **kw)
        return r

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, **kw):
        return self.call("POST", path, **kw)

    def put(self, path, **kw):
        return self.call("PUT", path, **kw)


# --- spend gate -----------------------------------------------------------------------------


def spend():
    out = subprocess.run(
        [sys.executable, str(HERE / "spend.py"), str(ROOT / "stack/.env"), str(ROOT.parent / "MedicalReviewerAgent/.env")],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["total_usd"])


def gate():
    total = spend()
    print(f"total_usd={total}")
    if total >= NO_START_AT:
        raise SystemExit(f"budget: total {total} >= {NO_START_AT}, not starting")
    return total


# --- commands -------------------------------------------------------------------------------


def cmd_creds(_):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if CREDS.exists():
        print("creds.json exists")
        return
    data = {k: {"email": e, "password": secrets.token_urlsafe(14) + "aA1!"} for k, e in (("admin", ADMIN), ("user", USER))}
    CREDS.write_text(json.dumps(data), encoding="utf-8")
    print("creds.json written")


def cmd_setup(_):
    sys.path.insert(0, str(ROOT / "server/tests"))
    import ui
    from playwright.sync_api import sync_playwright

    c = creds()
    code = (ROOT / "stack/secrets/bootstrap_code").read_text().strip()
    shots = SCRATCH / "shots"
    shots.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page.goto(BASE)
        page.wait_for_url(re.compile(r"/setup"))
        page.screenshot(path=str(shots / "01-setup-empty.png"))  # no values typed yet
        ui.setup(page, BASE, code, "ผู้ดูแลทดสอบ", c["admin"]["email"], c["admin"]["password"])
        link = ui.new_user(page, BASE, c["user"]["email"], "ผู้ใช้ทดสอบ")  # never printed
        page2 = browser.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page2.goto(link)
        page2.locator("#password").fill(c["user"]["password"])
        page2.get_by_role("button").filter(has_text=re.compile("บันทึก|ตั้งรหัส|ยืนยัน")).first.click()
        page2.wait_for_timeout(3000)
        browser.close()
    print("setup done")


def cmd_configure(a):
    api = Api("admin")
    key = read_env(ROOT / "stack/.env", "OPENROUTER_API_KEY")
    r = api.put("/admin/llm-credentials/openrouter", json={"api_key": key})
    print("credential", r.status_code)
    models = api.get("/admin/llm-models").json()
    if not any(m["model"] == MODEL for m in models):
        r = api.post("/admin/llm-models", json={
            "label": "Gemini 2.5 Flash Lite", "provider": "openrouter", "model": MODEL,
            "enabled": True, "is_default": True, "reasoning": "", "max_tokens": {},
        })
        print("model", r.status_code, r.text[:200] if not r.ok else "")
    search = api.get("/admin/search-providers").json()
    print("search providers", [(p["kind"], p["is_default"], p["enabled"]) for p in search])
    if a.mra_key_file:
        mra = re.search(r"mra_\S+", Path(a.mra_key_file).read_text()).group(0)
        r = api.put("/admin/medical", json={"url": "http://host.docker.internal:8088", "api_key": mra})
        print("medical", r.status_code, {k: v for k, v in r.json().items() if k != "api_key"} if r.ok else r.text[:200])
        print("medical check", api.post("/admin/medical/check").json())
    print("options", [e["id"] if isinstance(e, dict) and "id" in e else e for e in api.get("/options").json().get("engines", [])])


def follow(api, run_id, admin=None, label=""):
    start = time.time()
    last = None
    while True:
        d = api.get(f"/runs/{run_id}").json()
        mark = (d["status"], d["stage"])
        if mark != last:
            print(f"  [{int(time.time() - start):4d}s] {d['status']} {d['stage']}")
            last = mark
        if d["status"] in FINAL:
            break
        if time.time() - start > TIMEOUT:
            api.post(f"/runs/{run_id}/cancel")
            print("  TIMEOUT: cancelled")
            time.sleep(10)
            d = api.get(f"/runs/{run_id}").json()
            break
        if int(time.time() - start) % 60 < 10 and spend() >= STOP_AT:  # the budget guard, also mid-Run
            api.post(f"/runs/{run_id}/cancel")
            print("  BUDGET: total >= 6.80, cancelled")
        time.sleep(10)
    return d, time.time() - start


def summarise(run, seconds, admin):
    row = next((r for r in admin.get("/admin/runs", params={"limit": 50}).json() if r["id"] == run["id"]), {})
    out = {
        "run": run["id"], "engine": run["engine"], "language": run["language"], "depth": run["depth"],
        "status": run["status"], "reason": run["reason"], "stage": run["stage"], "seconds": round(seconds),
        "sources": run["source_count"], "title": run["report_title"],
        "cost_usd": row.get("cost_usd"), "tokens": [row.get("tokens_in"), row.get("tokens_out")],
        "search_calls": row.get("search_calls"), "notes": list((run.get("notes") or {}).keys()),
        "message_len": len(run["message"] or ""),
    }
    print(json.dumps(out, ensure_ascii=False))
    return out


def cmd_run(a):
    before = gate()
    api, admin = Api("user"), Api("admin")
    body = {"topic": a.topic, "language": a.lang, "depth": a.depth, "engine": a.engine,
            "request_key": secrets.token_hex(8)}
    if a.model:
        body["llm_model_id"] = a.model
    if a.medical:
        body["medical"] = {"mode": a.medical}
    r = api.post("/sessions", json=body)
    if not r.ok:
        raise SystemExit(f"start refused {r.status_code} {r.text[:300]}")
    run = r.json()["runs"][0]
    print("started", run["id"])
    done, secs = follow(api, run["id"])
    out = summarise(done, secs, admin)
    after = spend()
    print(f"total_usd={after} delta={after - before:.4f}")
    if after >= STOP_AT:
        print("BUDGET STOP: total >= 6.80")
    return out


def cmd_disc(a):
    before = gate()
    api, admin = Api("user"), Api("admin")
    r = api.post("/discussions", json={"topic": a.topic, "language": a.lang, "depth": "fast", "request_key": secrets.token_hex(8),
                                        **({"llm_model_id": a.model} if a.model else {})})
    if not r.ok:
        raise SystemExit(f"start refused {r.status_code} {r.text[:300]}")
    d = r.json()
    sid = d["id"]
    print("discussion", sid)
    ids = [x["id"] for x in d.get("turns", d.get("runs", []))] or []
    plan = [("open", None)] + [("say", a.say)] * a.turns
    for i, (what, text) in enumerate(plan):
        if what == "say":
            gate()
            r = api.post(f"/discussions/{sid}/turns", json={"action": "say", "text": text, "request_key": secrets.token_hex(8)})
            if not r.ok:
                print("turn refused", r.status_code, r.text[:300])
                break
            rid = r.json()["id"]
        else:
            g = api.get(f"/discussions/{sid}").json()
            rid = (g.get("turns") or g.get("runs"))[-1]["id"]
        done, secs = follow(api, rid)
        summarise(done, secs, admin)
        print(f"total_usd={spend()}")
    print("discussion", sid)


def cmd_export(a):
    api = Api("user")
    out = SCRATCH / "exports" / a.run_id[:8]
    out.mkdir(parents=True, exist_ok=True)
    for fmt in ("html", "md", "pdf", "interactive", "observatory"):
        for ev in ("false", "true"):
            r = api.get(f"/runs/{a.run_id}/export", params={"format": fmt, "evidence": ev})
            body = r.content
            text = body[:400000].decode("utf-8", "ignore") if fmt != "pdf" else ""
            bad = re.findall(r"Traceback|Internal Server Error|undefined|\[object Object\]|NaN", text)[:3]
            (out / f"{fmt}-ev{ev}.{ 'pdf' if fmt == 'pdf' else 'md' if fmt == 'md' else 'html'}").write_bytes(body)
            print(f"{fmt:12} evidence={ev:5} -> {r.status_code} {len(body):>9} bytes "
                  f"{r.headers.get('content-type', '')[:30]} bad={bad} pdf_ok={body[:5] == b'%PDF-' if fmt == 'pdf' else '-'}")
    r = api.get(f"/runs/{a.run_id}/report")
    print("report json", r.status_code, len(r.content))


def rpc(session, url, token, method, params=None, i=[0]):
    i[0] += 1
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r = requests.post(url, headers=h, json={"jsonrpc": "2.0", "id": i[0], "method": method, "params": params or {}}, timeout=180)
    text = r.text
    m = re.search(r"data: (\{.*\})", text)
    return r.status_code, json.loads(m.group(1) if m else text) if text.strip() else {}


def cmd_mcp(a):
    api = Api("user")
    r = api.post("/me/tokens", json={"name": "audit-mcp", "scopes": ["read", "research"], "days": 30})
    token = r.json()["token"]
    tid = r.json()["record"]["id"]
    print("token id", tid)
    for path, p, runid in (("/api/mcp", "research", a.run_id), ("/api/mcp/medical", "medical_research", a.medical_run)):
        url = BASE + path
        code, tools = rpc(None, url, token, "tools/list")
        names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        print(path, code, names)
        calls = {f"{p}_options": {}, f"{p}_list": {}}
        if runid:
            calls.update({f"{p}_status": {"id": runid, "wait_seconds": 1}, f"{p}_report": {"id": runid},
                          f"{p}_export": {"id": runid, "format": "md"}, f"{p}_events": {"id": runid}})
        for name in names:
            if name.endswith(("_start", "_cancel")):
                continue
            args = calls.get(name)
            if args is None:
                continue
            code, res = rpc(None, url, token, "tools/call", {"name": name, "arguments": args})
            res_s = json.dumps(res, ensure_ascii=False)
            err = res.get("error") or res.get("result", {}).get("isError")
            print(f"  {name:28} http={code} error={bool(err)} bytes={len(res_s)} {res_s[:160] if err else ''}")
    api.call("DELETE", f"/me/tokens/{tid}")
    print("token revoked")


def cmd_scan(_):
    pat = re.compile(r"sk-or-[A-Za-z0-9_-]{8,}|\b[A-Za-z0-9_-]{40,}\b")
    sk = re.compile(r"sk-or-")

    def count(text):
        return len(sk.findall(text)), len(pat.findall(text))

    for c in ("litstorm-audit-api-1", "litstorm-audit-worker-1"):
        t = subprocess.run(["docker", "logs", c], capture_output=True, text=True).stdout
        t += subprocess.run(["docker", "logs", c], capture_output=True, text=True).stderr
        print(c, "sk-or / long-token counts:", count(t))
    admin = Api("admin")
    msgs = [r for r in admin.get("/admin/runs", params={"limit": 100}).json()]
    total = [0, 0]
    for r in msgs:
        d = admin.get(f"/runs/{r['id']}").json()
        s, lg = count(json.dumps(d))
        total[0] += s
        total[1] += lg
    print("run details", len(msgs), "runs; counts:", tuple(total))
    ls = subprocess.run(["docker", "exec", "litstorm-audit-worker-1", "sh", "-c",
                         "find /data -name stderr.log 2>/dev/null | head -50 | xargs -r cat"], capture_output=True, text=True)
    print("stderr.log counts:", count(ls.stdout), "bytes", len(ls.stdout))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("creds")
    sub.add_parser("setup")
    sub.add_parser("scan")
    sub.add_parser("spend")
    c = sub.add_parser("configure")
    c.add_argument("--mra-key-file")
    r = sub.add_parser("run")
    r.add_argument("engine")
    r.add_argument("topic")
    r.add_argument("lang")
    r.add_argument("depth")
    r.add_argument("--medical", choices=["quick", "full"])
    r.add_argument("--model", help="llm model id; the default model when absent")
    d = sub.add_parser("disc")
    d.add_argument("topic")
    d.add_argument("lang")
    d.add_argument("--turns", type=int, default=1)
    d.add_argument("--model")
    d.add_argument("--say", default="ช่วยสรุปประเด็นสำคัญที่สุดให้หน่อย")
    e = sub.add_parser("export")
    e.add_argument("run_id")
    m = sub.add_parser("mcp")
    m.add_argument("run_id")
    m.add_argument("--medical-run", default="")
    a = p.parse_args()
    {"creds": cmd_creds, "setup": cmd_setup, "configure": cmd_configure, "run": cmd_run, "disc": cmd_disc,
     "export": cmd_export, "mcp": cmd_mcp, "scan": cmd_scan, "spend": lambda _: print(spend())}[a.cmd](a)


if __name__ == "__main__":
    main()
