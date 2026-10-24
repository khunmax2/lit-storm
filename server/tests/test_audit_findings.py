"""Findings of the 2026-10-24 audit (docs/reports/audit-2026-10-24/security.md).

Each test asserts the SAFE behaviour, so it fails today and is marked
xfail(strict=True): once the finding is fixed the test passes, strict turns
that into a failure, and whoever fixed it removes the mark. Nothing here
calls a real model or search service; outbound calls are captured.
"""

import asyncio
import http.server
import re
import ssl
import threading
from pathlib import Path

import pytest

from conftest import make_user


def finding(code):
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=code)


# --- SEC-02: Agent Research fetches internal addresses ----------------------------


class _Internal(http.server.BaseHTTPRequestHandler):
    """Stands in for a service only the Worker can reach (SearXNG, MRA, the host)."""

    def do_GET(self):  # noqa: N802 - http.server's name
        body = b"<html><body><p>internal-service-secret-sec02</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def internal_service():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Internal)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


@finding("SEC-02")
def test_sec02_agent_research_does_not_fetch_internal_addresses(internal_service):
    """The pages a search result (or the crawl agent, from what the model
    asks) points at are fetched with no check of where they are: a loopback,
    private or link-local address comes back as text for the report."""
    from deep_researcher.tools.web_search import WebpageSnippet, scrape_urls

    results = asyncio.run(scrape_urls([WebpageSnippet(url=internal_service, title="", description="")]))
    assert not any("internal-service-secret-sec02" in (r.text or "") for r in results)


# --- SEC-03 and SEC-08: signing in -----------------------------------------------------


@finding("SEC-03")
@pytest.mark.db
def test_sec03_repeated_wrong_passwords_are_slowed_down(admin, browser):
    make_user(admin, browser, "audit-victim@example.org", "the right password 1")
    stranger = browser()
    codes = [
        stranger.post("/api/auth/login", json={"email": "audit-victim@example.org", "password": f"guess {i:04d}"}).status_code
        for i in range(50)
    ]
    # 429 Too Many Requests, 423 Locked or 503 with Retry-After: any of them is a throttle.
    assert THROTTLED & set(codes), f"50 wrong passwords in a row, all answered {set(codes)}"


THROTTLED = {423, 429, 503}


@finding("SEC-08")
@pytest.mark.db
def test_sec08_login_does_the_same_work_for_an_unknown_address(admin, browser, monkeypatch):
    """An address with no account is refused before any password is
    checked, so it answers about 50 ms sooner (argon2) than a wrong password
    for a real account. Safe: the password is checked (against a dummy hash)
    whether or not the address has an account."""
    from litstorm import security

    calls = []
    real = security.verify_password

    def counted(password_hash, password):
        calls.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(security, "verify_password", counted)
    r = browser().post("/api/auth/login", json={"email": "audit-nobody@example.org", "password": "not the password"})
    assert r.status_code == 401
    assert calls, "no password was checked for an address without an account"


# --- SEC-05: a stored key goes to an address typed in the request -----------------

STORED_KEY = "sk-or-v1-audit-stored-key-0000000000"
ELSEWHERE = "http://attacker.invalid/v1"


@finding("SEC-05")
@pytest.mark.db
def test_sec05_testing_a_draft_model_does_not_send_the_stored_key_elsewhere(admin, monkeypatch):
    import litellm

    sent = []

    def capture(**kwargs):
        sent.append(kwargs)
        raise RuntimeError("captured, not sent")

    monkeypatch.setattr(litellm, "completion", capture)
    assert admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": STORED_KEY}).status_code == 200
    r = admin.post("/api/admin/llm-models/check", json={"provider": "openrouter", "model": "any/model", "api_base": ELSEWHERE})
    assert r.status_code == 200
    leaked = [k for k in sent if k.get("api_key") == STORED_KEY and k.get("api_base") == ELSEWHERE]
    assert len(leaked) == 0, "the stored OpenRouter key was handed to an address the request named"


@finding("SEC-05")
@pytest.mark.db
def test_sec05_testing_an_embedding_does_not_send_the_stored_key_elsewhere(admin, monkeypatch):
    """embedding.key_for keeps the key from another address for
    "openai-compatible" only; the other providers take an api_base too."""
    from litstorm import embedding

    sent = []

    class Refused:
        status_code = 401
        text = "captured"

    def capture(url, json=None, headers=None, timeout=None):
        sent.append((url, headers or {}))
        return Refused()

    monkeypatch.setattr(embedding.requests, "post", capture)
    assert admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": STORED_KEY}).status_code == 200
    r = admin.post("/api/admin/embedding/check", json={"provider": "openrouter", "model": "m", "api_base": ELSEWHERE})
    assert r.status_code == 200
    leaked = [u for u, h in sent if u.startswith(ELSEWHERE) and STORED_KEY in h.get("Authorization", "")]
    assert len(leaked) == 0, "the stored OpenRouter key was sent to an address the request named"


