"""Who may call every endpoint: the access matrix (full audit, 2026-10-24).

ACCESS gives every endpoint of the app an access class: each HTTP route by
(method, path), and each MCP tool by ("TOOL", "<server path>#<tool name>"),
because a token's scopes are checked tool by tool behind one route. A class
comes from the documents, never from what the code happens to do:

- public: no sign-in. Setting up the first Administrator and setting a
  password from a link (docs/web-app-design.md, 2026-09-23), the health check
  (docs/deploy/HOST-203.md), an export link, which is its own permission
  (docs/adr/0009 §7).
- signed_in: any signed-in person ("ผู้ใช้ต้องล็อกอินเพื่อเข้าใช้งานเว็บ").
- owner: only the owner of the Project, topic, Run or token in the path.
  Anyone else gets the 404 a missing id gets (deps.own), an Administrator
  too: they do not read a person's research (2026-09-23; 2026-10-24, when
  Support Access Grants went). They do read an integration account's,
  which no person owns (docs/adr/0009 §4).
- admin: Administrators only, and never through a token (ADR-0009 §3).
- token:read, token:research: a live MCP token, never the web's cookie
  (ADR-0009 §6, and its rejected alternatives). A tool's cell names the
  scope it needs: read lists, follows and reads; research starts and
  cancels (§3). An MCP path itself is token:read: its door lets in any
  live token, and what each scope may do is the tools' to check.
- undecided: the documents do not say. Not tested, so that nothing today's
  code does is locked in as right; docs/reports/audit-2026-10-24/
  authz-matrix.md asks the owner.

Every class has its checks (CHECKS). A check that fails is a finding of the
audit, marked xfail(strict) with its id in FINDINGS: the file passes while
the bug is there and fails once it is fixed, to have the mark taken off.

The checks share one set of accounts and research, made once for the file
(`world`): conftest's fixtures start from empty tables for every test, and
the matrix has hundreds of checks.
"""

import json
import re
import secrets
import uuid
from types import SimpleNamespace

import pytest

from conftest import Browser, make_user

pytestmark = pytest.mark.db

CLASSES = {"public", "signed_in", "owner", "admin", "token:read", "token:research", "undecided"}

# The MCP servers (docs/adr/0009 §9) and their tools' prefix.
MCP_SERVERS = {
    "/api/mcp": "research",
    "/api/mcp/storm": "storm_research",
    "/api/mcp/deep": "deep_research",
    "/api/mcp/agent": "agent_research",
    "/api/mcp/medical": "medical_research",
}
# What each tool needs (ADR-0009 §3, ADR-0010 for events: a Run's status
# and events, as its owner sees them).
TOOL_CLASSES = {
    "start": "token:research",
    "cancel": "token:research",
    "status": "token:read",
    "report": "token:read",
    "export": "token:read",
    "list": "token:read",
    "events": "token:read",
    # Lists depths, sources, models and the quota left; the documents give
    # it no scope (the Connections page's test button calls it).
    "options": "undecided",
}

