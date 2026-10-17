"""Medical Review: MedicalReviewerAgent as a remote Engine (docs/adr/0013),
against a stand-in MRA on this machine that answers its routes as it does:
POST /api/v1/reviews, the review's event stream, the review, its page, DELETE."""

import json
import threading
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture

REVIEW_ID = "11111111-2222-3333-4444-555555555555"

# MRA's result, cut down to what convert.py reads; the texts are made up.
RESULT = {
    "mode": "full", "review_type": "slr", "language": "en",
    "summary": "Drug X lowered the risk in two trials [P1, P2].",
    "question": {
        "refined_question": "In adults with Y, does drug X versus placebo lower the risk of Z?", "framework": "PICO",
        "pico": {"population": "adults with Y", "intervention_or_exposure": "drug X", "comparator": "placebo",
                 "outcomes": ["Z"]},
        "assumptions": ["Adults means 18 and over."],
    },
    "synthesis": {
        "answer": "Drug X probably lowers the risk of Z [P1; P2].",
        "executive_summary": "Two trials agree that drug X lowers the risk [P1, P2]; a third had too few events [P3].",
        "key_findings": [{"outcome": "Z", "statement": "Lower risk with drug X.", "refs": ["P1", "P2"], "k": 2,
                          "certainty": "moderate"}],
        "comparison": [{"outcome": "Z", "cells": [
            {"ref": "P1", "finding": "lower", "direction": "positive", "effect_measure": "RR", "effect_value": 0.8,
             "ci_lower": 0.7, "ci_upper": 0.9},
            {"ref": "P2", "finding": "lower", "direction": "positive", "effect_measure": "RR", "effect_value": 0.85,
             "ci_lower": None, "ci_upper": None}]}],
        "consensus": [{"statement": "Both trials found less Z.", "refs": ["P1", "P2"], "explanation": "Same doses."}],
        "conflicts": [], "research_gaps": ["Trials longer than a year."],
        "evidence_strength": "moderate", "grade_baseline": "moderate", "evidence_rationale": "Two RCTs, small.",
    },
    "meta_analysis": None,
    "methods": {"sources": {"pubmed": 12, "openalex": 9}, "searched_at": "2026-10-17T05:00:00Z",
                "synthesis": {"model": "qwen/qwen3.5-flash"}},
    "stats": {"found": 21, "screened": 18, "selected": 3},
    "papers": [
        {"ref": "P1", "title": "Trial one", "url": "https://example.org/p1", "authors": ["A", "B"], "journal": "J",
         "year": 2024, "card": {"study_design": "RCT", "sample_size": 300,
                                "outcomes": [{"evidence_quote": "Z occurred in 8% versus 10% (RR 0.80)."}]}},
        {"ref": "P2", "title": "Trial two", "doi": "10.1/x", "authors": ["C"], "journal": "K", "year": 2025,
         "card": {"study_design": "RCT", "outcomes": [{"evidence_quote": "RR 0.85 for Z."},
                                                      {"evidence_quote": "RR 0.85 for Z."}]}},
        {"ref": "P3", "title": "Trial three", "pmid": "123", "card": {"outcomes": []}},
    ],
}
EVENTS = [
    ("queued", {}), ("started", {"resume": False}), ("checking_topic", {}), ("refining", {}),
    ("question_refined", {"refined_question": RESULT["question"]["refined_question"], "assumptions": []}),
    ("planning", {"queries": ["x y z"]}), ("searching", {"found": 21}), ("screened", {"kept": 3, "total": 18}),
    ("reading", {"ref": "P1", "title": "Trial one"}), ("extracted", {"ref": "P1", "ok": True, "verified": 2}),
    ("synthesizing", {"papers": 3}), ("finalizing", {}), ("done", {"cost_usd": 0.0421}),
]


class FakeMRA:
    """A stand-in MRA: what it answers, and what it was asked."""

    def __init__(self):
        self.submit = [(202, {"review_id": REVIEW_ID, "status": "queued", "cached": False}, {})]
        self.events = list(EVENTS)
        self.review = {"id": REVIEW_ID, "status": "done", "cost_usd": 0.0421, "language": "en", "result": RESULT}
        self.page = b"<!doctype html><title>MRA report</title>"
        self.asked, self.deleted, self.keys = [], [], []

    def serve(self):
        mra = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code, body, kind="application/json", headers=None):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", kind)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                mra.keys.append(self.headers.get("X-API-Key"))
                mra.asked.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                code, body, headers = mra.submit.pop(0) if len(mra.submit) > 1 else mra.submit[0]
                self._send(code, body, headers=headers)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path.endswith("/events"):
                    frames = "".join(f"id: {i}\nevent: {kind}\ndata: {json.dumps(data)}\n\n"
                                     for i, (kind, data) in enumerate(mra.events, 1))
                    return self._send(200, (": ping\n\n" + frames).encode(), "text/event-stream")
                if path == f"/api/v1/reviews/{REVIEW_ID}":
                    return self._send(200, mra.review)
                if path == f"/r/{REVIEW_ID}/report.html":
                    return self._send(200, mra.page, "text/html")
                self._send(404, {"detail": "not found"})

            def do_DELETE(self):  # noqa: N802
                mra.deleted.append(self.path)
                self._send(200, {"review_id": REVIEW_ID, "status": "cancelled"})

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{server.server_port}"
        return server