# --- SEC-06: Agent Research turns certificate checks off ---------------------------


@finding("SEC-06")
def test_sec06_agent_research_checks_certificates():
    """Its one TLS context serves the Tavily search (the key in the body),
    SearXNG and every page it reads."""
    from deep_researcher.tools import web_search

    assert web_search.ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert web_search.ssl_context.check_hostname


# --- SEC-07: a reset leaves the account's API tokens working ---------------------


@finding("SEC-07")
@pytest.mark.db
def test_sec07_a_password_reset_stops_the_accounts_api_tokens(admin, browser):
    import json

    from fastapi.testclient import TestClient

    from litstorm.api import create_app

    user = make_user(admin, browser, "audit-reset@example.org")
    token = user.post("/api/me/tokens", json={"name": "t", "scopes": ["read"], "days": 30}).json()["token"]
    account = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "audit-reset@example.org")
    # "the old password stops working and the User is signed out everywhere" (api/admin.reset_link)
    assert admin.post(f"/api/admin/users/{account['id']}/link").status_code == 200

    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}
    with TestClient(create_app()) as client:
        r = client.post("/api/mcp", headers=headers, content=json.dumps(listing))
    assert r.status_code in (401, 403), f"the token still opens the MCP server after the reset ({r.status_code})"


# --- SEC-09: security headers ------------------------------------------------------------

WEB = Path(__file__).resolve().parents[2] / "web"


@finding("SEC-09")
def test_sec09_the_web_app_is_served_with_a_csp_and_no_framing():
    # Directives only: a comment that names a header does not send it.
    lines = (WEB / "nginx.conf").read_text(encoding="utf-8").splitlines()
    conf = "\n".join(line.split("#", 1)[0] for line in lines)
    assert re.search(r"add_header\s+Content-Security-Policy\s", conf)
    assert re.search(r"add_header\s+Content-Security-Policy\s[^\n]*frame-ancestors", conf) or re.search(
        r"add_header\s+X-Frame-Options\s", conf
    )


# --- SEC-11: dependencies with fixes that reach our code ----------------------------


def _version(name):
    from importlib.metadata import version

    from packaging.version import Version

    return Version(version(name))


@finding("SEC-11")
def test_sec11_outbound_https_libraries_are_patched():
    from packaging.version import Version

    # certifi < 2026.10.19 trusts the emSign ECC Root CA - G3 (PYSEC-2026-4320).
    assert _version("certifi") >= Version("2026.10.19")
    # aiohttp 3.14.4: the client Agent Research reads pages with (GHSA-2g87-pp6c-29x5 and others).
    assert _version("aiohttp") >= Version("3.14.4")


# =====================================================================================
# BUG-xx: findings of the code readers on the Worker, quota and Trash (Task 3a).
# docs/reports/audit-2026-10-24/bugs.md says what each one is and how bad.
# =====================================================================================

import time  # noqa: E402
import uuid  # noqa: E402

from test_trash_and_cost import age, configured, purge, research, run_fake  # noqa: E402,F401 - a fixture too


def _claim_one():
    from litstorm import db as db_mod
    from litstorm.worker import queue

    with db_mod.sessions()() as s:
        return queue.claim(s)


def _ready_to_run(db, run_id, script):
    """Point a queued Run at the fake engine, as test_trash_and_cost.run_fake does, and claim it."""
    from litstorm.db.models import Run

    run = db.get(Run, uuid.UUID(run_id))
    run.engine = "fake"
    run.config = {**{k: v for k, v in run.config.items() if k != "interpret"}, "params": {"script": script}}
    db.commit()
    return _claim_one()


def _state(db, run_id):
    from litstorm.db.models import Run

    db.expire_all()
    return db.get(Run, uuid.UUID(str(run_id)))


def _failed(db, run_id, reason="refused"):
    """Mark a Run failed for a reason that keeps its quota, as the Worker would have."""
    from datetime import datetime, timezone

    from litstorm.db.models import FAILED, Run

    run = db.get(Run, uuid.UUID(run_id))
    now = datetime.now(timezone.utc)
    run.status, run.reason, run.started_at, run.finished_at = FAILED, reason, now, now
    db.commit()