ACCESS: dict[tuple[str, str], str] = {
    # --- FastAPI's own pages (outside /api, which is all nginx forwards) ---
    ("GET", "/openapi.json"): "undecided",
    ("GET", "/docs"): "undecided",
    ("GET", "/docs/oauth2-redirect"): "undecided",
    ("GET", "/redoc"): "undecided",
    # --- signing in (api/auth.py; ADR-0002; design 2026-09-23) ---
    ("GET", "/api/health"): "public",
    ("GET", "/api/setup"): "public",
    ("POST", "/api/setup"): "public",  # the bootstrap code from a Docker secret is the permission
    ("POST", "/api/auth/login"): "public",
    ("POST", "/api/auth/logout"): "undecided",  # changes data without the CSRF header ADR-0002 asks for
    ("POST", "/api/auth/password-link"): "public",  # the link is the permission
    ("POST", "/api/auth/password"): "public",
    ("GET", "/api/me"): "signed_in",
    ("PUT", "/api/me/language"): "signed_in",
    # --- an Administrator's (api/admin.py) ---
    ("GET", "/api/admin/users"): "admin",
    ("POST", "/api/admin/users"): "admin",
    ("POST", "/api/admin/users/{user_id}/link"): "admin",
    ("PATCH", "/api/admin/users/{user_id}"): "admin",
    ("DELETE", "/api/admin/users/{user_id}"): "admin",
    ("GET", "/api/admin/llm-credentials"): "admin",
    ("PUT", "/api/admin/llm-credentials/{provider}"): "admin",
    ("DELETE", "/api/admin/llm-credentials/{provider}"): "admin",
    ("GET", "/api/admin/llm-models"): "admin",
    ("POST", "/api/admin/llm-models"): "admin",
    ("PUT", "/api/admin/llm-models/{model_id}"): "admin",
    ("POST", "/api/admin/llm-models/{model_id}/test"): "admin",
    ("POST", "/api/admin/llm-models/check"): "admin",
    ("GET", "/api/admin/search-providers"): "admin",
    ("POST", "/api/admin/search-providers"): "admin",
    ("PUT", "/api/admin/search-providers/{provider_id}"): "admin",
    ("POST", "/api/admin/search-providers/{provider_id}/test"): "admin",
    ("POST", "/api/admin/search-providers/check"): "admin",
    ("GET", "/api/admin/model-roles"): "admin",
    ("PUT", "/api/admin/model-roles"): "admin",
    ("GET", "/api/admin/embedding"): "admin",
    ("PUT", "/api/admin/embedding"): "admin",
    ("POST", "/api/admin/embedding/check"): "admin",
    ("GET", "/api/admin/engines"): "admin",
    ("PUT", "/api/admin/engines/{engine}"): "admin",
    ("GET", "/api/admin/usage"): "admin",
    ("GET", "/api/admin/runs"): "admin",
    ("GET", "/api/admin/monitor"): "admin",
    ("GET", "/api/admin/monitor/open"): "admin",
    ("POST", "/api/admin/monitor/acknowledge"): "admin",
    ("GET", "/api/admin/limits"): "admin",
    ("PUT", "/api/admin/limits"): "admin",
    # --- research (api/research.py): Projects, topics, Runs, the Trash ---
    ("GET", "/api/options"): "signed_in",
    ("GET", "/api/projects"): "signed_in",
    ("POST", "/api/projects"): "signed_in",
    ("PATCH", "/api/projects/{project_id}"): "owner",
    ("GET", "/api/projects/{project_id}"): "owner",
    ("DELETE", "/api/projects/{project_id}"): "owner",
    ("POST", "/api/refine"): "signed_in",
    ("POST", "/api/sessions"): "signed_in",
    ("POST", "/api/projects/{project_id}/sessions"): "owner",
    ("GET", "/api/sessions/recent"): "signed_in",
    ("GET", "/api/sessions"): "signed_in",
    ("PATCH", "/api/sessions/{session_id}"): "owner",
    ("GET", "/api/sessions/{session_id}"): "owner",
    ("DELETE", "/api/sessions/{session_id}"): "owner",
    ("POST", "/api/sessions/{session_id}/runs"): "owner",
    ("POST", "/api/runs/{run_id}/selection"): "owner",
    ("POST", "/api/runs/{run_id}/retry"): "owner",
    ("GET", "/api/me/quota"): "signed_in",
    ("GET", "/api/runs/{run_id}"): "owner",
    ("GET", "/api/runs/{run_id}/live"): "owner",
    ("POST", "/api/runs/{run_id}/cancel"): "owner",
    ("DELETE", "/api/runs/{run_id}"): "owner",
    ("GET", "/api/trash"): "signed_in",
    ("POST", "/api/trash/{kind}/{item_id}/restore"): "owner",
    # --- Reports (api/research.py; design 2026-09-23, 2026-10-01) ---
    ("GET", "/api/runs/{run_id}/report"): "owner",
    ("GET", "/api/runs/{run_id}/visuals"): "owner",
    ("POST", "/api/runs/{run_id}/visuals"): "owner",
    ("PATCH", "/api/runs/{run_id}/visuals"): "owner",
    ("GET", "/api/runs/{run_id}/interactive"): "owner",
    ("GET", "/api/runs/{run_id}/service-page"): "owner",
    ("GET", "/api/runs/{run_id}/observatory"): "owner",
    ("GET", "/api/runs/{run_id}/export"): "owner",
    ("GET", "/api/exports/{token}"): "public",
    # --- Discussions (api/discussions.py) ---
    ("POST", "/api/discussions"): "signed_in",
    ("GET", "/api/discussions/{session_id}"): "owner",
    ("POST", "/api/discussions/{session_id}/turns"): "owner",
    # --- tokens and integration accounts (api/tokens.py; ADR-0009) ---
    ("GET", "/api/me/connection"): "signed_in",
    ("GET", "/api/me/tokens"): "signed_in",
    ("POST", "/api/me/tokens"): "signed_in",
    ("DELETE", "/api/me/tokens/{token_id}"): "owner",
    ("GET", "/api/admin/mcp"): "admin",
    ("PUT", "/api/admin/mcp"): "admin",
    ("GET", "/api/admin/tokens"): "admin",
    ("DELETE", "/api/admin/tokens/{token_id}"): "admin",
    ("GET", "/api/admin/integrations"): "admin",
    ("POST", "/api/admin/integrations"): "admin",
    ("PATCH", "/api/admin/integrations/{account_id}"): "admin",
    ("POST", "/api/admin/integrations/{account_id}/tokens"): "admin",
    # --- Medical Review (api/medical.py; ADR-0013) ---
    ("GET", "/api/medical/status"): "signed_in",
    ("GET", "/api/admin/medical"): "admin",
    ("PUT", "/api/admin/medical"): "admin",
    ("POST", "/api/admin/medical/check"): "admin",
    # --- the MCP servers (api/mcp.py): any method, the door of TokenGate ---
    **{("*", path): "token:read" for path in MCP_SERVERS},
    **{
        ("TOOL", f"{path}#{prefix}_{tool}"): cls
        for path, prefix in MCP_SERVERS.items()
        for tool, cls in TOOL_CLASSES.items()
    },
}

