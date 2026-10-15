"""DeepLit's MCP server, called as a client would: the SDK's own client over
Streamable HTTP, against the app in process (api/mcp.py)."""

import asyncio
import json
import os
import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture

pytestmark = pytest.mark.db

URL = "http://test.local/api/mcp"


def _token(user, scopes=("read", "research")):
    r = user.post("/api/me/tokens", json={"name": "test", "scopes": list(scopes), "days": 30})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _call(token, steps, progress=None, url=URL):
    """Run `steps(session)` against a fresh app with an MCP client session."""
    from litstorm.api import create_app

    app = create_app()

    async def go():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), headers={"Authorization": f"Bearer {token}"}, timeout=60
            ) as http:
                async with streamable_http_client(url, http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return await steps(session)

    return asyncio.run(go())


def _data(result):
    """A tool result's payload: structured when there is one, else its text."""
    assert not result.isError, result.content[0].text
    if result.structuredContent is not None:
        content = result.structuredContent
        return content.get("result", content) if set(content) == {"result"} else content
    text = result.content[0].text
    try:
        return json.loads(text)
    except ValueError:
        return text


def _raw(token, body):
    """A plain HTTP request to the endpoint, as a misconfigured client sends."""
    from fastapi.testclient import TestClient

    from litstorm.api import create_app

    with TestClient(create_app()) as client:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = token
        return client.post("/api/mcp", headers=headers, content=json.dumps(body))


def test_no_token_no_server(admin, browser, db):
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    r = _raw(None, listing)
    assert r.status_code == 401 and r.json()["error"] == "no_token" and "Bearer" in r.headers["www-authenticate"]
    assert _raw("Bearer dlk_unknown", listing).json()["error"] == "bad_token"
    user = make_user(admin, browser)
    token = _token(user)
    admin.put("/api/admin/mcp", json={"enabled": False, "users_create_tokens": True})
    r = _raw(f"Bearer {token}", listing)
    assert r.status_code == 403 and r.json()["error"] == "mcp_disabled"


def test_the_tools_with_instructions(admin, browser):
    token = _token(make_user(admin, browser))

    async def steps(session):
        return (await session.list_tools()).tools

    tools = _call(token, steps)
    assert all(t.description == " ".join(t.description.split()) for t in tools)  # one clean line each
    assert sorted(t.name for t in tools) == sorted([
        "research_options", "research_start", "research_status", "research_report", "research_list", "research_cancel",
        "research_events", "research_export",
    ])
    # The MCP App: start and status are drawn on the canvas; its feed is for the canvas, not the model.
    meta = {t.name: (t.meta or {}).get("ui") for t in tools}
    assert meta["research_start"] == meta["research_status"] == {"resourceUri": "ui://deeplit/research-canvas.html"}
    assert meta["research_events"] == {"resourceUri": "ui://deeplit/research-canvas.html", "visibility": ["app"]}
    assert meta["research_report"] is None


def test_the_canvas_is_an_mcp_app_resource(admin, browser):
    token = _token(make_user(admin, browser), scopes=("read",))

    async def steps(session):
        listed = (await session.list_resources()).resources
        read = await session.read_resource("ui://deeplit/research-canvas.html")
        return listed, read.contents[0]

    listed, content = _call(token, steps)
    canvas = next(r for r in listed if str(r.uri) == "ui://deeplit/research-canvas.html")
    assert canvas.mimeType == "text/html;profile=mcp-app" and (canvas.meta or {})["ui"] == {"prefersBorder": True}
    assert content.mimeType == "text/html;profile=mcp-app"
    html = content.text
    assert html.startswith("<!doctype html>") and '"ui/initialize"' in html and '"research_events"' in html
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")  # nothing from the network
    assert "https://" not in html


def test_the_canvas_reads_a_runs_events_and_only_its_owners(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import Run, RunEvent

    user = make_user(admin, browser)
    token = _token(user, scopes=("read",))
    run_id = user.post("/api/sessions", json={"topic": "Songkran", "language": "en"}).json()["runs"][0]["id"]
    for type_, data in [
        ("stage", {"stage": "research"}),
        ("note", {"kind": "flow", "event": "plan", "sections": [{"id": "s1", "title": "History"}]}),
        ("note", {"kind": "flow", "event": "tasks", "lane": "s1", "round": 1, "queries": [{"agent": "search", "query": "q"}]}),
        ("note", {"kind": "traceback", "text": "for whoever debugs"}),
        ("note", {"kind": "browsed", "urls": ["https://example.org/a"]}),
    ]:
        db.add(RunEvent(run_id=run_id, type=type_, data=data))
    run = db.get(Run, run_id)
    run.status = "succeeded"
    db.commit()
    other = _token(make_user(admin, browser, email="someone@example.org"), scopes=("read",))

    async def steps(session):
        first = _data(await session.call_tool("research_events", {"id": run_id}))
        rest = _data(await session.call_tool("research_events", {"id": run_id, "after": first["after"]}))
        return first, rest

    first, rest = _call(token, steps)
    assert first["run"]["id"] == run_id and first["run"]["engine"] == "storm" and first["final"] is True
    # What the web shows the owner; a traceback stays in the database.
    assert [e["data"].get("kind", e["type"]) for e in first["events"]] == ["stage", "flow", "flow", "browsed"]
    assert rest["events"] == [] and rest["after"] == first["after"]

    async def theirs(session):
        return await session.call_tool("research_events", {"id": run_id})

    refused = _call(other, theirs)
    assert refused.isError and "No research with that id" in refused.content[0].text


def test_options_name_the_modes_sources_and_quota(admin, browser, configured):  # noqa: F811
    token = _token(make_user(admin, browser))

    async def steps(session):
        return _data(await session.call_tool("research_options", {}))

    options = _call(token, steps)
    assert "co-storm" not in [e["id"] for e in options["engines"]]  # Discussions are not offered here yet
    assert [s["label"] for s in options["search_providers"]] == ["TCI-ThaiJO", "arXiv"]
    assert options["quota"]["remaining"] == options["quota"]["limit"]


def test_a_run_started_through_mcp_is_followed_listed_and_cancelled(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import ApiToken, Run

    token = _token(make_user(admin, browser))
    seen = []

    async def steps(session):
        async def progress(done, total, message):
            seen.append((done, total, message))

        started = _data(await session.call_tool(
            "research_start", {"topic": "Songkran", "language": "th", "sources": ["arxiv"], "wait_seconds": 1},
            progress_callback=progress,
        ))
        status = _data(await session.call_tool("research_status", {"id": started["id"], "wait_seconds": 0}))
        listed = _data(await session.call_tool("research_list", {}))
        cancelled = _data(await session.call_tool("research_cancel", {"id": started["id"]}))
        return started, status, listed, cancelled

    started, status, listed, cancelled = _call(token, steps)
    assert started["status"] == "queued" and "research_status" in started["next"]  # no Worker here
    assert started["web_url"].endswith(f"/runs/{started['id']}")
    assert status["id"] == started["id"] and [r["id"] for r in listed] == [started["id"]]
    assert cancelled["status"] == "cancelled" and cancelled["quota_refunded"] is True
    assert seen and seen[0][2] == "queued"
    run = db.get(Run, started["id"])
    assert run.via_token_id == db.query(ApiToken).one().id  # for the Run card's badge


def test_a_read_token_cannot_start_research(admin, browser, configured):  # noqa: F811
    token = _token(make_user(admin, browser), scopes=["read"])

    async def steps(session):
        return await session.call_tool("research_start", {"topic": "Songkran"})

    result = _call(token, steps)
    assert result.isError and "'research' scope" in result.content[0].text


def test_refusals_say_what_is_wrong(admin, browser, configured):  # noqa: F811
    token = _token(make_user(admin, browser))

    async def steps(session):
        return [
            await session.call_tool("research_start", {"topic": "Songkran", "sources": ["nowhere"]}),
            await session.call_tool("research_start", {"topic": "Songkran", "mode": "co-storm"}),
            await session.call_tool("research_status", {"id": "not-an-id"}),
            await session.call_tool("research_status", {"id": "00000000-0000-0000-0000-000000000000"}),
        ]

    texts = [r.content[0].text for r in _call(token, steps)]
    assert "No source named 'nowhere'. Choose from: TCI-ThaiJO, arXiv." in texts[0]
    assert "Discussions" in texts[1] and "not a research id" in texts[2] and "No research with that id" in texts[3]


def _finished_run(user, db, topic="Songkran"):
    """A Run of `user`'s marked succeeded, with the fake engine's report on disk."""
    from litstorm import settings
    from litstorm.db.models import Run
    from litstorm.engines.fake import sample_report

    run_id = user.post("/api/sessions", json={"topic": topic, "language": "en"}).json()["runs"][0]["id"]
    run = db.get(Run, run_id)
    run.status = "succeeded"
    db.commit()
    folder = os.path.join(settings.get().runs_dir, run_id)
    os.makedirs(folder, exist_ok=True)
    report = sample_report(type("C", (), {"topic": topic, "language": "en"})())
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)
    return run_id


def test_a_finished_report_is_read_whole_or_in_parts(admin, browser, configured, db):  # noqa: F811
    user = make_user(admin, browser)
    token = _token(user)
    run_id = _finished_run(user, db)

    async def steps(session):
        return [
            _data(await session.call_tool("research_report", {"id": run_id, "part": p}))
            for p in ("full", "outline", "section:1")
        ]

    full, outline, section = _call(token, steps)
    assert full.startswith("# Songkran") and "[Example](https://example.org/a)" in full
    assert "1. Background" in outline and "section:N" in outline
    assert section.startswith("## Background") and "1. [Example](https://example.org/a)" in section


def test_an_integration_account_starts_only_its_modes(admin, browser, configured):  # noqa: F811
    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya", "allowed_engines": ["deep"]}).json()
    token = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None}).json()["token"]

    async def steps(session):
        options = _data(await session.call_tool("research_options", {}))
        refused = await session.call_tool("research_start", {"topic": "Songkran", "mode": "storm"})
        return options, refused

    options, refused = _call(token, steps)
    assert [e["id"] for e in options["engines"]] == ["deep"]
    assert refused.isError and "may not start that mode" in refused.content[0].text