def _together(*calls):
    """Each call in a thread of its own, started at once; the results, or the exception a call raised."""
    import threading

    results = [None] * len(calls)

    def go(i, fn):
        try:
            results[i] = fn()
        except Exception as error:  # noqa: BLE001 - what the caller of a request would have seen
            results[i] = error

    threads = [threading.Thread(target=go, args=(i, fn)) for i, fn in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(90)
    return results


def _meet_at(monkeypatch, owner, name, *, after):
    """Make two requests reach `owner.name` together (the first call of each thread only), so
    that both have passed whatever came before it when either goes on. `after`: wait after the
    real call (an early check) rather than before it."""
    import threading

    real = getattr(owner, name)
    barrier = threading.Barrier(2, timeout=3)
    seen = threading.local()

    def wait():
        if getattr(seen, "done", False):
            return
        seen.done = True
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass

    def wrapper(*args, **kwargs):
        if after:
            result = real(*args, **kwargs)
            wait()
            return result
        wait()
        return real(*args, **kwargs)

    monkeypatch.setattr(owner, name, wrapper)


def _limits(admin, **changes):
    current = admin.get("/api/admin/limits").json()
    assert admin.put("/api/admin/limits", json={**current, **changes}).status_code == 200


# --- the Worker's loop -----------------------------------------------------------------


@pytest.fixture
def one_pass(monkeypatch):
    """The Worker's main(), told to stop after its first look at the queue, with no spare
    process. Returns a function that runs it and turns "it died" into an AssertionError."""
    import signal

    from litstorm.worker import main as worker

    previous = signal.getsignal(signal.SIGTERM)

    class Wake:
        def wait(self, timeout, stopping):
            stopping.set()

        def close(self):
            pass

    class NoSpare:
        def refill(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(worker.notify, "QueueWakeup", Wake)
    monkeypatch.setattr(worker, "Spare", NoSpare)

    def run():
        try:
            worker.main()
        except Exception as error:  # noqa: BLE001
            raise AssertionError(f"the Worker's process ended: {type(error).__name__}: {error}") from error

    yield run
    signal.signal(signal.SIGTERM, previous)


@finding("BUG-01")
@pytest.mark.db
@pytest.mark.parametrize("step", ["purge", "sweep_interrupted", "claim"])
def test_bug01_one_failed_step_does_not_end_the_workers_process(db, one_pass, monkeypatch, step):
    """main() calls the purge, the sweep and the claim with nothing around them: a database
    error in any of them ends the process, and no Run is claimed until it is restarted
    (and the purge runs first on every start)."""
    from sqlalchemy.exc import OperationalError

    from litstorm.worker import main as worker

    def broken(*args, **kwargs):
        raise OperationalError("select 1", {}, Exception("the database went away"))

    owner, name = {"purge": (worker.trash, "purge"), "sweep_interrupted": (worker.queue, "sweep_interrupted"),
                   "claim": (worker.queue, "claim")}[step]
    monkeypatch.setattr(owner, name, broken)
    one_pass()


def _queued_into_the_trash(admin, browser, monkeypatch, who="audit-alice@example.org"):
    """What the race leaves: create_run checks the Session, then the owner's limits, then
    inserts, while the trash stops only the Runs that exist at that moment. The Session is
    trashed between the check and the insert (by a second connection, as another request
    would), so a new Run sits QUEUED in a Session in the Trash. Returns the owner and the Run."""
    from litstorm import db as db_mod
    from litstorm import quota, trash
    from litstorm.db.models import ResearchSession

    owner = make_user(admin, browser, who)
    _, session, _ = research(owner)
    real = quota.check_submit

    def trashed_meanwhile(s, user, units=1):
        with db_mod.sessions()() as other:
            trash.trash_session(other, other.get(ResearchSession, uuid.UUID(session["id"])))
            other.commit()
        return real(s, user, units)

    monkeypatch.setattr(quota, "check_submit", trashed_meanwhile)
    r = owner.post(f"/api/sessions/{session['id']}/runs", json={"topic": "Songkran again", "language": "th"})
    monkeypatch.setattr(quota, "check_submit", real)
    assert r.status_code == 201, r.text
    return owner, session, r.json()


@finding("BUG-02")
@pytest.mark.db
def test_bug02_a_purged_run_that_was_still_queued_does_not_stop_everyone_elses(admin, browser, configured, db, monkeypatch):
    """The purge accepts a Run that is still QUEUED (it only skips running ones) and blanks its
    config; the Run stays queued, is first in line, and claim() raises KeyError on it every time,
    so no one else's Run starts and the Worker's process ends (BUG-01) on every restart."""
    from litstorm.db.models import ResearchSession

    _, session, queued = _queued_into_the_trash(admin, browser, monkeypatch)
    bob = make_user(admin, browser, "audit-bob@example.org")
    _, _, bobs = research(bob)
    age(db, ResearchSession, session["id"], days=31)
    assert purge() >= 1

    claimed = []
    for _ in range(3):
        try:
            claim = _claim_one()
        except Exception as error:  # noqa: BLE001
            raise AssertionError(f"claiming raised {type(error).__name__}: {error}; Bob's Run was never reached") from error
        if claim is None:
            break
        claimed.append(str(claim.run_id))
    assert bobs["id"] in claimed


@finding("BUG-03")
@pytest.mark.db
def test_bug03_a_run_queued_while_its_session_is_trashed_is_not_started(admin, browser, configured, db, monkeypatch):
    """The Worker has no look at the Trash: the Run the race left in it is claimed and run
    (the owner's money, in a place they deleted)."""
    _queued_into_the_trash(admin, browser, monkeypatch)
    claim = _claim_one()
    assert claim is None, "the Worker claimed a Run that sits in a Session in the Trash"


# --- the supervisor and run_one ------------------------------------------------------------


@finding("BUG-04")
def test_bug04_an_error_in_the_supervisor_does_not_leave_the_child_running(tmp_path, monkeypatch):
    """Anything raised in supervise's loop (the heartbeat's database call, a bad line in
    events.jsonl) leaves the child process running with nobody watching it: no deadline, no
    cancel, no events; run_one then writes the Run as failed and refunded."""
    from litstorm.engines.base import Secrets
    from litstorm.runner import supervisor
    from test_supervisor import config

    started = []
    real = supervisor.start

    def spy(*args, **kwargs):
        proc = real(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(supervisor, "start", spy)
    beats = []

    def heartbeat():
        beats.append(1)
        if len(beats) >= 2:
            raise RuntimeError("the database is restarting")

    try:
        with pytest.raises(RuntimeError):
            supervisor.supervise(
                str(tmp_path), config([{"sleep": 30}]), Secrets(llm_api_key="sk-x"), heartbeat=heartbeat, poll_interval=0.05
            )
        time.sleep(0.5)
        alive = started[0].poll() is None
    finally:
        for proc in started:
            proc.kill()
            proc.wait()
    assert not alive, "the child went on running after the supervisor failed"


@finding("BUG-05")
@pytest.mark.db
def test_bug05_a_run_that_lost_its_lease_is_stopped(admin, browser, configured, db, monkeypatch):
    """The sweep marked the Run interrupted (its heartbeat was late); renew() says so and the
    Worker only logs it. The child works on to the end, the freed slot is filled by another Run,
    and its report is thrown away (finish matches no row)."""
    import threading
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import main, queue

    alice = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(alice)
    claim = _ready_to_run(db, run["id"], [{"stage": "research"}, {"sleep": 10}])
    monkeypatch.setattr(main, "DB_TOUCH", 0.2)

    def stall():
        time.sleep(1.0)
        with db_mod.sessions()() as s:
            s.execute(update(Run).where(Run.id == claim.run_id).values(
                lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=5)))
            s.commit()
            queue.sweep_interrupted(s)

    thread = threading.Thread(target=stall)
    thread.start()
    began = time.monotonic()
    main.run_one(claim)
    took = time.monotonic() - began
    thread.join()
    assert _state(db, run["id"]).status == "interrupted"
    assert took < 7, f"the child ran for {took:.1f}s after its Run was given up"


@finding("BUG-06")
@pytest.mark.db
def test_bug06_a_report_that_cannot_be_read_does_not_leave_the_run_running(admin, browser, configured, db, monkeypatch, tmp_path):
    """After supervise, run_one loads the report before it writes the outcome, outside any try:
    a report.json that fails validation ends the thread, no status is written, and the lease
    expiry later records the Run as interrupted and refunds it, though the engine had finished."""
    from litstorm.db.models import FINAL
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import main

    alice = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(alice)
    claim = _ready_to_run(db, run["id"], [])
    bad = tmp_path / "report.json"
    bad.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "supervise", lambda *a, **k: Outcome("succeeded", "succeeded", report_path=str(bad)))
    try:
        main.run_one(claim)
    except Exception:  # noqa: BLE001 - in the Worker this ends the Run's thread
        pass
    status = _state(db, run["id"]).status
    assert status in FINAL, f"the Run was left {status!r}"


def _cancel_pressed_then(run_id, outcome):
    """A supervise whose Run ends with `outcome` just after its owner pressed Cancel: the
    owner's request arrived after the last time the supervisor looked."""
    from sqlalchemy import update

    from litstorm import db as db_mod
    from litstorm.db.models import CANCELLING, Run

    def fake(*args, **kwargs):
        with db_mod.sessions()() as s:
            s.execute(update(Run).where(Run.id == run_id).values(status=CANCELLING))
            s.commit()
        return outcome

    return fake


@finding("BUG-07")
@pytest.mark.db
def test_bug07_a_run_the_owner_cancelled_is_not_recorded_as_succeeded(admin, browser, configured, db, monkeypatch):
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import main

    alice = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(alice)
    claim = _ready_to_run(db, run["id"], [])
    monkeypatch.setattr(main, "supervise", _cancel_pressed_then(claim.run_id, Outcome("succeeded", "succeeded")))
    main.run_one(claim)
    # supervisor.py: "Asked to stop, but finished first: the owner said stop, so the Run is cancelled".
    assert _state(db, run["id"]).status == "cancelled"


@finding("BUG-07")
@pytest.mark.db
def test_bug07_a_failure_after_cancel_was_pressed_does_not_give_the_quota_back(admin, browser, configured, db, monkeypatch):
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import main

    alice = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(alice)
    claim = _ready_to_run(db, run["id"], [])
    monkeypatch.setattr(main, "supervise", _cancel_pressed_then(claim.run_id, Outcome("failed", "engine_error", "boom")))
    main.run_one(claim)
    row = _state(db, run["id"])
    # "A Run that started and was then cancelled has cost something; the quota is kept."
    assert (row.status, row.quota_refunded) == ("cancelled", False)


@finding("BUG-08")
@pytest.mark.db
def test_bug08_a_timed_out_medical_run_releases_its_review(admin, browser, configured, db, monkeypatch):
    """Only a cancelled Run tells MRA to stop its review (main.run_one); one killed at the
    deadline is as unwanted, and MRA goes on spending on a review nobody waits for."""
    from dataclasses import replace

    from litstorm import medical, outcomes
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import main

    alice = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(alice)
    claim = _claim_one()
    claim.config = replace(claim.config, engine="medical", service={"url": "http://mra.test"})
    claim.secrets = replace(claim.secrets, service_api_key="k")
    released = []
    monkeypatch.setattr(medical, "release", lambda s, run_id, url, key: released.append(run_id))
    monkeypatch.setattr(main, "supervise", lambda *a, **k: Outcome("failed", outcomes.TIMED_OUT, "still running"))
    main.run_one(claim)
    assert released == [claim.run_id]


# --- quota, limits and the ways a Run starts ----------------------------------------------

from test_discussions import ask as _ask_turn  # noqa: E402
from test_discussions import finish as _finish_turn  # noqa: E402
from test_discussions import start as _start_discussion  # noqa: E402


@finding("BUG-09")
@pytest.mark.db
def test_bug09_two_research_starts_by_one_account_at_once_do_not_deadlock(admin, browser, configured, db, monkeypatch):
    """_start_session inserts the Session (a foreign key to the account's row takes a shared
    lock on it) and only then locks the same row FOR UPDATE in check_submit. Two starts at
    once each hold the shared lock and wait for the other's: PostgreSQL ends one with a
    deadlock and the page gets a 500. Without the barrier below, 7 of 8 pairs failed."""
    from litstorm.api import research as research_api

    _limits(admin, max_queued_per_user=50, monthly_run_quota=50)
    user = make_user(admin, browser, "audit-alice@example.org")
    _meet_at(monkeypatch, research_api, "_existing", after=True)

    def start():
        return user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "request_key": str(uuid.uuid4())})

    outcome = [r if isinstance(r, Exception) else r.status_code for r in _together(start, start)]
    assert outcome == [201, 201], f"two starts at once answered {outcome}"