# (cell, check) -> the finding it evidences, in
# docs/reports/audit-2026-10-24/authz-matrix.md.
FINDINGS: dict[tuple[tuple[str, str], str], str] = {
    # A switched-off account's token gets 401 "bad_token", not ADR-0009 §6's 403.
    **{(("*", path), "suspended_403"): "SEC-01" for path in MCP_SERVERS},
}

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
NOWHERE = "00000000-0000-4000-8000-000000000000"
NOT_YOURS = "No research with that id belongs to this account."
WITH_AN_ID = {"status", "report", "export", "cancel", "events"}
# GETs reading a Run or a topic on the web, which an Administrator may do
# for an integration account's (deps.readable).
READ_FOR_INTEGRATION = ("/api/runs/{run_id}", "/api/sessions/{session_id}")


def checks_for(key, cls):
    """The checks a cell's class asks of it, by name."""
    method, path = key
    if method == "TOOL":
        tool = path.rsplit("_", 1)[1]
        return ["missing_scope_refused", "scope_allowed"] + (
            ["other_user_refused", "admin_token_refused"] if tool in WITH_AN_ID else []
        )
    if cls.startswith("token:"):
        return ["no_token_401", "cookie_401", "unknown_token_401", "suspended_403", "token_admitted"]
    if cls == "public":
        return ["anonymous_allowed"]
    out = ["anonymous_401"]
    if cls == "admin":
        out += ["user_403", "admin_token_401"]
    if cls == "owner":
        out += ["other_user_404", "admin_404"]
    if method in UNSAFE:
        # Changes are not made to see that the right caller may: the
        # missing CSRF header shows the caller was recognised.
        out.append("no_csrf_403")
    else:
        out.append(f"{cls}_allowed")
        if cls == "admin":
            out.append("no_research_content")
        if cls == "owner" and path.startswith(READ_FOR_INTEGRATION):
            out.append("admin_reads_integration")
    return out


