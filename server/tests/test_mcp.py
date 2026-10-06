"""DeepLit's MCP server, called as a client would: the SDK's own client over
Streamable HTTP, against the app in process (api/mcp.py)."""

import asyncio
import json
import os

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


def _call(token, steps, progress=None):
    """Run `steps(session)` against a fresh app with an MCP client session."""
    from litstorm.api import create_app

    app = create_app()

    async def go():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), headers={"Authorization": f"Bearer {token}"}, timeout=60
            ) as http:
                async with streamable_http_client(URL, http_client=http) as (read, write, _):
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


def test_six_tools_with_instructions(admin, browser):
    token = _token(make_user(admin, browser))

    async def steps(session):
        return (await session.list_tools()).tools

    tools = _call(token, steps)
    assert all(t.description == " ".join(t.description.split()) for t in tools)  # one clean line each
    assert sorted(t.name for t in tools) == sorted([
        "research_options", "research_start", "research_status", "research_report", "research_list", "research_cancel",
    ])


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


def test_a_finished_report_is_read_whole_or_in_parts(admin, browser, configured, db):  # noqa: F811
    from litstorm import settings
    from litstorm.db.models import Run
    from litstorm.engines.fake import sample_report

    user = make_user(admin, browser)
    token = _token(user)
    run_id = user.post("/api/sessions", json={"topic": "Songkran", "language": "en"}).json()["runs"][0]["id"]
    run = db.get(Run, run_id)
    run.status = "succeeded"
    db.commit()
    folder = os.path.join(settings.get().runs_dir, run_id)
    os.makedirs(folder, exist_ok=True)
    report = sample_report(type("C", (), {"topic": "Songkran", "language": "en"})())
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)

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
