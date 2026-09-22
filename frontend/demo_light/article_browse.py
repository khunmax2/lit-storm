"""Ordering and narrowing a library, without opening the articles in it.

A library grows by one report every few minutes and never shrinks on its
own, so alphabetical order stops being useful almost immediately: the thing
you want is nearly always the thing you just made, and alphabetical hides it
somewhere in the middle. Newest first is the default for that reason.

Everything decided here is decided from the *names* of the files in a
report's directory and, at most, one small JSON beside them. Nothing reads
an article to sort or filter a list of them — a library of two hundred
reports would otherwise read two hundred files to draw one page.
"""

import json
import os
from pathlib import Path

import article_store
import streamlit as st

# How a report came to be here. The first two are this app's own engines;
# the next two arrived from a framed sibling through `research_sync`; the
# last was carried in by hand.
STORM = "storm"
COSTORM = "costorm"
DEEP_RESEARCH = "deep-research"
AGENTS_RESEARCH = "agents-research"
IMPORTED = "imported"

ORIGINS = (STORM, COSTORM, DEEP_RESEARCH, AGENTS_RESEARCH, IMPORTED)

# Sorts, in the order they are offered. `NEWEST` is the default.
NEWEST = "newest"
OLDEST = "oldest"
NAME = "name"

SORTS = (NEWEST, OLDEST, NAME)

# The one filter that is not an origin: a run that stopped before it wrote
# an article. Kept in the same list because a reader picking from it is
# asking one question — "show me which ones?" — and does not care that the
# answers come from two different properties.
UNFINISHED = "unfinished"

ALL = ""


@st.cache_data(show_spinner=False)
def _recorded_origin(path, mtime):
    """The engine named in an `import_info.json`, or IMPORTED.

    `mtime` is in the cache key so a rewritten file is re-read; the file is
    tiny and written once, so this is read at most once per report.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return IMPORTED
    head = str(data.get("origin") or "").split(":", 1)[0]
    return head if head in (DEEP_RESEARCH, AGENTS_RESEARCH) else IMPORTED


def origin_of(files):
    """Which engine wrote this report, from what is in its directory."""
    recorded = files.get("import_info.json")
    if recorded:
        try:
            return _recorded_origin(recorded, os.path.getmtime(recorded))
        except OSError:
            return IMPORTED
    # Co-STORM saves the discussion beside the article; STORM has no such
    # file. Both write conversation_log.json, so that one cannot tell them
    # apart and is not asked.
    if "costorm_conversation.json" in files:
        return COSTORM
    return STORM


def when_of(files):
    """When this report last changed, as a timestamp. 0 when unreadable.

    The article's own file if there is one, because that is the moment the
    report became a report. An interrupted run has no article, so the newest
    thing it did manage to write stands in for it.
    """
    article = article_store.completed_article(files)
    candidates = [article] if article else list(files.values())
    newest = 0.0
    for path in candidates:
        try:
            newest = max(newest, os.path.getmtime(path))
        except OSError:
            continue
    return newest


def origins_present(articles):
    """The origins this library actually contains, in a stable order.

    A filter offering choices that match nothing is a filter that wastes a
    click to prove there is nothing there.
    """
    found = {origin_of(files) for files in articles.values()}
    return [origin for origin in ORIGINS if origin in found]


def has_unfinished(articles):
    return any(
        not article_store.completed_article(files) for files in articles.values()
    )


def arrange(articles, sort=NEWEST, show=ALL):
    """Names of the articles to draw, filtered and in order.

    `show` is an origin, UNFINISHED, or ALL.
    """
    names = list(articles)

    if show == UNFINISHED:
        names = [
            n for n in names if not article_store.completed_article(articles[n])
        ]
    elif show in ORIGINS:
        names = [n for n in names if origin_of(articles[n]) == show]

    if sort == NAME:
        return sorted(names, key=lambda n: n.lower())
    # Ties broken by name, and in the same direction whichever way the dates
    # run: two reports written in the same second would otherwise swap
    # places between renders. Negating the timestamp rather than reversing
    # the whole sort is what keeps the tiebreak pointing one way.
    if sort == OLDEST:
        return sorted(names, key=lambda n: (when_of(articles[n]), n.lower()))
    return sorted(names, key=lambda n: (-when_of(articles[n]), n.lower()))