@finding("BUG-09")
@pytest.mark.db
def test_bug09_two_discussion_starts_by_one_account_at_once_do_not_deadlock(admin, browser, configured, db, monkeypatch):
    """The same order of locks in api/discussions.start (Session inserted, then new_turn locks
    the account)."""
    from litstorm.api import discussions

    _limits(admin, max_queued_per_user=50, monthly_run_quota=50)
    user = make_user(admin, browser, "audit-alice@example.org")
    _meet_at(monkeypatch, discussions, "_existing", after=True)

    def start():
        return user.post("/api/discussions", json={"topic": "Songkran and tourism", "language": "th",
                                                   "request_key": str(uuid.uuid4())})

    outcome = [r if isinstance(r, Exception) else r.status_code for r in _together(start, start)]
    assert outcome == [201, 201], f"two starts at once answered {outcome}"


@finding("BUG-10")
@pytest.mark.db
def test_bug10_the_same_turn_sent_twice_at_once_makes_one_turn(admin, browser, configured, db, monkeypatch):
    """The second request waits on the Discussion's lock, then sees the first one's Turn in
    progress and answers 409 "a Turn is in progress", though the Turn it asked for was made."""
    from litstorm.api import discussions

    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    _meet_at(monkeypatch, discussions, "_existing", after=True)
    body = {"action": "say", "text": "What about the local economy?", "request_key": str(uuid.uuid4())}
    first, second = _together(
        lambda: user.post(f"/api/discussions/{d['id']}/turns", json=body),
        lambda: user.post(f"/api/discussions/{d['id']}/turns", json=body),
    )
    outcome = [r if isinstance(r, Exception) else r.status_code for r in (first, second)]
    assert outcome == [201, 201], f"the same request twice answered {outcome}"
    assert first.json()["id"] == second.json()["id"]