@pytest.fixture
def mra():
    fake = FakeMRA()
    server = fake.serve()
    yield fake
    server.shutdown()


class Progress:
    def __init__(self):
        self.stages, self.notes, self.usages = [], [], []

    def stage(self, name):
        self.stages.append(name)

    def note(self, kind, **data):
        self.notes.append((kind, data))

    def usage(self, stage, llm, search, usd=None):
        self.usages.append(usd)


class Cancel:
    def __init__(self, after=None):
        self.after, self.checks = after, 0

    def requested(self):
        return self.after is not None and self.checks >= self.after

    def check(self):
        from litstorm.engines.base import Cancelled

        self.checks += 1
        if self.requested():
            raise Cancelled()


def _run(mra, tmp_path, cancel=None, **service):
    from litstorm.engines.base import RunConfig, Secrets
    from litstorm.engines.medical.engine import MedicalEngine

    config = RunConfig(run_id="r", engine="medical", topic="drug X and Z", language="en", llm={}, search={},
                       service={"url": mra.url, "mode": "full", **service})
    progress = Progress()
    report = MedicalEngine().run(config, Secrets(service_api_key="mra_key"), str(tmp_path), progress, cancel or Cancel())
    return report, progress


# --- the report -------------------------------------------------------------------------------


def test_a_review_reads_as_a_report_with_its_evidence():
    from litstorm import report as report_mod
    from litstorm.engines.medical.convert import to_report

    report = to_report({"result": RESULT}, "en", "drug X and Z")
    report_mod.validate(report)
    assert report["lead"] == "Drug X probably lowers the risk of Z [1][2]."  # [P1; P2], numbered
    headings = [s["heading"] for s in report["sections"]]
    assert headings[:3] == ["Key findings", "Discussion", "Comparison of studies"]
    assert "Studies included" in headings and "How this review was done" in headings
    body = {s["heading"]: s["body"] for s in report["sections"]}
    assert "(certainty: moderate; k=2)" in body["Key findings"]
    assert "| Z | [1] | lower | RR 0.8 (95% CI 0.7–0.9) |" in body["Comparison of studies"]
    assert "P: adults with Y" in body["How this review was done"]
    assert [s["id"] for s in report["sources"]] == [1, 2, 3]  # P3, only in the discussion, is a source too
    one, two, three = report["sources"]
    assert one["evidence"] == ["Z occurred in 8% versus 10% (RR 0.80)."]  # the abstract's sentence
    assert two["evidence"] == ["RR 0.85 for Z."] and two["url"] == "https://doi.org/10.1/x"
    assert three["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/" and three["evidence"] == []


def test_a_marker_for_a_paper_mra_did_not_return_is_dropped():
    from litstorm import report as report_mod
    from litstorm.engines.medical.convert import to_report

    result = {**RESULT, "synthesis": {**RESULT["synthesis"], "answer": "Yes [P1, P9]."}}
    report = to_report({"result": result}, "th", "x")
    report_mod.validate(report)
    assert report["lead"] == "Yes [1]."
    assert report["sections"][0]["heading"] == "ข้อค้นพบหลัก"  # the report's language


# --- the Engine against MRA ------------------------------------------------------------------


def test_a_review_is_asked_followed_and_kept(mra, tmp_path):
    report, progress = _run(mra, tmp_path, review_type="meta_analysis", study_types=["RCT"], year_from=2015)
    assert mra.asked == [{"topic": "drug X and Z", "language": "en", "options": {
        "mode": "full", "review_type": "meta_analysis", "study_types": ["RCT"], "year_from": 2015}}]
    assert mra.keys == ["mra_key"]
    assert progress.stages == ["refine", "search", "screen", "read", "synthesize"]
    assert ("service", {"review_id": REVIEW_ID, "cached": False}) in progress.notes
    assert [d["event"] for k, d in progress.notes if k == "medical"][-1] == "done"
    assert progress.usages == [0.0421]  # MRA's price for it
    assert (tmp_path / "mra_report.html").read_bytes() == mra.page and (tmp_path / "mra_review.json").exists()
    assert report["engine"] == "medical" and report["title"] == "drug X and Z"


def test_a_review_mra_already_had_costs_nothing(mra, tmp_path):
    mra.submit = [(202, {"review_id": REVIEW_ID, "status": "done", "cached": True}, {})]
    _, progress = _run(mra, tmp_path, mode="quick")
    assert ("service_cache", {"review_id": REVIEW_ID}) in progress.notes
    assert progress.usages == [0.0]
    assert not (tmp_path / "mra_report.html").exists()  # a quick answer has no page of its own


def test_a_busy_mra_is_asked_again_after_its_retry_after(mra, tmp_path):
    mra.submit = [(503, {"reason": "queue_full"}, {"Retry-After": "1"}),
                  (202, {"review_id": REVIEW_ID, "cached": False}, {})]
    _, progress = _run(mra, tmp_path)
    assert len(mra.asked) == 2 and any(k == "service_busy" for k, _ in progress.notes)


def test_an_emergency_is_declined_with_its_hotlines(mra, tmp_path):
    from litstorm.engines.base import EngineFailure

    mra.submit = [(422, {"code": "emergency", "message": "Call for help now.", "message_th": "โทรขอความช่วยเหลือ",
                         "hotlines": ["1669 (EMS)"]}, {})]
    with pytest.raises(EngineFailure) as failed:
        _run(mra, tmp_path)
    assert failed.value.reason == "service_declined" and str(failed.value) == "Call for help now. 1669 (EMS)"


def test_a_question_mra_rejects_ends_the_run_declined(mra, tmp_path):
    from litstorm.engines.base import EngineFailure

    mra.events = EVENTS[:3] + [("rejected", {"reason": "about one person's own case", "code": "personal_medical"})]
    with pytest.raises(EngineFailure) as failed:
        _run(mra, tmp_path)
    assert failed.value.reason == "service_declined" and "one person's own case" in str(failed.value)


def test_an_mra_that_cannot_be_reached_is_unavailable(tmp_path, monkeypatch):
    from litstorm.engines.base import EngineFailure
    from litstorm.engines.medical import engine

    monkeypatch.setattr(engine, "_sleep", lambda seconds, cancel: None)
    nowhere = type("M", (), {"url": "http://127.0.0.1:9"})()  # nothing listens there
    with pytest.raises(EngineFailure) as failed:
        _run(nowhere, tmp_path)
    assert failed.value.reason == "service_unavailable"


def test_a_cancel_stops_following(mra, tmp_path):
    from litstorm.engines.base import Cancelled

    with pytest.raises(Cancelled):
        _run(mra, tmp_path, cancel=Cancel(after=5))


# --- in the app ---------------------------------------------------------------------------------


@pytest.fixture
def medical_on(mra, db):
    from litstorm import medical

    medical.save(db, url=mra.url, api_key="mra_key")
    db.commit()
    return mra


@pytest.mark.db
def test_the_tab_is_offered_only_once_mra_is_set(admin, browser, configured, db, mra):  # noqa: F811
    from litstorm import medical

    user = make_user(admin, browser)
    assert "medical" not in [e["id"] for e in user.get("/api/options").json()["engines"]]
    refused = user.post("/api/sessions", json={"topic": "drug X and Z", "language": "en", "engine": "medical"})
    assert refused.status_code == 422 and refused.json()["detail"] == "engine_not_available"
    medical.save(db, url=mra.url, api_key="mra_key")
    db.commit()
    assert "medical" in [e["id"] for e in user.get("/api/options").json()["engines"]]


@pytest.mark.db
def test_a_medical_run_keeps_what_mra_is_asked(admin, browser, configured, medical_on, db):  # noqa: F811
    from litstorm.db.models import Run

    user = make_user(admin, browser)
    body = {"topic": "drug X and Z", "language": "en", "engine": "medical",
            "medical": {"mode": "full", "review_type": "scoping", "study_types": ["Cohort"], "year_from": 2010}}
    run = user.post("/api/sessions", json=body).json()["runs"][0]
    stored = db.get(Run, uuid.UUID(run["id"]))
    assert stored.config["service"] == {"mode": "full", "review_type": "scoping", "study_types": ["Cohort"],
                                        "year_from": 2010, "url": medical_on.url}
    assert run["model_label"] == "MedicalReviewerAgent" and run["search_label"] == "MRA"
    extra = user.post("/api/sessions", json={**body, "sections": ["A"]})
    assert extra.status_code == 422 and extra.json()["detail"] == "not_for_mode"


def _run_through_worker(db, user, **medical):
    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import main, queue

    run = user.post("/api/sessions", json={"topic": "drug X and Z", "language": "en", "engine": "medical",
                                           **({"medical": medical} if medical else {})}).json()["runs"][0]
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)
    db.expire_all()
    return db.get(Run, uuid.UUID(run["id"]))