def test_a_token_is_held_to_its_rate(admin, browser, monkeypatch):
    from litstorm.api import mcp

    monkeypatch.setattr(mcp, "CALLS_PER_MINUTE", 2)
    token = _token(make_user(admin, browser))
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    from fastapi.testclient import TestClient

    from litstorm.api import create_app

    with TestClient(create_app()) as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
                   "Content-Type": "application/json"}
        codes = [client.post("/api/mcp", headers=headers, content=json.dumps(listing)).status_code for _ in range(3)]
    assert codes[-1] == 429


def test_a_run_from_mcp_shows_its_token_and_an_integrations_is_read_by_admins(admin, browser, configured, db):  # noqa: F811
    from datetime import datetime, timezone

    from litstorm.db.models import Run

    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya"}).json()
    token = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None}).json()["token"]

    async def steps(session):
        return _data(await session.call_tool("research_start", {"topic": "Songkran", "wait_seconds": 0}))

    started = _call(token, steps)
    assert "web_url" not in started  # no one signs in as an integration account
    run = admin.get(f"/api/runs/{started['id']}")
    assert run.status_code == 200 and run.json()["via_token"] == "server"  # an Administrator reads it
    assert make_user(admin, browser).get(f"/api/runs/{started['id']}").status_code == 404  # no one else does
    assert [r["id"] for r in admin.get("/api/admin/integrations").json()[0]["recent"]] == [started["id"]]

    db.get(Run, started["id"]).started_at = datetime.now(timezone.utc)
    db.commit()
    rows = {r["name"]: r for r in admin.get("/api/admin/usage").json()["rows"]}
    assert rows["DeepWitya"]["kind"] == "integration" and rows["DeepWitya"]["mcp_runs"] == 1
    latest = admin.get("/api/admin/runs").json()[0]
    assert (latest["name"], latest["kind"]) == ("DeepWitya", "integration")  # not its made-up address