def _cells():
    for key, cls in ACCESS.items():
        if cls == "undecided":
            continue
        for check in checks_for(key, cls):
            finding = FINDINGS.get((key, check))
            marks = [pytest.mark.xfail(strict=True, raises=AssertionError, reason=finding)] if finding else []
            yield pytest.param(key, cls, check, id=f"{key[0]} {key[1]} | {check}", marks=marks)


# --- the accounts and research the checks use -----------------------------------

CODE = "authz-" + secrets.token_urlsafe(12)
PASSWORD = "authz " + secrets.token_urlsafe(12)
OFFLINE = {"reachable": False, "accepting": False, "reason": "unreachable: not asked in tests", "key_ok": None,
           "sources": []}


@pytest.fixture(scope="module")
def world(database_url, tmp_path_factory):
    """Empty tables, then: an Administrator; Alice with a Project, a topic
    whose Run has a report, a failed Run, a Project in the Trash, a
    Discussion and tokens of each scope; Bob, someone else; Carol, whose
    account is switched off after she made a token; and an integration
    account with a Run of its own. Medical Review is set up, so every MCP
    server is open, and is never asked (OFFLINE)."""
    from sqlalchemy import text

    from litstorm import db as db_mod
    from litstorm import settings
    from litstorm.db.models import Base

    with db_mod.engine().begin() as conn:  # as conftest's db fixture does
        names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} CASCADE"))
    code = tmp_path_factory.mktemp("authz") / "code"
    code.write_text(CODE + "\n")
    patch = pytest.MonkeyPatch()
    try:
        yield from _world(patch, code)
    finally:
        patch.undo()
        settings.get.cache_clear()