@pytest.mark.db
def test_a_medical_run_ends_with_a_report_and_mras_price(admin, browser, configured, medical_on, db):  # noqa: F811
    user = make_user(admin, browser)
    stored = _run_through_worker(db, user, mode="full")
    assert stored.status == "succeeded" and stored.source_count == 3
    assert stored.cost_usd == Decimal("0.0421") and stored.quota_refunded is False
    assert stored.notes["service"]["review_id"] == REVIEW_ID
    report = user.get(f"/api/runs/{stored.id}/report").json()
    assert report["lead"].startswith("Drug X probably lowers")


@pytest.mark.db
def test_a_review_mra_already_had_gives_the_quota_back(admin, browser, configured, medical_on, db):  # noqa: F811
    medical_on.submit = [(202, {"review_id": REVIEW_ID, "status": "done", "cached": True}, {})]
    user = make_user(admin, browser)
    stored = _run_through_worker(db, user)
    assert stored.status == "succeeded" and stored.quota_refunded is True and stored.cost_usd == Decimal("0")


@pytest.mark.db
def test_mra_is_told_to_stop_only_when_no_other_run_follows_the_review(admin, browser, configured, medical_on, db):  # noqa: F811
    from litstorm import medical
    from litstorm.db.models import Run

    user = make_user(admin, browser)
    ids = [user.post("/api/sessions", json={"topic": f"question {i}", "language": "en", "engine": "medical"}).json()["runs"][0]["id"]
           for i in range(2)]
    for run_id in ids:
        row = db.get(Run, uuid.UUID(run_id))
        row.status, row.notes = "running", {"service": {"review_id": REVIEW_ID, "cached": False}}
    db.commit()
    assert medical.release(db, uuid.UUID(ids[0]), medical_on.url, "mra_key") is False  # the other still follows it
    assert medical_on.deleted == []
    db.get(Run, uuid.UUID(ids[1])).status = "cancelled"
    db.commit()
    assert medical.release(db, uuid.UUID(ids[0]), medical_on.url, "mra_key") is True
    assert medical_on.deleted == [f"/api/v1/reviews/{REVIEW_ID}"]