def test_progress_only_goes_forward():
    from types import SimpleNamespace

    from litstorm.api.mcp import _progress

    steps = [_progress(SimpleNamespace(engine="deep", status=status, stage=stage))
             for status, stage in [("queued", None), ("running", "research"), ("running", "report"),
                                   ("running", "normalize"), ("succeeded", "normalize")]]
    assert [s for s, _ in steps] == [0, 1, 2, 2, 3] and {t for _, t in steps} == {3}


def test_a_finished_report_is_exported_through_a_short_lived_link(admin, browser, configured, db):  # noqa: F811
    from fastapi.testclient import TestClient

    from litstorm import exports, settings
    from litstorm.api import create_app

    user = make_user(admin, browser)
    token = _token(user, scopes=("read",))
    run_id = _finished_run(user, db)
    waiting = user.post("/api/sessions", json={"topic": "Loy Krathong", "language": "en"}).json()["runs"][0]["id"]

    async def steps(session):
        made = [_data(await session.call_tool("research_export", {"id": run_id, "format": f}))
                for f in ("interactive", "html", "md")]
        unfinished = await session.call_tool("research_export", {"id": waiting})
        return made, unfinished

    (interactive, page, md), unfinished = _call(token, steps)
    assert unfinished.isError and "no report" in unfinished.content[0].text
    base = settings.get().export_url
    assert interactive["filename"] == page["filename"] == "Songkran.html" and md["filename"] == "Songkran.md"
    assert interactive["url"].startswith(f"{base}/api/exports/") and "curl" in interactive["next"]
    # The interactive page draws its charts in a Chromium (tests/test_interactive.py); the
    # link itself works the same for every format, so the plain page and Markdown are fetched.

    with TestClient(create_app()) as client:  # no cookie, no token: the link alone
        r = client.get(page["url"][len(base):])
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/html") and "attachment" in r.headers["content-disposition"]
        assert r.headers["cache-control"] == "private, no-store" and "Songkran" in r.text
        r = client.get(md["url"][len(base):])
        assert r.status_code == 200 and r.text.startswith("# Songkran")

        link = page["url"].rsplit("/", 1)[1]
        payload, signature = link.split(".")
        assert client.get(f"/api/exports/{payload}.{signature[:-2]}AA").status_code == 404  # tampered
        assert client.get("/api/exports/not-a-link").status_code == 404
        owner = user.get("/api/me").json()["id"]
        old, _ = exports.sign(run_id, owner, "md", now=time.time() - exports.LIFETIME - 1)
        assert client.get(f"/api/exports/{old}").status_code == 410
        # Someone else's id in a link the server signed still opens nothing that is not theirs.
        other = make_user(admin, browser, email="other@example.org")
        theirs, _ = exports.sign(run_id, other.get("/api/me").json()["id"], "md")
        assert client.get(f"/api/exports/{theirs}").status_code == 404



