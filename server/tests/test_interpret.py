"""Topic interpretation: a Run reads its topic first (litstorm.interpret).
The reading steers research through the focus every Engine takes, is kept
with the Run and as the report's method, and never holds a Run up."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import make_user
from litstorm.engines.base import RunConfig, Secrets
from litstorm.runner import files
from litstorm.runner.supervisor import supervise
from test_api_runs import configured  # noqa: F401  (fixture)

READING = {
    "question": "How did Songkran change in Bangkok after 2010?",
    "scope": ["Bangkok", "2010 onwards"],
    "assumptions": ["the festival as celebrated, not its religious meaning"],
    "keywords": {"en": ["Songkran Bangkok", "Thai New Year tourism"], "th": ["สงกรานต์ กรุงเทพ"]},
    "exclude": ["water-gun sales"],
}


class FakeModel:
    """An OpenAI-compatible model that answers every chat with `reply`."""

    def __init__(self, reply, status=200):
        self.reply, self.status, self.asked = reply, status, []

    def __enter__(self):
        model = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                model.asked.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps({
                    "id": "x", "object": "chat.completion", "created": 0, "model": "m",
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": model.reply}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
                } if model.status == 200 else {"error": {"message": "down"}}).encode()
                self.send_response(model.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()


def _config(model_url, topic="สงกรานต์", language="th", interpret=True, **extra):
    return RunConfig(
        run_id="r1", engine="fake", topic=topic, language=language,
        llm={"provider": "openai-compatible", "model": "m", "api_base": model_url},
        search={"provider": "arxiv"},
        params={"script": [{"stage": "research"}, {"focus_probe": True}]},
        interpret=interpret, **extra,
    )


def _events(run_dir):
    with open(files.path(str(run_dir), files.EVENTS), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# --- reading a reply ------------------------------------------------------------------------


def test_a_reply_is_read_cleaned_and_bounded():
    from litstorm import interpret

    reply = "Here it is:\n```json\n" + json.dumps({
        **READING, "scope": "Bangkok", "exclude": ["a", "A", " a "] + [f"x{i}" for i in range(9)],
        "assumptions": None,
    }) + "\n```"
    found = interpret.parse(reply)
    assert found["question"] == READING["question"]
    assert found["scope"] == ["Bangkok"]  # one string is a list of one
    assert found["assumptions"] == []
    assert found["exclude"][0] == "a" and len(found["exclude"]) == interpret.MAX_ITEMS
    assert found["keywords"] == READING["keywords"]


def test_a_reply_without_a_question_is_no_reading():
    from litstorm import interpret

    assert interpret.parse("I cannot help with that.") is None
    assert interpret.parse(json.dumps({**READING, "question": "  "})) is None
    assert interpret.parse("[1, 2]") is None


def test_the_reading_steers_research_after_the_owners_own_words():
    from litstorm import instructions

    config = _config("", interpretation={**READING, "searched": ["en", "th"]},
                     refinement=[{"question": "Which period?", "answer": "since 2010"}],
                     instructions={"search_scope": "news and research"})
    focus = instructions.focus(config)
    assert focus.index("since 2010") < focus.index("news and research") < focus.index("research question:")
    assert "Songkran Bangkok" in focus and "สงกรานต์ กรุงเทพ" in focus and "leave out: water-gun sales" in focus

    english = _config("", topic="Songkran", language="en", interpretation={**READING, "searched": ["en"]})
    assert "สงกรานต์" not in instructions.focus(english)  # Thai terms would pull Thai sources in
    assert instructions.focus(_config("")) == ""


# --- in the Run's process -------------------------------------------------------------------


def test_the_run_reads_its_topic_first_and_the_engine_is_steered_by_it(tmp_path):
    with FakeModel(json.dumps(READING)) as model:
        outcome = supervise(str(tmp_path), _config(model.url), Secrets(llm_api_key="sk-x"), poll_interval=0.05)
    assert outcome.status == "succeeded"
    asked = model.asked[0]["messages"][0]["content"]
    assert "สงกรานต์" in asked and "in Thai" in asked

    events = _events(tmp_path)
    stages = [e["stage"] for e in events if e["type"] == "stage"]
    assert stages[0] == "interpret" and stages[1] == "research"
    reading = next(e for e in events if e.get("kind") == "interpretation")
    assert reading["question"] == READING["question"] and reading["searched"] == ["en", "th"]
    focus = next(e for e in events if e.get("kind") == "focus")["text"]
    assert "research question: How did Songkran change" in focus and "สงกรานต์ กรุงเทพ" in focus
    assert outcome.usage[0] == {"type": "usage", "stage": "interpret", "llm": {
        "openai/m": {"prompt_tokens": 120, "completion_tokens": 80}}, "search": {}, "t": outcome.usage[0]["t"]}

    with open(tmp_path / files.REPORT, encoding="utf-8") as f:
        assert json.load(f)["interpretation"]["question"] == READING["question"]
    assert (tmp_path / files.WORK / "interpretation.json").exists()


def test_a_model_that_fails_leaves_the_topic_as_typed(tmp_path):
    with FakeModel("", status=500) as model:
        outcome = supervise(str(tmp_path), _config(model.url), Secrets(llm_api_key="sk-x"), poll_interval=0.05)
    assert outcome.status == "succeeded"
    events = _events(tmp_path)
    assert next(e for e in events if e.get("kind") == "interpretation")["failed"]
    assert next(e for e in events if e.get("kind") == "focus")["text"] == ""
    with open(tmp_path / files.REPORT, encoding="utf-8") as f:
        assert "interpretation" not in json.load(f)


def test_a_reply_that_is_no_reading_leaves_the_topic_as_typed(tmp_path):
    with FakeModel("Sorry, what do you mean?") as model:
        outcome = supervise(str(tmp_path), _config(model.url), Secrets(llm_api_key="sk-x"), poll_interval=0.05)
    assert outcome.status == "succeeded"
    assert [u["stage"] for u in outcome.usage][0] == "interpret"  # what it cost is still counted
    assert next(e for e in _events(tmp_path) if e.get("kind") == "interpretation")["failed"]


def test_a_run_not_set_to_interpret_asks_no_one(tmp_path):
    with FakeModel(json.dumps(READING)) as model:
        outcome = supervise(str(tmp_path), _config(model.url, interpret=False), Secrets(llm_api_key="sk-x"),
                            poll_interval=0.05)
    assert outcome.status == "succeeded" and model.asked == []
    assert [e["stage"] for e in _events(tmp_path) if e["type"] == "stage"] == ["research"]


# --- the report's method --------------------------------------------------------------------


def _report(language="th"):
    from litstorm.engines.fake import sample_report

    report = sample_report(_config("", language=language))
    report["interpretation"] = {**READING, "searched": ["en", "th"] if language == "th" else ["en"]}
    return report


def test_the_exports_show_the_reading_as_the_method():
    from litstorm import report as report_mod
    from litstorm.render import html, markdown

    report = _report()
    report_mod.validate(report)
    page = html.render(report)
    assert '<section class="method" id="method">' in page and "ระบบตีความหัวเรื่องนี้ว่า" in page
    assert page.index('id="method"') < page.index('id="sources"')
    md = markdown.render(report)
    assert "## วิธีการ" in md and "ไทย: สงกรานต์ กรุงเทพ" in md

    english = markdown.render(_report("en"))
    assert "## Method" in english and "Thai:" not in english  # only the terms it searched with

    plain = _report()
    del plain["interpretation"]
    assert 'class="method"' not in html.render(plain) and "## วิธีการ" not in markdown.render(plain)


def test_a_reading_that_is_not_one_is_refused():
    from litstorm import report as report_mod

    report = _report()
    report["interpretation"] = {"scope": []}
    with pytest.raises(report_mod.ReportError):
        report_mod.validate(report)


# --- the API --------------------------------------------------------------------------------


def _start(user, engine="storm"):
    project = user.post("/api/projects", json={"name": "P"}).json()
    return user.post(f"/api/projects/{project['id']}/sessions",
                     json={"topic": "Songkran", "language": "th", "engine": engine}).json()["runs"][0]


@pytest.mark.db
def test_every_mode_that_can_reads_its_topic_by_default(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import Run

    engines = {e["id"]: e for e in admin.get("/api/admin/engines").json()}
    assert {k for k, e in engines.items() if e["interprets"]} == {"storm", "deep", "agent"}
    assert all(e["interpret"] == e["interprets"] for e in engines.values())

    user = make_user(admin, browser)
    run = _start(user)
    assert run["interpret"] is True and db.get(Run, run["id"]).config["interpret"] is True


@pytest.mark.db
def test_an_administrator_turns_it_off_for_one_mode(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import Run

    r = admin.put("/api/admin/engines/storm", json={"interpret": False})
    assert {e["id"]: e["interpret"] for e in r.json()}["storm"] is False
    # Switching the mode off and on again leaves the reading off.
    admin.put("/api/admin/engines/deep", json={"enabled": False})
    engines = {e["id"]: e for e in admin.put("/api/admin/engines/deep", json={"enabled": True}).json()}
    assert engines["storm"]["interpret"] is False and engines["deep"]["interpret"] is True

    user = make_user(admin, browser)
    run = _start(user)
    assert run["interpret"] is False and "interpret" not in db.get(Run, run["id"]).config
    # A retry is made as the mode is set now.
    admin.put("/api/admin/engines/storm", json={"interpret": True})
    user.post(f"/api/runs/{run['id']}/cancel")
    again = user.post(f"/api/runs/{run['id']}/retry").json()
    assert again["interpret"] is True


@pytest.mark.db
def test_a_mode_that_reads_its_own_way_cannot_be_set_to(admin):
    for engine in ("co-storm", "medical"):
        r = admin.put(f"/api/admin/engines/{engine}", json={"interpret": True})
        assert r.status_code == 422 and r.json()["detail"] == "cannot_interpret"


@pytest.mark.db
def test_the_owner_and_mcp_see_what_the_topic_was_read_as(admin, browser, configured, db):  # noqa: F811
    from litstorm.api import mcp
    from litstorm.db.models import Run, User

    user = make_user(admin, browser)
    run = _start(user)
    stored = db.get(Run, run["id"])
    stored.notes = {"interpretation": {**READING, "searched": ["en", "th"]}}
    stored.status, stored.stage = "running", "interpret"
    db.commit()
    shown = user.get(f"/api/runs/{run['id']}").json()
    assert shown["notes"]["interpretation"]["question"] == READING["question"]
    assert mcp._progress(stored) == (1, 6)  # the reading, STORM's four stages, and the end

    _, facts = mcp._run_facts(db, db.get(User, stored.owner_id), run["id"])
    assert facts["interpreted_as"] == READING["question"]


@pytest.mark.db
def test_the_reading_reaches_the_canvases_as_it_happens(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import RunEvent

    user = make_user(admin, browser)
    run = _start(user)
    db.add_all([RunEvent(run_id=run["id"], type="stage", data={"stage": "interpret"}),
                RunEvent(run_id=run["id"], type="note", data={"kind": "interpretation", **READING}),
                RunEvent(run_id=run["id"], type="note", data={"kind": "traceback", "text": "kept from the owner"})])
    db.commit()
    events = user.get(f"/api/runs/{run['id']}").json()["events"]
    assert [e["data"].get("kind", e["data"].get("stage")) for e in events] == ["interpret", "interpretation"]
