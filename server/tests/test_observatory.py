"""The observatory (litstorm.render.observatory): the page's data, its safety,
the live page for a Run's owner, and the file through both export paths."""

import json
import re
import uuid

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture
from test_mcp import _call, _data, _finished_run, _token


def _embedded(page):
    blob = re.search(r'<script type="application/json" id="obs-data">(.*?)</script>', page, re.DOTALL).group(1)
    return json.loads(blob)


def _facts(**more):
    return {"id": "r1", "topic": "Songkran", "language": "en", "engine": "agent", "engine_label": "Agent Research",
            "depth": "standard", "status": "succeeded", **more}


def test_the_page_carries_its_data_and_asks_for_nothing():
    from litstorm.render import observatory

    events = [{"id": 1, "at": "2026-10-15T01:00:00+00:00", "type": "stage", "data": {"stage": "plan"}}]
    report = {"title": "T", "lead": "Water is thrown.[1]", "sections": [{"heading": "H", "body": "B[1]", "children": []}],
              "sources": [{"id": 1, "url": "https://example.org/a", "title": "A", "evidence": ["Water is thrown at Songkran."]}]}
    page = observatory.render(_facts(), events, report)
    data = _embedded(page)
    assert data["run"]["topic"] == "Songkran" and data["events"] == events and data["live"] is None
    assert data["report"]["sources"][0]["evidence"] == ["Water is thrown at Songkran."]
    assert observatory.CSP in page and "connect-src" not in page
    # Nothing is loaded from anywhere: no script, style, image or frame by address.
    assert not re.search(r"""<(script|link|img|iframe)[^>]+(src|href)=["']?https?:""", page)
    assert "highlightRAGChunk" in page

    live = observatory.render(_facts(status="running"), [], None, live={"run": "../r1", "report": "report"})
    assert observatory.LIVE_CSP in live and _embedded(live)["live"] == {"run": "../r1", "report": "report"}


def test_nothing_the_run_or_model_wrote_can_end_the_script():
    from litstorm.render import observatory

    evil = "</script><script>alert(1)</script><!-- __OBS_DATA__"
    report = {"title": evil, "lead": evil, "sections": [], "sources": [{"id": 1, "url": "javascript:alert(1)", "title": evil, "evidence": [evil]}]}
    page = observatory.render(_facts(topic=evil), [{"id": 1, "at": None, "type": "note", "data": {"kind": "flow", "event": "observed", "text": evil}}], report)
    assert page.count("</script>") == 2  # the data's and the code's own
    assert "<script>alert" not in page
    assert _embedded(page)["run"]["topic"] == evil
    assert "<title>Observatory — &lt;/script&gt;" in page


def test_only_the_notes_the_owner_sees_are_drawn():
    from types import SimpleNamespace

    from litstorm.render import observatory

    def ev(i, kind):
        return SimpleNamespace(id=i, at=None, type="note", data={"kind": kind})

    out = observatory.events_out([ev(1, "browsed"), ev(2, "traceback"), ev(3, "tree"), SimpleNamespace(id=4, at=None, type="usage", data={})])
    assert [e["id"] for e in out] == [1, 3, 4]


@pytest.mark.db
def test_the_live_page_is_its_owners_and_replays_once_done(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import RunEvent

    user = make_user(admin, browser)
    run_id = _finished_run(user, db)
    db.add(RunEvent(run_id=uuid.UUID(run_id), type="note", data={"kind": "browsed", "urls": ["https://example.org/a"]}))
    db.add(RunEvent(run_id=uuid.UUID(run_id), type="note", data={"kind": "traceback", "text": "secret"}))
    db.commit()

    r = user.get(f"/api/runs/{run_id}/observatory")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "connect-src 'self'" in r.headers["content-security-policy"] and r.headers["cache-control"] == "private, no-store"
    data = _embedded(r.text)
    assert data["live"] == {"run": f"../{run_id}", "report": "report"}
    assert [e["data"]["kind"] for e in data["events"] if e["type"] == "note"] == ["browsed"]
    assert data["report"]["title"] and data["report"]["sources"]

    other = make_user(admin, browser, email="other@example.org")
    assert other.get(f"/api/runs/{run_id}/observatory").status_code == 404


@pytest.mark.db
def test_the_file_downloads_from_the_web_app_and_through_mcp(admin, browser, configured, db):  # noqa: F811
    from fastapi.testclient import TestClient

    from litstorm import settings
    from litstorm.api import create_app

    user = make_user(admin, browser)
    run_id = _finished_run(user, db)
    r = user.get(f"/api/runs/{run_id}/export", params={"format": "observatory"})
    assert r.status_code == 200, r.text
    assert "Songkran.observatory.html" in r.headers["content-disposition"]
    assert _embedded(r.text)["live"] is None

    token = _token(user, scopes=("read",))

    async def steps(session):
        return _data(await session.call_tool("research_export", {"id": run_id, "format": "observatory"}))

    made = _call(token, steps)
    assert made["filename"] == "Songkran.observatory.html"
    base = settings.get().export_url
    with TestClient(create_app()) as client:
        got = client.get(made["url"][len(base):])
        assert got.status_code == 200 and _embedded(got.text)["run"]["id"] == run_id