def test_a_repeated_start_is_the_same_run_and_costs_nothing(admin, browser, configured):  # noqa: F811
    token = _token(make_user(admin, browser))

    async def steps(session):
        args = {"topic": "Songkran water festival", "language": "en", "depth": "fast", "wait_seconds": 0}
        first = _data(await session.call_tool("research_start", args))
        again = _data(await session.call_tool("research_start", {**args, "topic": " Songkran water festival "}))
        deeper = _data(await session.call_tool("research_start", {**args, "depth": "standard"}))
        listed = _data(await session.call_tool("research_list", {}))
        schema = {t.name: t.inputSchema for t in (await session.list_tools()).tools}
        return first, again, deeper, listed, schema

    first, again, deeper, listed, schema = _call(token, steps)
    assert again["id"] == first["id"] and "repeated" in again and "repeated" not in first
    assert deeper["id"] != first["id"]
    assert sorted(r["id"] for r in listed) == sorted([first["id"], deeper["id"]])
    # Inside a client that cancels a tool call after 30 seconds (Agenta), by default.
    assert schema["research_start"]["properties"]["wait_seconds"]["default"] == 20


def test_a_thai_title_keeps_its_vowels_in_the_file_name():
    from litstorm.api.research import _filename

    title = "ฝุ่น PM2.5 ในประเทศไทย: สาเหตุและมาตรการแก้ไข"
    assert _filename({"title": title}, "html") == "ฝุ่น PM2_5 ในประเทศไทย_ สาเหตุและมาตรการแก้ไข.html"


# --- one server per mode ------------------------------------------------------------------------


