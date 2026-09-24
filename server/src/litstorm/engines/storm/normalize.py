"""Turn what STORM wrote to disk into a report (see litstorm.report).

STORM leaves the article as markdown-ish text with ``#`` headings and inline
``[n]`` markers, and the sources in url_to_info.json, keyed by URL, with
``url_to_unified_index`` giving each URL its ``n``. Evidence is per Source,
not per marker: STORM pools every passage it used from one URL.

Two things are done here that STORM does not do:

* Sources are renumbered 1, 2, 3 ... in the order a reader meets them, and
  the markers rewritten to match. Polishing can drop passages, which leaves
  gaps like [1], [4], [9] otherwise.
* A marker with no source behind it is removed rather than shown pointing
  at nothing. The count is returned so the caller can log it.
"""

import json
import os
import re

from litstorm import report as report_mod

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

# STORM's polishing step files the lead under this heading.
LEAD_HEADING = "summary"


POLISHED_REFERENCES = "url_to_info_polished.json"

# Each article text, with the references its citation numbers belong to.
# STORM's polishing renumbers citations without rewriting url_to_info.json,
# so polished text is only ever read with the references saved beside it by
# our engine; without them the draft is used instead.
_PAIRS = (
    ("storm_gen_article_polished.txt", POLISHED_REFERENCES),
    ("storm_gen_article.txt", "url_to_info.json"),
)


def article_paths(article_dir):
    """(article, references) paths that agree with each other, or None."""
    for text, refs in _PAIRS:
        text_path = os.path.join(article_dir, text)
        refs_path = os.path.join(article_dir, refs)
        if os.path.exists(text_path) and os.path.exists(refs_path):
            return text_path, refs_path
    return None


def parse_sections(text):
    """(lead, sections) from STORM's article text."""
    lead_lines = []
    root = {"children": [], "level": 0}
    stack = [root]
    current = None
    in_lead_section = False

    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            if level == 1 and heading.lower() == LEAD_HEADING:
                in_lead_section = True
                current = None
                continue
            in_lead_section = False
            node = {"heading": heading, "level": level, "lines": [], "children": []}
            while stack[-1]["level"] >= level:
                stack.pop()
            stack[-1]["children"].append(node)
            stack.append(node)
            current = node
        elif in_lead_section or current is None:
            lead_lines.append(line)
        else:
            current["lines"].append(line)

    counter = iter(range(1, 10_000))

    def finish(nodes):
        return [
            {
                "id": f"s{next(counter)}",
                "heading": node["heading"],
                "body": "\n".join(node["lines"]).strip(),
                "children": finish(node["children"]),
            }
            for node in nodes
        ]

    return "\n".join(lead_lines).strip(), finish(root["children"])


MARKER = re.compile(r"(\s*)\[(\d+)\]")


def _rewrite(text, mapping):
    """Replace [old] with [new]; drop markers with no mapping, and the space
    before them. Returns (text, dropped)."""
    dropped = 0

    def swap(match):
        nonlocal dropped
        old = int(match.group(2))
        if old in mapping:
            return f"{match.group(1)}[{mapping[old]}]"
        dropped += 1
        return ""

    return MARKER.sub(swap, text), dropped


def normalize(article_dir, topic, language):
    """(report, dropped_markers) for one STORM output directory."""
    paths = article_paths(article_dir)
    if paths is None:
        raise FileNotFoundError(f"no article with its references in {article_dir}")
    text_path, refs_path = paths
    with open(text_path, encoding="utf-8") as f:
        lead, sections = parse_sections(f.read())
    with open(refs_path, encoding="utf-8") as f:
        refs = json.load(f)
    by_index = {
        int(index): refs["url_to_info"].get(url, {"url": url})
        for url, index in refs.get("url_to_unified_index", {}).items()
    }

    draft = {"lead": lead, "sections": sections}
    order = []
    for text in report_mod.all_text(draft):
        for n in report_mod.cited_ids(text):
            if n in by_index and n not in order:
                order.append(n)
    mapping = {old: new for new, old in enumerate(order, start=1)}

    dropped = 0
    lead, d = _rewrite(lead, mapping)
    dropped += d
    for section in report_mod.walk(sections):
        section["body"], d = _rewrite(section["body"], mapping)
        dropped += d

    sources = []
    for old in order:
        info = by_index[old]
        sources.append(
            {
                "id": mapping[old],
                "url": info.get("url", ""),
                "title": info.get("title") or info.get("url", ""),
                "description": info.get("description", ""),
                "evidence": [s for s in info.get("snippets", []) if s and s.strip()],
            }
        )

    result = {
        "schema": report_mod.SCHEMA,
        "engine": "storm",
        "title": topic,
        "language": language,
        "lead": lead,
        "sections": sections,
        "sources": sources,
    }
    report_mod.validate(result)
    return result, dropped