@finding("BUG-11")
@pytest.mark.db
def test_bug11_the_same_submit_sent_twice_at_the_last_unit_of_quota_is_not_refused(admin, browser, configured, db, monkeypatch):
    """With one unit left, the request that waited for the owner's row lock finds the other's
    Run counted and answers 429 quota_exhausted: the page says the quota is used up, while the
    Run it asked for is queued. Idempotency is not looked at again after the lock. (Same at
    the queue limit.)"""
    from litstorm.api import research as research_api

    _limits(admin, monthly_run_quota=2)
    user = make_user(admin, browser, "audit-alice@example.org")
    _, session, _ = research(user)  # takes the first unit
    _meet_at(monkeypatch, research_api, "_existing", after=True)
    body = {"topic": "Songkran again", "language": "th", "request_key": str(uuid.uuid4())}
    url = f"/api/sessions/{session['id']}/runs"
    first, second = _together(lambda: user.post(url, json=body), lambda: user.post(url, json=body))
    outcome = [r if isinstance(r, Exception) else r.status_code for r in (first, second)]
    assert outcome == [201, 201], f"the same request twice answered {outcome}"
    assert first.json()["id"] == second.json()["id"]


@finding("BUG-12")
@pytest.mark.db
def test_bug12_two_retries_of_a_failed_turn_at_once_make_one_turn(admin, browser, configured, db, monkeypatch):
    """retry() does not lock the Discussion (ask() does): both requests read the Turns, see none
    in progress, and each queues one: two Turns at a time in one Discussion."""
    from litstorm import quota
    from litstorm.db.models import Run

    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    failed = d["turns"][0]["id"]
    _finish_turn(db, failed, status="failed")
    _meet_at(monkeypatch, quota, "check_submit", after=False)
    results = _together(lambda: user.post(f"/api/runs/{failed}/retry"), lambda: user.post(f"/api/runs/{failed}/retry"))
    assert not any(isinstance(r, Exception) for r in results), results
    waiting = [r for r in db.query(Run).filter(Run.session_id == uuid.UUID(d["id"])).all() if r.status == "queued"]
    assert len(waiting) <= 1, f"{len(waiting)} Turns are queued in one Discussion"


