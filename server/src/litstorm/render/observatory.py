"""The observatory: one HTML page that shows a Run's agents at work, then the
report they wrote with every cited sentence lit up against the Source passage
it rests on (docs/adr/0011).

The page (observatory.html) draws everything from data carried inside it:

- the Run, and its events as the owner sees them on the Run page (stages,
  usage, and the notes perspectives / tree / flow / browsed), from which it
  builds the agents as the MCP canvas does (docs/adr/0010);
- the report, when there is one: its text, and each Source's evidence, the
  passages the engine kept from it.

Two ways to open it:

- **a file** (export format `observatory`, also through research_export): it
  replays the Run on its own, with no request at all, so it opens offline or
  in a sandboxed frame such as Agenta's file viewer;
- **live** (`GET /api/runs/{id}/observatory`, signed in): it starts from what
  has happened so far and then reads the Run and, once it succeeds, its report
  from the same origin.

Everything the Run or the model wrote goes into the page as JSON and is put on
screen as text, never as markup; `<` is escaped in the JSON, so nothing in it
can close the script that carries it.
"""

import html
import json
import os
import re
from functools import cache

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "observatory.html")

# A file asks for nothing. The live page reads the Run and its report, and only from its own origin.
CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
LIVE_CSP = CSP + "; connect-src 'self'"

# The notes a Run's owner sees (api/research.py, _SHOWN_NOTES) that the page draws.
NOTES = {"perspectives", "browsed", "tree", "flow", "interpretation"}
EVIDENCE_CHARS = 700  # per passage: enough to read the match, not the whole page


@cache
def _template():
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read()


def run_facts(run, engine_label="", model_label=""):
    """What the page's header shows about a Run."""

    def iso(d):
        return d.isoformat() if d else None

    return {
        "id": str(run.id),
        "topic": run.topic,
        "language": run.language,
        "engine": run.engine,
        "engine_label": engine_label,
        "model_label": model_label,
        "depth": (run.config or {}).get("depth", "standard"),
        "status": run.status,
        "reason": run.reason,
        "message": run.message,
        "queued_at": iso(run.queued_at),
        "started_at": iso(run.started_at),
        "finished_at": iso(run.finished_at),
    }


def events_out(events):
    """A Run's events as the page reads them: stages, usage and the notes it draws."""
    return [
        {"id": e.id, "at": e.at.isoformat() if e.at else None, "type": e.type, "data": e.data}
        for e in events
        if e.type in ("stage", "usage") or (e.type == "note" and (e.data or {}).get("kind") in NOTES)
    ]


def report_out(report):
    """The parts of report.json the page uses."""
    if not report:
        return None

    def section(s):
        return {"heading": s.get("heading", ""), "body": s.get("body", ""), "children": [section(c) for c in s.get("children") or []]}

    return {
        "title": report.get("title", ""),
        "language": report.get("language", ""),
        "lead": report.get("lead", ""),
        "sections": [section(s) for s in report.get("sections") or []],
        "sources": [
            {
                "id": s.get("id"),
                "url": s.get("url", ""),
                "title": s.get("title", ""),
                "description": (s.get("description") or "")[:EVIDENCE_CHARS],
                "evidence": [str(x)[:EVIDENCE_CHARS] for x in (s.get("evidence") or [])][:4],
            }
            for s in report.get("sources") or []
        ],
    }


def render(run_facts_, events, report=None, live=None):
    """The page. `live` is {"run": url, "report": url}, relative to the page,
    for the live page; None makes a file that replays itself."""
    data = {"run": run_facts_, "events": events, "report": report_out(report), "live": live}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    # In a script element only "</script" (or "<!--") could end it early: no "<" survives.
    blob = blob.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    title = (report or {}).get("title") or run_facts_.get("topic") or "DeepLit"
    fill = {
        "CSP": LIVE_CSP if live else CSP,
        "LANG": "th" if run_facts_.get("language") == "th" else "en",
        "TITLE": html.escape(f"Observatory — {title}"),
        "DATA": blob,
    }
    # One pass, so nothing a value carries is filled in again.
    return re.sub(r"__OBS_([A-Z]+)__", lambda m: fill[m.group(1)], _template())