def _world(patch, code):
    from fastapi.testclient import TestClient
    from sqlalchemy import update

    from litstorm import db as db_mod
    from litstorm import medical, settings
    from litstorm.api import create_app
    from litstorm.api import medical as medical_api
    from litstorm.db.models import ResearchSession, Run
    from litstorm.render import interactive

    patch.setenv("LITSTORM_BOOTSTRAP_CODE_FILE", str(code))
    settings.get.cache_clear()
    patch.setattr(medical, "check", lambda url, api_key, timeout=5.0: dict(OFFLINE))
    patch.setattr(medical_api, "_status", {"at": 0.0, "url": None, "value": None})  # its cache, ours alone
    # Charts are drawn in a browser the tests do not have (test_api_visuals).
    patch.setattr(interactive, "prerender", lambda specs: ["<svg></svg>"] * len(specs))

    def browser():
        return Browser(TestClient(create_app()))

    def ok(response, status=(200, 201, 204)):
        assert response.status_code in status, response.text
        return response.json() if response.content else None

    admin = browser()
    ok(admin.post("/api/setup", json={"code": CODE, "email": "admin@example.org", "name": "Admin", "password": PASSWORD}))
    ok(admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"}))
    model = ok(admin.post("/api/admin/llm-models",
                          json={"label": "Flash", "provider": "openrouter", "model": "g/flash", "is_default": True}))
    search = ok(admin.post("/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True}))
    ok(admin.put("/api/admin/medical", json={"url": "http://mra.test.local", "api_key": "mra-test-key"}))

    alice = make_user(admin, browser, "alice@example.org", PASSWORD)
    bob = make_user(admin, browser, "bob@example.org", PASSWORD)
    carol = make_user(admin, browser, "carol@example.org", PASSWORD)
    # Its tag alone gives a topic away, escaped or cut short; no id is made of it.
    tag = f"topicmark{secrets.token_hex(4)}"
    mark = f"Alice's private topic {tag}"

    project = ok(alice.post("/api/projects", json={"name": "Alice's project"}))["id"]
    topic = ok(alice.post(f"/api/projects/{project}/sessions", json={"topic": mark, "language": "en"}))
    failed = ok(alice.post("/api/sessions", json={"topic": mark, "language": "en"}))["runs"][0]["id"]
    trashed = ok(alice.post("/api/projects", json={"name": "Alice's old project"}))["id"]
    ok(alice.delete(f"/api/projects/{trashed}"))
    discussion = ok(alice.post("/api/discussions", json={"topic": mark, "language": "en"}))["id"]
    bobs = ok(bob.post("/api/sessions", json={"topic": "Bob's own topic", "language": "en"}))["id"]

    def token(user, scopes, name="authz"):
        return ok(user.post("/api/me/tokens", json={"name": name, "scopes": scopes, "days": 30}))

    tokens = SimpleNamespace(
        alice_read=token(alice, ["read"])["token"],
        alice_research=token(alice, ["research"])["token"],
        bob=token(bob, ["read", "research"])["token"],
        carol=token(carol, ["read", "research"])["token"],
        admin=token(admin, ["read", "research"])["token"],
    )
    spare = token(alice, ["read"], "spare")["record"]["id"]
    ok(admin.patch(f"/api/admin/users/{ok(carol.get('/api/me'))['id']}", json={"is_active": False}))

    # An integration account's Run: made as Alice's, then handed over, as no
    # one signs in as the account.
    account = uuid.UUID(ok(admin.post("/api/admin/integrations", json={"name": "Integration (authz test)"}))["id"])
    handed = ok(alice.post("/api/sessions", json={"topic": "An integration's topic", "language": "en"}))

    with db_mod.sessions()() as s:
        s.execute(update(ResearchSession).where(ResearchSession.id == uuid.UUID(handed["id"])).values(owner_id=account))
        s.execute(update(Run).where(Run.session_id == uuid.UUID(handed["id"])).values(owner_id=account))
        s.commit()
        for run_id in (topic["runs"][0]["id"], handed["runs"][0]["id"]):
            _succeeded(s, run_id)
        _failed(s, failed, f"Failed while researching {mark}. Last error: Too Many Requests")

    # The MCP servers' session managers run in this client's lifespan.
    with TestClient(create_app()) as mcp:
        yield SimpleNamespace(
            admin=admin, alice=alice, bob=bob, anon=TestClient(create_app()), mcp=mcp, tokens=tokens, tag=tag,
            project=project, session=topic["id"], run=topic["runs"][0]["id"], trashed=trashed,
            discussion=discussion, spare_token=spare, bobs_session=bobs, model=model["id"], search=search["id"],
            integration_session=handed["id"], integration_run=handed["runs"][0]["id"],
        )


def _succeeded(s, run_id):
    """A Run marked finished, with the fake engine's report on disk."""
    import os
    from datetime import datetime, timedelta, timezone

    from litstorm import settings
    from litstorm.db.models import Run
    from litstorm.engines.fake import sample_report

    run = s.get(Run, uuid.UUID(run_id))
    now = datetime.now(timezone.utc)
    run.status, run.started_at, run.finished_at = "succeeded", now - timedelta(minutes=3), now
    s.commit()
    folder = os.path.join(settings.get().runs_dir, run_id)
    os.makedirs(folder, exist_ok=True)
    report = sample_report(SimpleNamespace(topic=run.topic, language="en"))
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)


def _failed(s, run_id, message):
    """A Run the system failed, as the Worker ends one (test_monitor.ended)."""
    from datetime import datetime, timedelta, timezone

    from litstorm.db.models import Run

    run = s.get(Run, uuid.UUID(run_id))
    finished = datetime.now(timezone.utc) - timedelta(minutes=5)
    run.status, run.reason, run.message, run.engine = "failed", "retries_exhausted", message, "deep"
    run.started_at, run.finished_at = finished - timedelta(minutes=3), finished
    s.commit()


# --- calling an endpoint as someone ---------------------------------------------------

QUERY = {("GET", "/api/runs/{run_id}/export"): "?format=md"}
# Bodies good enough to get past validation to the owner check.
BODIES = {
    ("PATCH", "/api/projects/{project_id}"): lambda w: {"name": "Renamed by someone"},
    ("POST", "/api/projects/{project_id}/sessions"): lambda w: {"topic": "Someone's topic", "language": "en"},
    ("PATCH", "/api/sessions/{session_id}"): lambda w: {"project_id": None},
    ("POST", "/api/sessions/{session_id}/runs"): lambda w: {"topic": "Once more", "language": "en"},
    ("POST", "/api/runs/{run_id}/selection"): lambda w: {"llm_model_id": w.model, "search_provider_id": w.search},
    ("PATCH", "/api/runs/{run_id}/visuals"): lambda w: {"hidden": []},
    ("POST", "/api/discussions/{session_id}/turns"): lambda w: {"action": "say", "text": "Hello"},
}
REFUSED = {"not_signed_in", "csrf", "admin_only"}


def _url(w, key, integration=False):
    path = key[1]

    def value(name):
        if path.startswith("/api/admin/"):
            return NOWHERE  # nothing an Administrator's handler should ever reach in these checks
        if name == "session_id" and path.startswith("/api/discussions/"):
            return w.discussion
        return {
            "project_id": w.project,
            "session_id": w.integration_session if integration else w.session,
            "run_id": w.integration_run if integration else w.run,
            "kind": "project",
            "item_id": w.trashed,
            "token_id": w.spare_token,
            "token": "not-a-link",
        }[name]

    return re.sub(r"\{(\w+)\}", lambda m: value(m.group(1)), path) + QUERY.get(key, "")


def _send(w, who, key, csrf=True, integration=False, headers=None):
    """`key`'s request as `who` (a conftest.Browser; None: no one)."""
    body = BODIES.get(key)
    kw = {"json": body(w)} if body else {}
    if who is None:
        w.anon.cookies.clear()
        return w.anon.request(key[0], _url(w, key, integration), headers=headers, **kw)
    sent = {**(who._headers() if csrf else {}), **(headers or {})}
    return who.client.request(key[0], _url(w, key, integration), headers=sent, **kw)


def _detail(response):
    """The API's refusal code ("not_found", "csrf", ...), if it sent one."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return None
    return detail if isinstance(detail, str) else None


def _reached(response):
    """Past every check of who may call: not refused, and not the 404 of
    someone else's id."""
    return response.status_code not in (401, 403) and not (
        response.status_code == 404 and _detail(response) == "not_found"
    )


def _mcp(w, path, token=None, method="tools/list", params=None, headers=None):
    from litstorm.api import mcp

    mcp._CALLS.clear()  # the 60-a-minute guard: this file calls far more often, on purpose
    sent = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", **(headers or {})}
    if token:
        sent["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return w.mcp.post(path, headers=sent, content=json.dumps(body))


def _answer(response):
    """The JSON-RPC result of one MCP request, sent as JSON or as an event."""
    assert response.status_code == 200, response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                message = json.loads(line[5:])
                if message.get("id") == 1:
                    return message["result"]
        raise AssertionError(response.text)
    return response.json()["result"]


TOOL_ARGS = {
    "options": lambda w: {},
    "start": lambda w: {"topic": "x", "wait_seconds": 0},  # too short: refused after the scope, starts nothing
    "status": lambda w: {"id": w.run, "wait_seconds": 0},
    "report": lambda w: {"id": w.run},
    "export": lambda w: {"id": w.run, "format": "md"},
    "list": lambda w: {},
    "cancel": lambda w: {"id": w.run},  # finished: nothing to cancel
    "events": lambda w: {"id": w.run},
}


def _tool(w, key, token):
    """The tool's result: (whether it is an error, its text)."""
    path, name = key[1].split("#")
    result = _answer(_mcp(w, path, token, "tools/call",
                          {"name": name, "arguments": TOOL_ARGS[name.rsplit("_", 1)[1]](w)}))
    return bool(result.get("isError")), " ".join(c.get("text", "") for c in result.get("content", []))


# --- the checks -------------------------------------------------------------------------


def _anonymous_allowed(w, key, cls):
    r = _send(w, None, key)
    assert r.status_code != 401 and _detail(r) not in REFUSED, (r.status_code, r.text)


def _anonymous_401(w, key, cls):
    r = _send(w, None, key)
    assert r.status_code == 401, (r.status_code, r.text)


def _user_403(w, key, cls):
    r = _send(w, w.alice, key)
    assert (r.status_code, _detail(r)) == (403, "admin_only"), (r.status_code, r.text)


def _admin_token_401(w, key, cls):
    """An Administrator's MCP token is no Administrator (ADR-0009 §3)."""
    r = _send(w, None, key, headers={"Authorization": f"Bearer {w.tokens.admin}"})
    assert r.status_code == 401, (r.status_code, r.text)


def _other_user_404(w, key, cls):
    r = _send(w, w.bob, key)
    assert (r.status_code, _detail(r)) == (404, "not_found"), (r.status_code, r.text)


def _admin_404(w, key, cls):
    r = _send(w, w.admin, key)
    assert (r.status_code, _detail(r)) == (404, "not_found"), (r.status_code, r.text)


def _no_csrf_403(w, key, cls):
    who = w.admin if cls == "admin" else w.alice  # someone who may, but sends no CSRF header
    r = _send(w, who, key, csrf=False)
    assert (r.status_code, _detail(r)) == (403, "csrf"), (r.status_code, r.text)


def _allowed_as(who):
    def check(w, key, cls):
        r = _send(w, getattr(w, who), key)
        assert _reached(r), (r.status_code, r.text[:500])

    return check


def _no_research_content(w, key, cls):
    """What an Administrator reads carries no person's topic (design
    2026-09-23; CONTEXT: System status)."""
    r = _send(w, w.admin, key)
    assert _reached(r) and w.tag not in r.text, r.text[:500]


def _admin_reads_integration(w, key, cls):
    r = _send(w, w.admin, key, integration=True)
    assert _reached(r), (r.status_code, r.text[:500])


def _no_token_401(w, key, cls):
    r = _mcp(w, key[1])
    assert r.status_code == 401 and "Bearer" in r.headers.get("www-authenticate", ""), (r.status_code, r.text)


def _cookie_401(w, key, cls):
    """Signed in on the web, with its CSRF header, is still no token."""
    cookies = w.alice.client.cookies
    r = _mcp(w, key[1], headers={
        "Cookie": f"litstorm_session={cookies.get('litstorm_session')}; litstorm_csrf={cookies.get('litstorm_csrf')}",
        **w.alice._headers(),
    })
    assert r.status_code == 401, (r.status_code, r.text)


def _unknown_token_401(w, key, cls):
    r = _mcp(w, key[1], "dlk_" + "x" * 43)
    assert r.status_code == 401, (r.status_code, r.text)


def _suspended_403(w, key, cls):
    """ADR-0009 §6: an account switched off gets 403 at the door."""
    r = _mcp(w, key[1], w.tokens.carol)
    assert r.status_code == 403, (r.status_code, r.text)


def _token_admitted(w, key, cls):
    assert _answer(_mcp(w, key[1], w.tokens.alice_read))["tools"]


def _scope(cls):
    return cls.split(":", 1)[1]


def _missing_scope_refused(w, key, cls):
    scope = _scope(cls)
    lacking = w.tokens.alice_research if scope == "read" else w.tokens.alice_read
    error, said = _tool(w, key, lacking)
    assert error and f"lacks the '{scope}' scope" in said, said


def _scope_allowed(w, key, cls):
    scope = _scope(cls)
    error, said = _tool(w, key, w.tokens.alice_read if scope == "read" else w.tokens.alice_research)
    assert not (error and "lacks the '" in said), said


def _other_user_refused(w, key, cls):
    error, said = _tool(w, key, w.tokens.bob)
    assert error and NOT_YOURS in said, said


def _admin_token_refused(w, key, cls):
    error, said = _tool(w, key, w.tokens.admin)
    assert error and NOT_YOURS in said, said


CHECKS = {
    "anonymous_allowed": _anonymous_allowed,
    "anonymous_401": _anonymous_401,
    "user_403": _user_403,
    "admin_token_401": _admin_token_401,
    "other_user_404": _other_user_404,
    "admin_404": _admin_404,
    "no_csrf_403": _no_csrf_403,
    "signed_in_allowed": _allowed_as("alice"),
    "owner_allowed": _allowed_as("alice"),
    "admin_allowed": _allowed_as("admin"),
    "no_research_content": _no_research_content,
    "admin_reads_integration": _admin_reads_integration,
    "no_token_401": _no_token_401,
    "cookie_401": _cookie_401,
    "unknown_token_401": _unknown_token_401,
    "suspended_403": _suspended_403,
    "token_admitted": _token_admitted,
    "missing_scope_refused": _missing_scope_refused,
    "scope_allowed": _scope_allowed,
    "other_user_refused": _other_user_refused,
    "admin_token_refused": _admin_token_refused,
}


# --- the tests ---------------------------------------------------------------------------


def _endpoints(w):
    """Every endpoint the app has: its routes, and each MCP server's tools."""
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:  # a FastAPI that lists every route on app.routes itself
        def iter_route_contexts(routes):
            return routes

    found = set()
    for route in iter_route_contexts(w.mcp.app.routes):
        methods = set(route.methods or ()) - {"HEAD"}
        found |= {(m, route.path) for m in methods or {"*"}}
    for path in [p for m, p in found if m == "*"]:
        tools = _answer(_mcp(w, path, w.tokens.alice_read))["tools"]
        found |= {("TOOL", f"{path}#{t['name']}") for t in tools}
    return found


def test_every_route_has_an_access_class(world):
    found = _endpoints(world)
    assert not found - ACCESS.keys(), f"endpoints with no access class: {sorted(found - ACCESS.keys())}"
    assert not ACCESS.keys() - found, f"classes of endpoints that are gone: {sorted(ACCESS.keys() - found)}"
    assert set(ACCESS.values()) <= CLASSES
    assert {check for key, cls in ACCESS.items() if cls != "undecided" for check in checks_for(key, cls)} <= CHECKS.keys()


@pytest.mark.parametrize("key, cls, check", list(_cells()))
def test_access_class_holds(world, key, cls, check):
    CHECKS[check](world, key, cls)


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/api/sessions", {"topic": "Bob's next topic", "language": "en"}),
    ("PATCH", "/api/sessions/{bobs_session}", {}),
    ("POST", "/api/discussions", {"topic": "Bob's talk", "language": "en"}),
], ids=["new topic", "move a topic", "new discussion"])
def test_a_body_cannot_name_another_users_project(world, method, path, body):
    """Filing into a Project is the owner's alone, named in the body too."""
    url = path.replace("{bobs_session}", world.bobs_session)
    r = world.bob.client.request(method, url, json={**body, "project_id": world.project}, headers=world.bob._headers())
    assert (r.status_code, _detail(r)) == (404, "not_found"), (r.status_code, r.text)