def _session_info(token, url):
    """The server's name and instructions, and its tools, as a client sees them."""
    from litstorm.api import create_app

    app = create_app()

    async def go():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), headers={"Authorization": f"Bearer {token}"}, timeout=60
            ) as http:
                async with streamable_http_client(url, http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        info = await session.initialize()
                        return info, (await session.list_tools()).tools

    return asyncio.run(go())


def test_each_mode_has_a_server_named_for_it(admin, browser):
    token = _token(make_user(admin, browser))
    info, tools = _session_info(token, URL + "/deep")
    assert info.serverInfo.name == "DeepLit Deep Research"
    assert "deeplit-storm" in info.instructions and "does not open pages" in info.instructions
    assert sorted(t.name for t in tools) == sorted(f"deep_research_{v}" for v in (
        "options", "start", "status", "report", "export", "list", "cancel", "events"))
    start = next(t for t in tools if t.name == "deep_research_start")
    assert "mode" not in start.inputSchema["properties"] and start.description.startswith("Start Deep Research")
    assert "deep_research_status" in start.description and "research_status " not in start.description.replace(
        "deep_research_status", "")
    meta = {t.name: (t.meta or {}).get("ui") for t in tools}
    assert meta["deep_research_start"] == {"resourceUri": "ui://deeplit/deep-canvas.html"}
    combined, _ = _session_info(token, URL)
    assert combined.serverInfo.name == "DeepLit"


def test_a_mode_server_starts_its_mode_and_sees_only_its_runs(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import Run

    token = _token(make_user(admin, browser))

    async def on_deep(session):
        options = _data(await session.call_tool("deep_research_options", {}))
        started = _data(await session.call_tool("deep_research_start", {"topic": "Songkran", "wait_seconds": 0}))
        canvas = await session.read_resource("ui://deeplit/deep-canvas.html")
        return options, started, canvas.contents[0].text

    options, started, canvas = _call(token, on_deep, url=URL + "/deep")
    assert [e["id"] for e in options["engines"]] == ["deep"]
    assert db.get(Run, started["id"]).engine == "deep" and "deep_research_status" in started["next"]
    assert '"deep_research_events"' in canvas and '"research_events"' not in canvas

    async def on_storm(session):
        return (
            _data(await session.call_tool("storm_research_list", {})),
            await session.call_tool("storm_research_status", {"id": started["id"], "wait_seconds": 0}),
            await session.call_tool("storm_research_events", {"id": started["id"]}),
            await session.call_tool("storm_research_cancel", {"id": started["id"]}),
        )

    listed, status, events, cancel = _call(token, on_storm, url=URL + "/storm")
    assert listed == []
    for refused in (status, events, cancel):
        assert refused.isError and "is a Deep Research run" in refused.content[0].text
        assert "deeplit-deep" in refused.content[0].text and "/api/mcp/deep" in refused.content[0].text
    assert db.get(Run, started["id"]).status == "queued"  # the refused cancel did nothing

    async def on_combined(session):
        return _data(await session.call_tool("research_list", {}))

    assert [r["id"] for r in _call(token, on_combined)] == [started["id"]]


def test_a_mode_server_is_closed_to_who_may_not_use_the_mode(admin, browser):
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya", "allowed_engines": ["deep"]}).json()
    token = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None}).json()["token"]

    def post(path, raw):
        from fastapi.testclient import TestClient

        from litstorm.api import create_app

        with TestClient(create_app()) as client:
            return client.post(path, content=json.dumps(listing), headers={
                "Authorization": f"Bearer {raw}", "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"})

    assert post("/api/mcp/deep", token).status_code == 200
    refused = post("/api/mcp/storm", token)
    assert refused.status_code == 403 and refused.json()["error"] == "mode_not_allowed"
    assert "STORM" in refused.json()["message"]
    person = _token(make_user(admin, browser))
    admin.put("/api/admin/engines/agent", json={"enabled": False})
    refused = post("/api/mcp/agent", person)
    assert refused.status_code == 403 and refused.json()["error"] == "mode_disabled"
    assert post("/api/mcp", person).status_code == 200  # the combined server stays open


def test_each_mode_draws_its_own_canvas():
    from litstorm.api import mcp

    pages = {m: mcp._canvas_html.__wrapped__(m) for m in (None, *mcp.MODES)}
    for mode, html in pages.items():
        drawn = {m for m in mcp.MODES if f"window.DL.scenes.{m} =" in html}
        assert drawn == ({mode} if mode else set(mcp.MODES))  # a mode's page carries its scene alone
        assert "/*CONFIG*/" not in html and "<!--SCENES-->" not in html
        assert f'"events": "{mode + "_research" if mode else "research"}_events"' in html
        assert "http://" not in html.replace("http://www.w3.org/2000/svg", "") and "https://" not in html
