"""The Worker: `python -m litstorm.worker.main`.

One loop claims queued Runs while there are free slots and starts a thread
for each, then sleeps until Postgres says the queue changed (litstorm.notify)
or its timer runs out; the thread runs the Run's process through the supervisor and
reports to the database as it goes. The same loop sweeps Runs whose Worker
went away (docs/adr/0003: scheduled work lives in the Worker).

The Worker never restarts an interrupted Run. Several Workers can share one
database; claims are serialised in the database, not here.
"""

import logging
import os
import signal
import threading
import time

from litstorm import db, notify, search_cache, settings, trash
from litstorm import report as report_mod
from litstorm.db.models import RunEvent
from litstorm.runner.supervisor import Spare, supervise
from litstorm.worker import queue

log = logging.getLogger("litstorm.worker")

# Seconds between looks at the queue when nothing says to look sooner: a Run
# queued or a slot freed wakes the loop at once (litstorm.notify). The timer
# still catches what no notification marks: an Administrator raising a
# ceiling, a lease running out.
POLL = 5.0
PURGE_EVERY = 600.0  # seconds between emptying expired Trash
DB_TOUCH = 10.0  # seconds between lease renewals and cancel checks


class _Throttle:
    """Call `fn` at most once per `every` seconds; return the last answer."""

    def __init__(self, every, fn):
        self.every, self.fn = every, fn
        self.last_at, self.last = 0.0, None

    def __call__(self):
        now = time.monotonic()
        if now - self.last_at >= self.every:
            self.last_at, self.last = now, self.fn()
        return self.last


def run_one(claim, spare=None):
    Session = db.sessions()
    run_dir = os.path.join(settings.get().runs_dir, str(claim.run_id))

    def with_session(fn):
        with Session() as session:
            return fn(session)

    def heartbeat():
        if not with_session(lambda s: queue.renew(s, claim)):
            log.warning("run %s: lease lost", claim.run_id)

    def should_cancel():
        return with_session(lambda s: queue.cancel_requested(s, claim))

    def on_event(event):
        kind = event.get("type")
        data = {k: v for k, v in event.items() if k not in ("type", "t")}
        with Session() as session:
            session.add(RunEvent(run_id=claim.run_id, type=kind, data=data))
            session.commit()
        if kind == "stage":
            with_session(lambda s: queue.set_stage(s, claim, event["stage"]))
        elif kind == "note" and event.get("kind") in queue.NOTE_KINDS:
            with_session(lambda s: queue.add_note(s, claim, event["kind"], data))

    log.info("run %s: start (%s)", claim.run_id, claim.config.engine)
    try:
        outcome = supervise(
            run_dir,
            claim.config,
            claim.secrets,
            deadline=claim.deadline_seconds,
            heartbeat=_Throttle(DB_TOUCH, heartbeat),
            should_cancel=_Throttle(DB_TOUCH / 2, should_cancel),
            on_event=on_event,
            poll_interval=1.0,
            spare=spare,
        )
    except Exception as error:  # noqa: BLE001 - the Run must still end
        log.exception("run %s: supervisor failed", claim.run_id)
        from litstorm.runner.supervisor import Outcome

        outcome = Outcome("failed", "engine_error", f"{type(error).__name__}: {error}")

    title = sources = None
    if outcome.report_path:
        report = report_mod.load(outcome.report_path)
        title, sources = report["title"], len(report["sources"])
    written = with_session(lambda s: queue.finish(s, claim, outcome, title, sources))
    log.info("run %s: %s (%s)%s", claim.run_id, outcome.status, outcome.reason, "" if written else " — not ours any more")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    os.makedirs(settings.get().runs_dir, exist_ok=True)
    Session = db.sessions()
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    threads = []

    def purge():
        with Session() as session:
            purged = trash.purge(session, settings.get().runs_dir)
        if purged:
            log.info("purged %d run(s) from the Trash", purged)
        search_cache.sweep(settings.get().search_cache_dir)

    purge_now = _Throttle(PURGE_EVERY, purge)
    spare = Spare()
    spare.refill()
    wakeup = notify.QueueWakeup()

    log.info("worker ready")
    while not stopping.is_set():
        purge_now()
        with Session() as session:
            swept = queue.sweep_interrupted(session)
        if swept:
            log.warning("marked %d run(s) interrupted", swept)

        while not stopping.is_set():
            with Session() as session:
                claim = queue.claim(session)
            if claim is None:
                break
            thread = threading.Thread(
                target=run_one, args=(claim, spare), name=f"run-{claim.run_id}", daemon=True
            )
            thread.start()
            threads.append(thread)

        threads = [t for t in threads if t.is_alive()]
        wakeup.wait(POLL, stopping)

    # A Worker told to stop leaves its Runs to be swept as interrupted:
    # they are not restarted, by design.
    log.info("worker stopping with %d run(s) in progress", len(threads))
    wakeup.close()
    spare.close()


if __name__ == "__main__":
    main()