@finding("BUG-13")
@pytest.mark.db
def test_bug13_trying_a_failed_run_again_twice_does_not_queue_it_twice(admin, browser, configured, db):
    """The Run is built with no request_key and the old one is never marked as retried, so
    every press of the button (the card of a failed Run keeps showing it) queues another copy
    and takes another unit of quota."""
    user = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(user)
    _failed(db, run["id"])
    first = user.post(f"/api/runs/{run['id']}/retry")
    assert first.status_code == 201, first.text
    second = user.post(f"/api/runs/{run['id']}/retry")
    assert second.status_code != 201 or second.json()["id"] == first.json()["id"], (
        f"a second Run was queued for the same failed Run (reserved: {user.get('/api/me/quota').json()['reserved']})"
    )


@finding("BUG-14")
@pytest.mark.db
def test_bug14_trying_again_a_run_of_a_mode_that_was_switched_off_is_refused(admin, browser, configured, db):
    """retry() skips what a fresh submit checks (new_run: the mode is still offered); the
    Administrator's switch is not honoured for it."""
    user = make_user(admin, browser, "audit-alice@example.org")
    _, _, run = research(user)
    _failed(db, run["id"])
    assert admin.put("/api/admin/engines/storm", json={"enabled": False}).status_code == 200
    r = user.post(f"/api/runs/{run['id']}/retry")
    assert r.status_code == 422 and r.json()["detail"] == "engine_not_available", (r.status_code, r.text)


@finding("BUG-15")
@pytest.mark.db
def test_bug15_a_turn_that_opened_a_block_and_failed_can_be_tried_again(admin, browser, configured, db):
    """The Turn that extends takes the next unit; if it fails with a refund its block goes
    away, the Discussion is "used up" again, and retry() (which never extends) answers 409
    turns_exhausted: the button the page offers for the failed Turn cannot succeed."""
    _limits(admin, turns_per_quota=2)
    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    step = _ask_turn(user, d["id"], action="step")
    assert step.status_code == 201, step.text
    _finish_turn(db, step.json()["id"])
    extended = _ask_turn(user, d["id"], action="step", extend=True)
    assert extended.status_code == 201, extended.text
    _finish_turn(db, extended.json()["id"], status="failed", refunded=True)
    r = user.post(f"/api/runs/{extended.json()['id']}/retry")
    assert r.status_code == 201, (r.status_code, r.text)


