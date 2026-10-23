"""System status for Administrators: what failed, how long Runs take, the queue.

Failures are grouped into Issues, as an error tracker groups them: one per
reason, mode and model, so a provider's bad hour is one line, not forty.
Only what the system did is shown: when, whose, which mode and model, and
what the failure said with the topic taken out. Topics and reports stay the
owner's (docs/web-app-design.md, 2026-09-23 สิทธิ์ผู้ดูแลต่อเนื้อหางานวิจัย).

An Issue is open until an Administrator acknowledges it; one that happens
again afterwards opens again. Acknowledgements are shared by all
Administrators and kept in a system setting.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from litstorm import limits, outcomes
from litstorm.catalog import ENGINES
from litstorm.db.models import FAILED, INTERRUPTED, PERSON, Run, SystemSetting, User

ACKS = "monitor.acks"
MAX_DAYS = 30  # the longest window the page shows (api/admin.system_status)
DEFAULT_DAYS = 7  # the page's first window, and the badge's
MESSAGE_CHARS = 300
SAID_CHARS = 40
DIGITS = re.compile(r"\d+")
# A key a provider quoted back: "sk-or-v1-…", "AIza…", a long token.
KEYLIKE = re.compile(r"\b(sk-[\w-]{4}|AIza|gsk_|tvly-)[\w-]{8,}|\b[A-Za-z0-9_-]{40,}\b")
RECENT = 5

# The system's own failures: an Administrator has something to look at.
SYSTEM = {
    outcomes.BAD_CONFIGURATION,
    outcomes.RETRIES_EXHAUSTED,
    outcomes.SERVICE_UNAVAILABLE,
    outcomes.INTERRUPTED,
    outcomes.TIMED_OUT,
    outcomes.ENGINE_ERROR,
}
# Worth watching when they pile up, but often the topic's, not the system's.
WATCH = {outcomes.EMPTY_REPORT, outcomes.TRUNCATED_REPORT, outcomes.REFUSED}
# The rest (cancelled, service_declined) is someone's choice: not shown.


def _now():
    return datetime.now(timezone.utc)


def issue_key(reason, engine, model, said=""):
    """One Issue per reason, mode, model, and what the failure says, its numbers aside:
    a spent key and a wrong search address are both bad configuration, and two things to fix."""
    return f"{reason}:{engine}:{model}:{DIGITS.sub('#', said)[:SAID_CHARS]}"


def _label(engine):
    return ENGINES.get(engine, {}).get("label", engine)


def _model(run):
    return (run.config or {}).get("llm", {}).get("label", "")


def _said(run):
    """The failure's own words, without the topic in them."""
    said = run.message or ""
    if run.topic:
        said = said.replace(run.topic, "…")
    return KEYLIKE.sub("…", said)[:MESSAGE_CHARS]


def _reason(run):
    """Runs that failed before outcomes.from_message all said engine_error; their words still tell."""
    if run.reason == outcomes.ENGINE_ERROR:
        return outcomes.from_message(run.message)
    return run.reason


def acks(session):
    row = session.get(SystemSetting, ACKS)
    return dict(row.value) if row else {}


def acknowledge(session, keys, admin):
    row = session.get(SystemSetting, ACKS)
    if row is None:
        row = SystemSetting(key=ACKS, value={})
        session.add(row)
    now = _now()
    # Past the longest window an acknowledgement opens nothing again: let it go.
    kept = {k: v for k, v in row.value.items() if datetime.fromisoformat(v["at"]) > now - timedelta(days=MAX_DAYS)}
    # A new dict, so the JSONB column sees the change.
    row.value = {**kept, **{k: {"at": now.isoformat(), "by": str(admin.id)} for k in keys}}
    session.commit()


def _percentile(values, share):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def issues(session, since):
    rows = session.execute(
        select(Run, User.email, User.name, User.kind)
        .join(User, User.id == Run.owner_id)
        # A Run the Worker dropped has a status of its own.
        .where(Run.status.in_((FAILED, INTERRUPTED)), Run.finished_at >= since, Run.reason.in_(SYSTEM | WATCH))
        .order_by(Run.finished_at.desc())
    ).all()
    acked = acks(session)
    grouped = defaultdict(list)
    for run, email, name, kind in rows:
        who = email if kind == PERSON else name
        grouped[issue_key(_reason(run), run.engine, _model(run), _said(run))].append((run, who))
    out = []
    for key, found in grouped.items():
        latest = found[0][0]
        ack = acked.get(key)
        ack_at = datetime.fromisoformat(ack["at"]) if ack else None
        reason = _reason(latest)
        system = reason in SYSTEM
        out.append({
            "key": key,
            "reason": reason,
            "severity": "system" if system else "watch",
            "engine": latest.engine,
            "engine_label": _label(latest.engine),
            "model_label": _model(latest),
            "count": len(found),
            "users": sorted({who for _, who in found}),
            "first_at": found[-1][0].finished_at,
            "last_at": latest.finished_at,
            "message": _said(latest),
            "acknowledged_at": ack_at,
            "open": system and (ack_at is None or latest.finished_at > ack_at),
            "recent": [{"at": r.finished_at, "who": who} for r, who in found[:RECENT]],
        })
    # Open first, then the latest.
    out.sort(key=lambda i: (not i["open"], -i["last_at"].timestamp()))
    return out


def engines(session, since):
    rows = session.execute(
        select(Run.engine, Run.status, Run.reason, Run.started_at, Run.finished_at)
        .where(Run.finished_at >= since)
    ).all()
    by = defaultdict(lambda: {"runs": 0, "succeeded": 0, "failed": 0, "minutes": []})
    for engine, status, reason, started, finished in rows:
        e = by[engine]
        e["runs"] += 1
        if status == "succeeded":
            e["succeeded"] += 1
            if started and finished:
                e["minutes"].append((finished - started).total_seconds() / 60)
        elif reason in SYSTEM:
            e["failed"] += 1
    return [
        {"engine": engine, "engine_label": _label(engine), "runs": e["runs"], "succeeded": e["succeeded"], "failed": e["failed"],
         "p50_minutes": _percentile(e["minutes"], 0.5), "p90_minutes": _percentile(e["minutes"], 0.9)}
        for engine, e in sorted(by.items())
    ]


def queue(session):
    counts = dict(session.execute(
        select(Run.status, func.count()).where(Run.status.in_(("queued", "running", "cancelling"))).group_by(Run.status)
    ).all())
    oldest = session.scalar(select(func.min(Run.queued_at)).where(Run.status == "queued"))
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0) + counts.get("cancelling", 0),
        "oldest_wait_seconds": int((_now() - oldest).total_seconds()) if oldest else None,
        "max_running": limits.load(session).max_concurrent_total,
    }


def status(session, days=DEFAULT_DAYS):
    since = _now() - timedelta(days=days)
    found = issues(session, since)
    return {
        "since": since,
        "issues": found,
        "open_count": sum(1 for i in found if i["open"]),
        "engines": engines(session, since),
        "queue": queue(session),
    }


def badge(session, days=DEFAULT_DAYS):
    """For the sidebar and the home page: how many Issues are open, and the
    latest of them, without the rest of the page."""
    found = [i for i in issues(session, _now() - timedelta(days=days)) if i["open"]]
    return {"open_count": len(found), "last_at": max((i["last_at"] for i in found), default=None)}
