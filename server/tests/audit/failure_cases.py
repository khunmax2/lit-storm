"""Task 6 of the 2026-10-24 audit: inject failures on the audit stack. Not part of pytest. No paid calls.

    cd server && uv run python tests/audit/stub_provider.py &          # the stand-in provider, :9099
    cd server && uv run python tests/audit/failure_cases.py prep       # stub credential + model + search row
    cd server && uv run python tests/audit/failure_cases.py case NAME  # 429 | 401 | worker | mra | search
    cd server && uv run python tests/audit/failure_cases.py restore    # put the Medical URL back, switch the stubs off

Each case starts one Run as the User, follows it to its end, and prints the Run card fields, the
System status Issues (/api/admin/monitor and /monitor/open) and quota_refunded, then screenshots the
Run's page (the page shows no secret). The audit stack's default model and search provider are not changed.
"""

import argparse
import json
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_runs as L  # noqa: E402

STUB = "http://host.docker.internal:9099"
STATE = L.SCRATCH / "failure_state.json"
SHOTS = L.SCRATCH / "shots"


def state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save(d):
    STATE.write_text(json.dumps(d), encoding="utf-8")


def set_base(admin, mode):
    r = admin.put("/admin/llm-credentials/openai-compatible", json={"api_key": "stub-key", "api_base": f"{STUB}/{mode}/v1"})
    assert r.ok, r.text


def search_body(mode, **kw):
    body = {"label": "AUDIT stub search", "kind": "searxng", "endpoint": f"{STUB}/{mode}/search", "enabled": True, "is_default": False}
    body.update(kw)
    return body


def cmd_prep(_):
    admin = L.Api("admin")
    st = state()
    st["medical"] = admin.get("/admin/medical").json()
    st["default_model"] = next((m["id"] for m in admin.get("/admin/llm-models").json() if m["is_default"]), None)
    st["default_search"] = next((p["id"] for p in admin.get("/admin/search-providers").json() if p["is_default"]), None)
    set_base(admin, "ok")
    r = admin.post("/admin/llm-models", json={"label": "AUDIT stub model", "provider": "openai-compatible", "model": "stub-model",
                                              "enabled": True, "is_default": False, "reasoning": "", "max_tokens": {}})
    assert r.ok, r.text
    st["model"] = r.json()["id"]
    r = admin.post("/admin/search-providers", json=search_body("ok"))
    assert r.ok, r.text
    st["search"] = r.json()["id"]
    save(st)
    print("prepared; medical url was", st["medical"].get("url"), "default model", st["default_model"])


def start(user, **extra):
    st = state()
    body = {"topic": "ผลของการนอนหลับต่อความจำ", "language": "th", "depth": "fast", "engine": "storm",
            "request_key": secrets.token_hex(8), "llm_model_id": st["model"]}
    body.update(extra)
    r = user.post("/sessions", json=body)
    if not r.ok:
        raise SystemExit(f"start refused {r.status_code} {r.text[:300]}")
    j = r.json()
    return j["runs"][0]["id"], j["runs"][0]["session_id"]


def monitor(admin):
    m = admin.get("/admin/monitor").json()
    keys = ("key", "reason", "severity", "engine", "count", "open", "message")
    return {"open_count": m["open_count"], "badge": admin.get("/admin/monitor/open").json(),
            "issues": [{k: i[k] for k in keys} for i in m["issues"]]}


def shot(session_id, name):
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(exist_ok=True)
    c = L.creds()["user"]
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        page = b.new_page(viewport={"width": 1280, "height": 860}, locale="th-TH")
        page.goto(f"{L.BASE}/login")
        page.locator("#email").fill(c["email"])
        page.locator("#password").fill(c["password"])
        page.get_by_role("button", name="เข้าสู่ระบบ").click()
        page.wait_for_url(re.compile(r"/$"))
        page.goto(f"{L.BASE}/sessions/{session_id}")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOTS / f"t6-{name}.png"))
        b.close()


def report(name, run_id, session_id, user, admin, secs):
    d = user.get(f"/runs/{run_id}").json()
    out = {"case": name, "run": run_id, "status": d["status"], "reason": d["reason"], "stage": d["stage"],
           "system_fault": d.get("system_fault"), "quota_refunded": d["quota_refunded"], "seconds": round(secs),
           "message": d["message"], "monitor": monitor(admin)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    shot(session_id, name)
    return out


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True).stdout.strip()


def cmd_case(a):
    admin, user = L.Api("admin"), L.Api("user")
    st = state()
    name = a.name
    t0 = time.time()
    if name in ("429", "401"):
        set_base(admin, name)
        rid, sid = start(user)
        L.follow(user, rid)
    elif name == "worker":
        set_base(admin, "slow")  # the model answers after 75 s, so the Run is mid-stage when the Worker dies
        rid, sid = start(user)
        for _ in range(40):
            if user.get(f"/runs/{rid}").json()["status"] == "running":
                break
            time.sleep(3)
        time.sleep(8)
        print("stop worker", docker("stop", "litstorm-audit-worker-1"))
        time.sleep(15)
        print("run while worker is down:", user.get(f"/runs/{rid}").json()["status"])
        print("start worker", docker("start", "litstorm-audit-worker-1"))
        L.follow(user, rid)
    elif name == "mra":
        original = st["medical"]["url"]
        r = admin.put("/admin/medical", json={"url": "http://host.docker.internal:9"})
        print("medical url ->", r.status_code)
        try:
            rid, sid = start(user, engine="medical", medical={"mode": "quick"}, language="en", topic="effects of sleep on memory")
            L.follow(user, rid)
        finally:
            r = admin.put("/admin/medical", json={"url": original})
            print("medical url restored", r.status_code, admin.get("/admin/medical").json().get("url") == original)
    elif name == "search":
        set_base(admin, "ok")
        r = admin.put(f"/admin/search-providers/{st['search']}", json=search_body("slow"))
        assert r.ok, r.text
        try:
            rid, sid = start(user, search_provider_id=st["search"])
            L.follow(user, rid)
        finally:
            admin.put(f"/admin/search-providers/{st['search']}", json=search_body("ok"))
    else:
        raise SystemExit("unknown case")
    report(name, rid, sid, user, admin, time.time() - t0)


def cmd_restore(_):
    admin = L.Api("admin")
    st = state()
    admin.put("/admin/medical", json={"url": st["medical"]["url"]})
    print("medical", admin.get("/admin/medical").json().get("url"))
    for m in admin.get("/admin/llm-models").json():
        if m["id"] == st.get("model"):
            m2 = {k: m[k] for k in ("label", "provider", "model", "reasoning", "max_tokens", "enabled", "is_default")}
            m2["enabled"] = False
            print("model disabled", admin.put(f"/admin/llm-models/{m['id']}", json=m2).status_code)
    for p in admin.get("/admin/search-providers").json():
        if p["id"] == st.get("search"):
            print("search disabled", admin.put(f"/admin/search-providers/{p['id']}", json=search_body("ok", enabled=False)).status_code)
    print("defaults unchanged:", [m["label"] for m in admin.get("/admin/llm-models").json() if m["is_default"]],
          [p["label"] for p in admin.get("/admin/search-providers").json() if p["is_default"]])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("prep")
    s.add_parser("restore")
    c = s.add_parser("case")
    c.add_argument("name")
    a = p.parse_args()
    {"prep": cmd_prep, "case": cmd_case, "restore": cmd_restore}[a.cmd](a)