@finding("BUG-16")
@pytest.mark.db
def test_bug16_choosing_again_checks_the_new_model_for_the_mode(admin, browser, configured, db):
    """A parked Agent Run takes any enabled model, one that cannot call tools included: a fresh
    submit answers 422 model_cannot_use_tools, this goes to the queue and fails half-way."""
    from litstorm.db.models import LlmModel
    from litstorm.worker import queue

    model = configured["model"]
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "supports_tools": True})
    other = admin.post("/api/admin/llm-models", json={"label": "Plain", "provider": "openrouter", "model": "a/plain"}).json()
    user = make_user(admin, browser, "audit-alice@example.org")
    made = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "agent"})
    assert made.status_code == 201, made.text
    run_id = made.json()["runs"][0]["id"]
    db.get(LlmModel, uuid.UUID(model["id"])).enabled = False
    db.commit()
    queue.park_unavailable(db)
    db.commit()
    assert _state(db, run_id).status == "needs_selection"
    r = user.post(f"/api/runs/{run_id}/selection",
                  json={"llm_model_id": other["id"], "search_provider_id": configured["search"]["id"]})
    assert r.status_code == 422, (r.status_code, r.text)


# --- the Trash and the purge ---------------------------------------------------------------

import os  # noqa: E402

from test_mcp import _call, _data, _token  # noqa: E402


@finding("BUG-17")
@pytest.mark.db
def test_bug17_the_purge_blanks_what_a_discussions_owner_typed(admin, browser, configured, db):
    """"Deleted for good" (trash.py's docstring: topic, events, files, the report) leaves the
    Turn's own `text` (what the user typed for a "say" Turn) in runs.turn, and the Run's notes
    (what the system made of the topic) in runs.notes, for ever."""
    from litstorm.db.models import ResearchSession, Run

    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    said = _ask_turn(user, d["id"], action="say", text="my private question about the clinic").json()
    run = db.get(Run, uuid.UUID(said["id"]))
    run.notes = {"interpretation": {"reading": "a private reading of the topic"}}
    db.commit()
    _finish_turn(db, said["id"])
    assert user.delete(f"/api/sessions/{d['id']}").status_code == 204
    age(db, ResearchSession, d["id"], days=31)
    assert purge() == 2

    db.expire_all()
    left = [(str(r.id), r.turn, r.notes) for r in db.query(Run).filter(Run.purged_at.is_not(None)).all() if r.turn or r.notes]
    assert not left, f"after the purge, still stored: {left}"


def _mcp_start(token, topic="Songkran"):
    async def steps(session):  # the raw result: an assertion raised in here would come back in an ExceptionGroup
        return await session.call_tool(
            "research_start", {"topic": topic, "language": "th", "sources": ["arxiv"], "wait_seconds": 0})

    return _data(_call(token, steps))


def _mcp_list(token):
    async def steps(session):
        return await session.call_tool("research_list", {})

    return _data(_call(token, steps))


@finding("BUG-18")
@pytest.mark.db
def test_bug18_mcp_list_does_not_show_research_in_a_trashed_session(admin, browser, configured, db):
    """The tool filters Run.trashed_at only; trashing a Session or Project marks that row, not
    its Runs. The tool lists what the web app shows as in the Trash (their ids answer 404)."""
    from litstorm.db.models import Run

    user = make_user(admin, browser, "audit-alice@example.org")
    token = _token(user)
    started = _mcp_start(token)
    assert user.delete(f"/api/sessions/{db.get(Run, uuid.UUID(started['id'])).session_id}").status_code == 204
    assert user.get(f"/api/runs/{started['id']}").status_code == 404
    assert _mcp_list(token) == []


@finding("BUG-18")
@pytest.mark.db
def test_bug18_mcp_list_does_not_show_an_empty_shell_after_the_purge(admin, browser, configured, db):
    """After the purge a Run is a blank row (no topic, no Session); the tool still lists it."""
    from litstorm.db.models import ResearchSession, Run

    user = make_user(admin, browser, "audit-alice@example.org")
    token = _token(user)
    started = _mcp_start(token)
    session_id = str(db.get(Run, uuid.UUID(started["id"])).session_id)
    assert user.delete(f"/api/sessions/{session_id}").status_code == 204
    age(db, ResearchSession, session_id, days=31)
    assert purge() == 1
    assert _mcp_list(token) == []


@finding("BUG-18")
@pytest.mark.db
def test_bug18_an_integrations_recent_runs_leave_out_the_trash(admin, browser, configured, db):
    """The Administrator's integration page filters Run.trashed_at only, as the MCP tool does."""
    from litstorm import trash
    from litstorm.db.models import ResearchSession, Run

    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya"}).json()
    token = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None}).json()["token"]
    started = _mcp_start(token)
    trash.trash_session(db, db.get(ResearchSession, db.get(Run, uuid.UUID(started["id"])).session_id))
    db.commit()
    assert admin.get("/api/admin/integrations").json()[0]["recent"] == []