@pytest.mark.db
def test_an_administrator_sets_mra_up_and_checks_it(admin, browser, mra):
    saved = admin.put("/api/admin/medical", json={"url": mra.url + "/", "api_key": "mra_key",
                                                  "web_url": "https://mra.example.org"}).json()
    assert saved == {"url": mra.url, "web_url": "https://mra.example.org", "console_url": "https://mra.example.org/admin",
                     "has_key": True, "configured": True}
    kept = admin.put("/api/admin/medical", json={"url": mra.url, "web_url": ""}).json()  # no key: the stored one stays
    assert kept["has_key"] is True and kept["console_url"] == f"{mra.url}/admin"
    assert "mra_key" not in json.dumps(admin.get("/api/admin/medical").json())  # never shown again
    user = make_user(admin, browser)
    assert user.get("/api/admin/medical").status_code == 403
    assert user.get("/api/medical/status").json()["reachable"] is False  # the stand-in has no /status


@pytest.mark.db
def test_mras_own_page_is_kept_and_shown_sandboxed(admin, browser, configured, medical_on, db):  # noqa: F811
    user = make_user(admin, browser)
    stored = _run_through_worker(db, user, mode="full")
    assert stored.notes["service_page"]["kept"] is True
    page = user.get(f"/api/runs/{stored.id}/service-page")
    assert page.status_code == 200 and page.content == medical_on.page
    assert page.headers["content-security-policy"].startswith("sandbox allow-scripts")
    other = make_user(admin, browser, email="other@example.org")
    assert other.get(f"/api/runs/{stored.id}/service-page").status_code == 404  # not theirs


@pytest.mark.db
def test_the_owner_sees_mras_steps_for_the_canvas(admin, browser, configured, medical_on, db):  # noqa: F811
    user = make_user(admin, browser)
    stored = _run_through_worker(db, user, mode="full")
    detail = user.get(f"/api/runs/{stored.id}").json()
    steps = [e["data"]["event"] for e in detail["events"] if e["type"] == "note" and e["data"].get("kind") == "medical"]
    assert steps[0] == "queued" and steps[-1] == "done" and "extracted" in steps
    run = detail.get("run", detail)
    assert run["service"] == {"mode": "full", "review_type": "slr", "study_types": [], "year_from": None}
