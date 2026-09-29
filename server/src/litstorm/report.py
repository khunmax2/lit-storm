"""report.json — the one shape every Engine's output is turned into.

The reading page, the Source Explorer and all three exports are drawn from
this file and nothing else (docs/adr/0005-report-json-file.md). An Engine
that records less than STORM does still fits: a Source may carry no
Evidence, and the reader is told so rather than shown something invented.

Shape, schema 1:

    {
      "schema": 1,
      "engine": "storm",
      "title": "...",
      "language": "th" | "en",
      "lead": "markdown, may be empty",
      "sections": [
        {"id": "s1", "heading": "...", "body": "markdown", "children": [...]}
      ],
      "sources": [
        {"id": 1, "url": "...", "title": "...", "description": "...",
         "evidence": ["passage the Engine used", ...]}
      ]
    }

Citations are the inline markers ``[n]`` in ``lead`` and ``body``; ``n`` is a
Source ``id``. Only cited Sources are kept, and every marker must resolve.
"""

import json
import os
import re
import tempfile

SCHEMA = 1
LANGUAGES = ("th", "en")

CITATION = re.compile(r"\[(\d+)\]")


class ReportError(ValueError):
    """The report does not have the shape above."""


def cited_ids(text):
    """Source ids cited in a piece of markdown, in order of first appearance."""
    seen = []
    for match in CITATION.finditer(text or ""):
        n = int(match.group(1))
        if n not in seen:
            seen.append(n)
    return seen


def walk(sections):
    """Every section, depth first, in reading order."""
    for section in sections:
        yield section
        yield from walk(section.get("children", []))


def all_text(report):
    """The lead and every section body, in reading order."""
    yield report.get("lead", "")
    for section in walk(report["sections"]):
        yield section.get("body", "")


def validate(report):
    """Raise ReportError unless `report` is a well-formed schema-1 report."""
    for key in ("schema", "engine", "title", "language", "lead", "sections", "sources"):
        if key not in report:
            raise ReportError(f"missing {key!r}")
    if report["schema"] != SCHEMA:
        raise ReportError(f"schema {report['schema']!r} is not {SCHEMA}")
    if report["language"] not in LANGUAGES:
        raise ReportError(f"language {report['language']!r} is not one of {LANGUAGES}")

    ids = set()
    for section in walk(report["sections"]):
        for key in ("id", "heading", "body", "children"):
            if key not in section:
                raise ReportError(f"section missing {key!r}: {section.get('heading')!r}")
        if section["id"] in ids:
            raise ReportError(f"duplicate section id {section['id']!r}")
        ids.add(section["id"])

    source_ids = set()
    for source in report["sources"]:
        for key in ("id", "url", "title", "evidence"):
            if key not in source:
                raise ReportError(f"source missing {key!r}: {source.get('url')!r}")
        source_ids.add(source["id"])

    cited = {n for text in all_text(report) for n in cited_ids(text)}
    dangling = cited - source_ids
    if dangling:
        raise ReportError(f"citations with no source: {sorted(dangling)}")
    uncited = source_ids - cited
    if uncited:
        raise ReportError(f"sources never cited: {sorted(uncited)}")


def is_empty(report):
    """True when the Engine finished but produced nothing worth reading.

    An empty report is refunded like a failure (docs/web-app-design.md,
    ความล้มเหลวกับการคืนโควตา).
    """
    has_text = any(text.strip() for text in all_text(report))
    return not has_text or not report["sources"]


def write(report, path):
    """Validate, then write so that a reader never sees half a file."""
    validate(report)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".report-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load(path):
    with open(path, encoding="utf-8") as f:
        report = json.load(f)
    validate(report)
    return report