@finding("BUG-19")
@pytest.mark.db
def test_bug19_a_repeated_mcp_start_does_not_return_a_run_in_the_trash(admin, browser, configured, db):
    """_repeat_of matches on token, topic and time only: asked again within ten minutes after
    the owner trashed the Session, the agent is told "this is that run, no quota used" with an
    id every other call refuses (404), and nothing is started."""
    from datetime import datetime, timezone

    from litstorm.db.models import SUCCEEDED, Run

    user = make_user(admin, browser, "audit-alice@example.org")
    token = _token(user)
    started = _mcp_start(token)
    run = db.get(Run, uuid.UUID(started["id"]))
    run.status, run.started_at, run.finished_at = SUCCEEDED, datetime.now(timezone.utc), datetime.now(timezone.utc)
    db.commit()
    assert user.delete(f"/api/sessions/{run.session_id}").status_code == 204
    again = _mcp_start(token)
    assert again["id"] != started["id"]


@finding("BUG-20")
@pytest.mark.db
def test_bug20_an_administrator_cannot_read_an_integrations_run_that_is_in_a_trashed_session(admin, browser, configured, db):
    """deps.readable's fallback for an integration account's research tests the row's own
    trashed_at, not whether its Session or Project is in the Trash (the owner's path does)."""
    from litstorm import trash
    from litstorm.db.models import ResearchSession, Run

    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya"}).json()
    token = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None}).json()["token"]
    started = _mcp_start(token)
    assert admin.get(f"/api/runs/{started['id']}").status_code == 200
    trash.trash_session(db, db.get(ResearchSession, db.get(Run, uuid.UUID(started["id"])).session_id))
    db.commit()
    assert admin.get(f"/api/runs/{started['id']}").status_code == 404


@finding("BUG-21")
@pytest.mark.db
def test_bug21_a_run_whose_files_could_not_be_deleted_is_not_marked_purged(admin, browser, configured, db, monkeypatch):
    """rmtree(ignore_errors=True), then purged_at is set: the next purge skips the Run and the
    directory (report, work/, the Discussion's state) stays on disk for ever, unlogged."""
    import shutil

    from litstorm import settings
    from litstorm.db.models import Project

    user = make_user(admin, browser, "audit-alice@example.org")
    project, _, run = research(user)
    run_fake(db, run["id"])
    run_dir = os.path.join(settings.get().runs_dir, run["id"])
    assert os.path.exists(run_dir)
    assert user.delete(f"/api/projects/{project['id']}").status_code == 204
    age(db, Project, project["id"], days=31)

    def stuck(path, ignore_errors=False, **kwargs):  # a file held open, a read-only mount
        if not ignore_errors:
            raise PermissionError(path)

    monkeypatch.setattr(shutil, "rmtree", stuck)
    purge()
    monkeypatch.undo()
    purged = _state(db, run["id"]).purged_at is not None
    assert not (purged and os.path.exists(run_dir)), "marked purged, files still on disk"


@finding("BUG-22")
@pytest.mark.db
def test_bug22_restoring_a_session_inside_a_trashed_project_is_refused_or_works(admin, browser, configured, db):
    """restore() does not look at the parent: a stale tab's restore of the Session answers 204,
    the Session leaves the Trash's own clock (it can now only be purged with its Project), and
    it is still hidden, because its Project is in the Trash."""
    user = make_user(admin, browser, "audit-alice@example.org")
    project, session, _ = research(user)
    assert user.delete(f"/api/sessions/{session['id']}").status_code == 204
    assert user.delete(f"/api/projects/{project['id']}").status_code == 204
    r = user.post(f"/api/trash/session/{session['id']}/restore")
    visible = user.get(f"/api/sessions/{session['id']}").status_code == 200
    assert r.status_code != 204 or visible, "restore said done (204) and the Session is still hidden"


@finding("BUG-23")
@pytest.mark.db
def test_bug23_listing_topics_does_not_cost_a_query_per_topic(admin, browser, configured, db):
    """_sessions asks for each topic's latest status on its own: 1 + N statements, N up to 500."""
    from sqlalchemy import event

    from litstorm import db as db_mod
    from litstorm.db.models import ResearchSession, User

    user = make_user(admin, browser, "audit-alice@example.org")
    owner = db.query(User).filter_by(email="audit-alice@example.org").one()

    def seed(n):
        db.add_all([ResearchSession(owner_id=owner.id, title=f"topic {uuid.uuid4().hex[:6]}") for _ in range(n)])
        db.commit()

    def statements():
        seen = []
        engine = db_mod.engine()
        hit = lambda *args, **kwargs: seen.append(1)  # noqa: E731
        event.listen(engine, "before_cursor_execute", hit)
        try:
            assert user.get("/api/sessions?limit=500").status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", hit)
        return len(seen)

    seed(5)
    few = statements()
    seed(40)
    many = statements()
    assert many - few <= 3, f"5 topics took {few} statements, 45 took {many}"
