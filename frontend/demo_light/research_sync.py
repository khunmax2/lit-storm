"""Filing Deep Research's finished reports in the library, without asking it.

The report is written inside another application, in the reader's browser,
and that application knows nothing about this one — not who is signed in,
not where reports are kept, not that a library exists. The obvious ways
across are both expensive: teach it to sign in, or replace its front end.

Neither is necessary, because of one property of the deployment. Both
applications are served by the same proxy on the same host and port, so the
browser gives them the same origin and therefore the same localStorage — and
the research UI already writes every finished run there, report text
included. A component of ours, sitting on the same page, can simply read it.

Who the report belongs to never leaves Python, which is the part that knows.
There is no token, no shared secret and no second sign-in: the component
hands over a report, and this module files it under `auth.user_id()`.

What this does depend on is the shape of that history, which belongs to the
sibling and could change under us. `deploy/research-ui/check_research_ui_contract.py`
asserts it against the pinned image, so an upstream bump that breaks the
arrangement fails a check rather than silently syncing nothing for a month.
"""

import json
from pathlib import Path

import article_import
import article_store
import auth
import demo_util
import streamlit as st
import streamlit.components.v1 as components

# A dotfile at the root of a workspace: `article_store.list_articles` skips
# names beginning with "." and anything that is not a directory, so this is
# invisible to every page that lists reports.
LEDGER = ".research_synced.json"

# How many names to try before giving up on a collision. Two runs on the same
# topic produce the same heading, and the heading is the directory name.
NAME_ATTEMPTS = 20

_component = components.declare_component(
    "research_sync", path=str(Path(__file__).parent / "components" / "research_sync")
)


def _ledger_path(root):
    return Path(root) / LEDGER


def synced(root):
    """{run id: article name} for everything already filed from this browser.

    Read from disk rather than session state so that a refresh — which ends
    a Streamlit session but not a browser's storage — does not import every
    report a second time.
    """
    try:
        loaded = json.loads(_ledger_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _remember(root, run_id, name):
    entries = synced(root)
    entries[run_id] = name
    _ledger_path(root).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _free_name(root, title):
    """`title`, or the first numbered variant of it that is not taken.

    The manual import refuses a name that exists, and should: someone typed
    it and can type another. Nobody is typing here, and refusing would mean
    a report that was researched, paid for and finished simply never arrives
    — so a second run on one topic becomes "topic (2)".
    """
    if not article_import.directory_name(title):
        raise ValueError("empty title")
    taken = set(article_store.list_articles(root))
    candidate = article_import.directory_name(title)
    if candidate not in taken:
        return title
    for suffix in range(2, NAME_ATTEMPTS + 1):
        numbered = f"{title} ({suffix})"
        if article_import.directory_name(numbered) not in taken:
            return numbered
    raise FileExistsError(title)


def _file_report(root, report):
    """Write one handed-over report into the library. Returns its name."""
    title = (report.get("title") or report.get("query") or "").strip()
    if not title:
        raise ValueError("the report has no title")
    name = article_import.save(
        root,
        _free_name(root, title),
        report["report"],
        origin=f"deep-research:{report.get('id', '')}",
    )
    _remember(root, report["id"], name)
    return name


def watch():
    """Draw the watcher and file whatever it hands over.

    Returns the name of an article filed on this run, or None. Called from
    the Deep Research tab, beside the frame — the component is zero height
    and draws nothing.
    """
    if not auth.user_id():
        return None
    root = demo_util.working_dir()
    already = synced(root)

    # The ids go in so the component can tell a new report from one it has
    # already handed over; this is also what releases it to offer the next.
    handed = _component(saved=list(already), default=None)
    if not isinstance(handed, dict) or not handed.get("id"):
        return None
    if handed["id"] in already:
        # Streamlit replays the last component value on every rerun, so this
        # is the ordinary case once a report has been filed, not an error.
        return None
    if not (handed.get("report") or "").strip():
        return None

    try:
        return _file_report(root, handed)
    except (OSError, ValueError, FileExistsError) as error:  # noqa: BLE001
        # One report that cannot be filed must not take the tab down with
        # it, and must not be retried forever: the id is recorded as failed
        # so the watcher moves on, and the manual import is still there.
        _remember(root, handed["id"], "")
        st.session_state["research_sync_error"] = str(error)
        return None
