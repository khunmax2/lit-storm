"""Waking on Postgres notifications instead of polling (migration 0012).

Postgres sends them when a transaction commits, so a listener never hears of
a Run before it can read it. A notification is only a nudge: whoever wakes
reads the database for what changed, and everyone still re-reads on a timer,
so a lost connection or a missed nudge costs a delay, never a Run.

- The Worker waits on `litstorm_queue` between claims (QueueWakeup).
- Each API process keeps one connection on `litstorm_run` and passes each
  Run's nudge to the live streams watching that Run (RunHub).
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict

import psycopg
from sqlalchemy.engine import make_url

from litstorm import settings

log = logging.getLogger("litstorm.notify")

QUEUE = "litstorm_queue"
RUN = "litstorm_run"
RETRY = 2.0  # seconds before listening again after the connection failed


def _dsn():
    url = make_url(settings.get().database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _listen(channel):
    conn = psycopg.connect(_dsn(), autocommit=True)
    conn.execute(f"LISTEN {channel}")
    return conn


class QueueWakeup:
    """The Worker's pause between looks at the queue, cut short when a Run
    is queued or leaves a slot."""

    def __init__(self):
        self._conn = None

    def wait(self, timeout, stopping):
        """Up to `timeout` seconds; True if a notification ended it."""
        try:
            if self._conn is None or self._conn.closed:
                self._conn = _listen(QUEUE)
            woke = any(True for _ in self._conn.notifies(timeout=timeout, stop_after=1))
            if woke:
                # A burst (many Runs queued at once) is one look at the queue.
                for _ in self._conn.notifies(timeout=0):
                    pass
            return woke
        except psycopg.Error as error:
            log.warning("queue notifications unavailable (%s); polling", error)
            self.close()
            stopping.wait(timeout)
            return False

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class RunHub:
    """One listening connection per process, shared by every live stream in
    it; a stream subscribes to its Run and is woken on that Run's nudges.

    The connection lives in a thread of its own: psycopg's async connection
    needs a selector event loop, which Windows (where the tests run) does
    not use by default. Each subscriber is an asyncio.Event set through its
    own loop.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = defaultdict(set)  # run id -> {(loop, Event)}
        self._thread = None

    def subscribe(self, run_id):
        key = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._subscribers[str(run_id)].add(key)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._listen, name="run-notifications", daemon=True)
                self._thread.start()
        return key

    def unsubscribe(self, run_id, key):
        with self._lock:
            keys = self._subscribers.get(str(run_id))
            if keys is not None:
                keys.discard(key)
                if not keys:
                    del self._subscribers[str(run_id)]

    def _wake(self, run_ids=None):
        with self._lock:
            ids = list(self._subscribers) if run_ids is None else run_ids
            keys = [k for run_id in ids for k in self._subscribers.get(run_id, ())]
        for loop, event in keys:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # its loop has closed; it unsubscribes as it ends
                pass

    def _listen(self):
        while True:
            try:
                with _listen(RUN) as conn:
                    # Whatever changed while there was no connection.
                    self._wake()
                    for note in conn.notifies():
                        self._wake([note.payload])
            except Exception as error:  # noqa: BLE001 - streams fall back to their timer meanwhile
                log.warning("run notifications unavailable (%s); retrying", error)
                time.sleep(RETRY)


runs = RunHub()


async def woken(key, timeout):
    """Until the subscription is woken or `timeout` seconds pass; True if woken."""
    _, event = key
    try:
        await asyncio.wait_for(event.wait(), timeout)
    except asyncio.TimeoutError:
        return False
    event.clear()
    return True
