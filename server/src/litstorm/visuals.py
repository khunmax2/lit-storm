"""Visual blocks for a report: charts, key figures, timelines, comparisons,
diagrams and a glossary, drawn beside the text in the interactive export
(docs/research/2026-10-01-interactive-html-report.md, §8).

The model never writes markup. It is shown the report's evidence cut into
numbered facts (F1, F2, ...) and answers with blocks in the small shape
below, naming for every value the fact it came from. Nothing it says is
kept on trust:

- a fact must exist, and its Source is the fact's, not the model's word;
- a number must appear in its fact's text, a date's year likewise, and a
  glossary term too;
- what fails is dropped, never filled in, and a block left too thin by
  that is dropped whole.

A report with no Evidence (Agent Research) gets facts from its own cited
sentences instead, and no numeric blocks at all: a number the reader cannot
trace to a source passage is not drawn.

Stored as visuals.json beside report.json; report.json itself never changes
(docs/adr/0005).
"""

import hashlib
import json
import math
import os
import re
import tempfile

from litstorm import report as report_mod

SCHEMA = 1

MAX_BLOCKS = 6
TYPES = ("stat_cards", "chart", "timeline", "comparison", "diagram", "glossary")
NUMERIC = ("stat_cards", "chart")
CHARTS = ("bar", "line", "pie")
DIAGRAMS = ("flow", "cycle", "hierarchy")

# Limits a block is cut to; beyond them a figure stops being readable.
MAX_ITEMS = {"stat_cards": 6, "timeline": 12, "comparison": 8, "glossary": 8}
MAX_SERIES, MAX_POINTS = 4, 12
MAX_COLUMNS = 4
MAX_NODES = 10
MAX_TEXT = {"title": 100, "label": 80, "detail": 200, "definition": 240, "unit": 20, "cell": 120, "note": 160}

# How the report's evidence is cut into facts.
FACT_CHARS = 280
MAX_FACT_CHARS = 24000

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_NODE_ID = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‍⁠﻿]")


class VisualsError(ValueError):
    """The visuals file does not have the shape above."""


# --- facts -------------------------------------------------------------------


def _pieces(text, language):
    """A passage in reading-sized pieces: at line and sentence ends, then at
    spaces (Thai marks phrases with spaces, not full stops)."""
    text = _CONTROL.sub("", text or "")
    parts = []
    for line in re.split(r"\n+", text):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])", line) if language == "en" else [line]
        for sentence in sentences:
            while len(sentence) > FACT_CHARS:
                cut = sentence.rfind(" ", FACT_CHARS // 2, FACT_CHARS)
                cut = cut if cut > 0 else FACT_CHARS
                parts.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if sentence:
                parts.append(sentence)
    # Short pieces joined, so a fact is a sentence rather than a fragment.
    merged = []
    for part in parts:
        if merged and len(merged[-1]) + len(part) + 1 <= FACT_CHARS and len(merged[-1]) < 80:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [p for p in merged if len(p) >= 12]


def _strip_markdown(text):
    """Page furniture out of a passage: images, link targets, bare addresses,
    heading and list marks, table rules. Evidence is scraped web text."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text or "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<?https?://\S+>?|\bdoi:\s*\S+", " ", text, flags=re.I)
    text = re.sub(r"[*_`#>|]+", " ", text)
    return re.sub(r"-{3,}|={3,}", " ", text)


_LETTER = re.compile(r"[A-Za-zก-๎]")


_REFERENCES = re.compile(r"\b(?:references|bibliography|works cited)\b|บรรณานุกรม|เอกสารอ้างอิง", re.I)
_CITATION_LIKE = re.compile(
    r"\(\d{4}[a-z]?\)|\bet al\.|[A-Z][A-Za-z'-]+, (?:[A-Z]\. ?){1,3}(?:,|&|\(|and)|\b\d+\s*\(\d+\)\s*,\s*\d+\s*[-–]\s*\d+"
)


def _without_references(passage):
    """A page's text up to its list of references: those years are the
    papers', not the topic's."""
    match = _REFERENCES.search(passage)
    return passage[: match.start()] if match and match.start() > len(passage) * 0.3 else passage


def _readable(piece):
    """Mostly words, not a run of symbols, numbers and names of files — nor a
    reference to a paper."""
    if _CITATION_LIKE.search(piece):
        return False
    return len(_LETTER.findall(piece)) >= 0.5 * len(piece.replace(" ", ""))


# A number a figure can be made of: with a unit, a percentage, or a year.
_MEASURE = re.compile(
    r"\d[\d,.]*\s*(?:%|percent|per cent|ร้อยละ|เปอร์เซ็นต์|ล้าน|พัน|หมื่น|แสน|บาท|ตัน|ไร่|กิโล|กก\.|กม\.|คน|ราย|"
    r"million|billion|thousand|tons?|tonnes?|kg|km|usd|us\$|\$|baht|people|cases)"
    r"|(?:ร้อยละ|\$|usd)\s*\d|\b(?:1[89]\d\d|20\d\d|2[45]\d\d)\b",
    re.I,
)


def _weight(fact):
    return len(_MEASURE.findall(_normal(fact["text"])))


def has_evidence(report):
    return any(source.get("evidence") for source in report["sources"])


def facts(report):
    """The passages the model may draw from, numbered.

    From the Sources' Evidence when there is any; otherwise from the report's
    own sentences that cite a Source, marked as such.

    When there is more than fits, passages with figures (a unit, a
    percentage, a year) go first, taken from each Source in turn so that no
    one Source fills the sheet; the rest follow the same way.
    """
    language = report["language"]
    found = []
    if has_evidence(report):
        for source in report["sources"]:
            for passage in source.get("evidence") or []:
                for piece in _pieces(_strip_markdown(_without_references(passage)), language):
                    found.append({"source": source["id"], "text": piece, "origin": "evidence"})
    else:
        for text in report_mod.all_text(report):
            for piece in _pieces(_strip_markdown(text), language):
                cited = report_mod.cited_ids(piece)
                if cited:
                    clean = re.sub(r"\s+", " ", report_mod.CITATION.sub("", piece)).strip()
                    found.append({"source": cited[0], "text": clean, "origin": "report"})
    seen, unique = set(), []
    for fact in found:
        key = _normal(fact["text"])
        if key not in seen and _readable(fact["text"]):
            seen.add(key)
            unique.append(fact)

    def in_turn(group):
        queues = {}
        for fact in group:
            queues.setdefault(fact["source"], []).append(fact)
        while queues:
            for source in list(queues):
                yield queues[source].pop(0)
                if not queues[source]:
                    del queues[source]

    ordered = list(in_turn([f for f in unique if _weight(f)])) + list(in_turn([f for f in unique if not _weight(f)]))
    kept, total = [], 0
    for fact in ordered:
        if total + len(fact["text"]) > MAX_FACT_CHARS:
            continue  # a shorter one may still fit
        kept.append(fact)
        total += len(fact["text"])
    # Numbered in the report's order of Sources, as a reader would expect.
    order = {s["id"]: i for i, s in enumerate(report["sources"])}
    position = {id(f): i for i, f in enumerate(unique)}
    kept.sort(key=lambda f: (order.get(f["source"], 0), position[id(f)]))
    return [{"id": f"F{i}", **fact} for i, fact in enumerate(kept, 1)]


# --- checks ------------------------------------------------------------------


def _normal(text):
    text = _CONTROL.sub("", str(text or "")).translate(_THAI_DIGITS).lower()
    return re.sub(r"\s+", " ", text).strip()


def numbers_in(text):
    """Every number written in a passage, as floats: Thai digits read, and a
    comma taken as a thousands mark when three digits follow it."""
    out = []
    for match in _NUMBER.finditer(_normal(text)):
        raw = match.group(0)
        raw = re.sub(r",(?=\d{3}(?:\D|$))", "", raw).replace(",", ".")
        if raw.count(".") > 1:  # 1.234.567 or a version number: read the parts
            out.extend(float(p) for p in raw.split(".") if p)
            continue
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def _number_in(value, text):
    return any(math.isclose(value, n, rel_tol=1e-9, abs_tol=1e-9) for n in numbers_in(text))


# "(Hinrichsen and Robey, 2000)": the year a paper came out, not an event's.
_IN_TEXT_CITATION = re.compile(r"\([^()]{0,80}?,\s*(?:\d{4}[a-z]?|n\.d\.)\)")


def _year_in(date, text):
    """A date's year is in the passage, in either era (2024 or 2567) — and
    not only as the year of a paper it cites."""
    match = re.match(r"^\s*(\d{4})", _normal(date))
    if not match:
        return False
    year = int(match.group(1))
    years = {year, year + 543, year - 543}
    text = _IN_TEXT_CITATION.sub(" ", text)
    return any(int(n) in years for n in numbers_in(text) if n.is_integer())


_WORD = re.compile(r"[a-z0-9\u0e01-\u0e4e]{3,}")


def _grounded(text, fact_text):
    """Some word of `text` (three letters or more) is in the passage: a label
    that shares nothing with its fact was made up."""
    passage = _normal(fact_text)
    return any(word in passage for word in _WORD.findall(_normal(text)))


def _when(date):
    """A date for ordering: Buddhist-era years (2567) read as CE (2024)."""
    text = _normal(date)
    match = re.match(r"^(\d{4})(.*)$", text)
    if not match:
        return text
    year = int(match.group(1))
    return f"{year - 543 if year > 2400 else year:04d}{match.group(2)}"


def _text(value, limit):
    if value is None:
        return ""
    text = _CONTROL.sub("", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        found = numbers_in(value)
        return found[0] if len(found) == 1 else None
    return None


def _cite(fact_id, by_id):
    fact = by_id.get(str(fact_id or "").strip().upper())
    if not fact:
        return None
    return {"fact": fact["id"], "source": fact["source"], "text": fact["text"], "origin": fact["origin"]}


class _Checker:
    def __init__(self, report, facts_):
        self.by_id = {f["id"]: f for f in facts_}
        self.sections = {s["id"] for s in report_mod.walk(report["sections"])}
        self.numeric = has_evidence(report)

    @staticmethod
    def _holds_row(passage, label, cells):
        """A comparison row its passage bears out: a word of it there, and
        every number in its cells written there."""
        if not any(_grounded(t, passage) for t in [label, *cells]):
            return False
        return all(_number_in(n, passage) for c in cells for n in numbers_in(c))

    def _row_passage(self, label, cells):
        """The passage a row with numbers came from, when it named the wrong
        one: the first that holds every numeric cell as written (spaces
        aside) and a word of its label."""
        numeric = [re.sub(r"\s+", "", _normal(c)) for c in cells if numbers_in(c)]
        if not numeric:
            return None
        for fact in self.by_id.values():
            flat = re.sub(r"\s+", "", _normal(fact["text"]))
            if all(c in flat for c in numeric) and _grounded(label, fact["text"]):
                return _cite(fact["id"], self.by_id)
        return None

    def anchor(self, raw):
        section = raw.get("section") if isinstance(raw, dict) else raw
        return section if section in self.sections else "lead"

    def stat_cards(self, b):
        items = []
        for raw in (b.get("items") or [])[: MAX_ITEMS["stat_cards"]]:
            if not isinstance(raw, dict):
                continue
            cite, value = _cite(raw.get("fact"), self.by_id), _number(raw.get("value"))
            if not cite or value is None or not _number_in(value, cite["text"]):
                continue
            as_of = _text(raw.get("as_of"), 20)
            if as_of and re.match(r"^\s*\d{4}", _normal(as_of)) and not _year_in(as_of, cite["text"]):
                as_of = ""
            items.append({
                "label": _text(raw.get("label"), MAX_TEXT["label"]),
                "value": value,
                "unit": _text(raw.get("unit"), MAX_TEXT["unit"]),
                "as_of": as_of,
                "cite": cite,
            })
        items = [i for i in items if i["label"]]
        return ({"items": items}, None) if items else (None, "no figure found in its facts")

    def chart(self, b):
        kind = b.get("chart")
        if kind not in CHARTS:
            return None, f"unknown chart {kind!r}"
        asked, series = 0, []
        for raw in (b.get("series") or [])[:MAX_SERIES]:
            if not isinstance(raw, dict):
                continue
            points = []
            for p in (raw.get("points") or [])[:MAX_POINTS]:
                asked += 1
                if not isinstance(p, dict):
                    continue
                cite, y = _cite(p.get("fact"), self.by_id), _number(p.get("y"))
                x = _text(p.get("x"), MAX_TEXT["label"])
                if not cite or y is None or not x or not _number_in(y, cite["text"]):
                    continue
                points.append({"x": x, "y": y, "cite": cite})
            if points:
                series.append({"name": _text(raw.get("name"), MAX_TEXT["label"]), "points": points})
        kept = sum(len(s["points"]) for s in series)
        # Too little survives, or too much was not found: the picture would mislead.
        if kept < 2 or kept * 2 < asked:
            return None, f"{kept} of {asked} values found in their facts"
        if kind == "pie":
            if len(series) != 1 or any(p["y"] < 0 for p in series[0]["points"]):
                kind = "bar"  # a pie of several series, or of negatives, is no pie
        if kind == "line":
            # A line joins points in order: they must be years or dates, each
            # year in its own fact. A series needs two such points, and not
            # one passage's single figure repeated (an average over 1990-1997
            # is not a value in 1990 and another in 1997).
            if not all(re.match(r"^\s*\d{4}", p["x"]) for s in series for p in s["points"]):
                kind = "bar"
            else:
                for s in series:
                    s["points"] = [p for p in s["points"] if _year_in(p["x"], p["cite"]["text"])]
                    s["points"].sort(key=lambda p: _when(p["x"]))
                series = [
                    s for s in series
                    if len(s["points"]) >= 2 and len({(p["cite"]["fact"], p["y"]) for p in s["points"]}) > 1
                ]
                if sum(len(s["points"]) for s in series) < 2:
                    return None, "no series with two dated values of their own"
        return {
            "chart": kind,
            "unit": _text(b.get("unit"), MAX_TEXT["unit"]),
            "x_label": _text(b.get("x_label"), MAX_TEXT["label"]),
            "y_label": _text(b.get("y_label"), MAX_TEXT["label"]),
            "series": series,
        }, None

    def timeline(self, b):
        events = []
        for raw in (b.get("events") or [])[: MAX_ITEMS["timeline"]]:
            if not isinstance(raw, dict):
                continue
            cite, date = _cite(raw.get("fact"), self.by_id), _text(raw.get("date"), 20)
            label = _text(raw.get("label"), MAX_TEXT["label"])
            if not cite or not label or not _year_in(date, cite["text"]):
                continue
            events.append({"date": date, "label": label, "detail": _text(raw.get("detail"), MAX_TEXT["detail"]), "cite": cite})
        if len(events) < 2:
            return None, "fewer than two dated events found in their facts"
        events.sort(key=lambda e: _when(e["date"]))
        return {"events": events}, None

    def comparison(self, b):
        columns = [_text(c, MAX_TEXT["label"]) for c in (b.get("columns") or [])[: MAX_COLUMNS + 1]]
        columns = [c for c in columns if c]
        raws = []
        for raw in (b.get("rows") or [])[: MAX_ITEMS["comparison"]]:
            if not isinstance(raw, dict):
                continue
            cells = [_text(c, MAX_TEXT["cell"]) for c in (raw.get("cells") or [])]
            fact = raw.get("fact")
            # A fact's id written as a cell, not as the row's fact.
            ids = [c for c in cells if re.fullmatch(r"F\d+", c)]
            if ids:
                cells = [c for c in cells if c not in ids]
                fact = fact or ids[0]
            raws.append({"label": _text(raw.get("label"), MAX_TEXT["label"]), "cells": cells, "fact": fact})
        # A first column that names what the rows are ("Measure"), its cells
        # given as the rows' labels: a header for the labels, not a column.
        if len(columns) > 1 and raws and all(len(r["cells"]) == len(columns) - 1 for r in raws):
            columns = columns[1:]
        columns = columns[:MAX_COLUMNS]
        rows = []
        for raw in raws:
            label, cells = raw["label"], raw["cells"]
            if not label or len(cells) != len(columns):
                continue
            cite = _cite(raw["fact"], self.by_id)
            if not (cite and self._holds_row(cite["text"], label, cells)):
                # The numbers are in another passage than the one named: that
                # passage, when one holds each of them as written.
                cite = self._row_passage(label, cells)
            if not cite:
                continue
            rows.append({"label": label, "cells": cells, "cite": cite})
        if not columns or len(rows) < 2:
            return None, "fewer than two rows with facts"
        # A column that says again, row by row, what a later one says: the
        # later is kept (its name tends to be the one that says what it is).
        keep = [i for i in range(len(columns))
                if not any(all(r["cells"][i] == r["cells"][j] for r in rows) for j in range(i + 1, len(columns)))]
        if len(keep) < len(columns):
            columns = [columns[i] for i in keep]
            for r in rows:
                r["cells"] = [r["cells"][i] for i in keep]
        return {"columns": columns, "rows": rows}, None

    def diagram(self, b):
        kind = b.get("kind") if b.get("kind") in DIAGRAMS else "flow"
        nodes, ids = [], set()
        for raw in (b.get("nodes") or [])[:MAX_NODES]:
            if not isinstance(raw, dict):
                continue
            node_id, label = str(raw.get("id") or "").strip().lower(), _text(raw.get("label"), MAX_TEXT["label"])
            if _NODE_ID.match(node_id) and label and node_id not in ids:
                ids.add(node_id)
                nodes.append({"id": node_id, "label": label})
        edges, seen = [], set()
        for raw in b.get("edges") or []:
            if not isinstance(raw, dict):
                continue
            a, z = str(raw.get("from") or "").strip().lower(), str(raw.get("to") or "").strip().lower()
            if a in ids and z in ids and a != z and (a, z) not in seen:
                seen.add((a, z))
                edges.append({"from": a, "to": z, "label": _text(raw.get("label"), 40)})
        cites = [c for c in (_cite(f, self.by_id) for f in (b.get("facts") or [])[:6]) if c]
        if len(nodes) < 3 or not edges:
            return None, "fewer than three linked steps"
        if not cites:
            return None, "no fact behind it"
        # Most steps must be named in the facts it cites.
        passages = " ".join(c["text"] for c in cites)
        if sum(_grounded(n["label"], passages) for n in nodes) < 0.6 * len(nodes):
            return None, "its steps are not in its facts"
        return {"kind": kind, "nodes": nodes, "edges": edges, "cites": cites}, None

    def glossary(self, b):
        terms = []
        for raw in (b.get("terms") or [])[: MAX_ITEMS["glossary"]]:
            if not isinstance(raw, dict):
                continue
            cite, term = _cite(raw.get("fact"), self.by_id), _text(raw.get("term"), MAX_TEXT["label"])
            definition = _text(raw.get("definition"), MAX_TEXT["definition"])
            # The term must be the one the fact talks about.
            if not cite or not term or not definition or _normal(term) not in _normal(cite["text"]):
                continue
            terms.append({"term": term, "definition": definition, "cite": cite})
        if len(terms) < 2:
            return None, "fewer than two terms found in their facts"
        return {"terms": terms}, None


def _shows(block):
    """What a block puts in front of the reader, as (fact, value) pairs: two
    blocks that show the same thing are one too many."""
    out = set()
    for it in block.get("items", []):
        out.add((it["cite"]["fact"], it["value"]))
    for s in block.get("series", []):
        for p in s["points"]:
            out.add((p["cite"]["fact"], p["y"]))
    for r in block.get("rows", []):
        # By their numbers when they have some: "1:2" and "1 imported to 2
        # made" are one row said twice, and a key figure's value is the same
        # value in a row.
        numbers = [n for c in r["cells"] for n in numbers_in(c)]
        out |= {(r["cite"]["fact"], n) for n in numbers} if numbers else {(r["cite"]["fact"], tuple(r["cells"]))}
    for e in block.get("events", []):
        out.add((e["cite"]["fact"], e["date"]))
    for t in block.get("terms", []):
        out.add(("term", t["term"].casefold()))
    return out


def check(raw_blocks, report, facts_, start=0, room=MAX_BLOCKS, earlier=()):
    """Keep what the facts bear out. Returns (blocks, dropped): every block
    carries its facts' passages; `dropped` says what went and why. `start`
    numbers the blocks on from an earlier answer, `room` is what is left of
    the cap, `earlier` the blocks that answer kept (none is shown twice)."""
    checker = _Checker(report, facts_)
    blocks, dropped = [], []
    shown = set().union(*(_shows(b) for b in earlier)) if earlier else set()
    for i, raw in enumerate(raw_blocks if isinstance(raw_blocks, list) else [], start):
        if not isinstance(raw, dict):
            continue
        kind = raw.get("type")
        name = f"v{i + 1}"
        if kind not in TYPES:
            dropped.append({"id": name, "type": str(kind)[:20], "reason": "unknown type"})
            continue
        if kind in NUMERIC and not checker.numeric:
            dropped.append({"id": name, "type": kind, "reason": "the report records no evidence to check numbers against"})
            continue
        if len(blocks) >= room:
            dropped.append({"id": name, "type": kind, "reason": f"more than {MAX_BLOCKS} blocks"})
            continue
        body, reason = getattr(checker, kind)(raw)
        if body is None:
            dropped.append({"id": name, "type": kind, "reason": reason})
            continue
        if kind == "stat_cards":
            # A figure already on show is not shown again; the rest may be.
            body["items"] = [it for it in body["items"] if (it["cite"]["fact"], it["value"]) not in shown]
            if not body["items"]:
                dropped.append({"id": name, "type": kind, "reason": "shows only what an earlier block shows"})
                continue
        new = _shows(body)
        if new and len(new & shown) * 2 >= len(new):
            dropped.append({"id": name, "type": kind, "reason": "shows what an earlier block shows"})
            continue
        shown |= new
        cites = body.get("cites") or [
            x["cite"] for key in ("items", "events", "rows", "terms") for x in body.get(key, [])
        ] + [p["cite"] for s in body.get("series", []) for p in s["points"]]
        blocks.append({
            "id": name,
            "type": kind,
            "anchor": checker.anchor(raw.get("anchor")),
            "title": _text(raw.get("title"), MAX_TEXT["title"]),
            "note": _text(raw.get("note"), MAX_TEXT["note"]),
            **body,
            "sources": sorted({c["source"] for c in cites}),
        })
    return blocks, dropped


# --- asking the model --------------------------------------------------------

TIMEOUT = 150
MAX_OUTPUT_TOKENS = 6000

PROMPT = """You are adding a few figures to a finished research report, to help a reader \
see what the text says. You may only use the numbered FACTS below; each belongs to a source.

Report title: {title}
Report language: {language}. Write every title, label and definition in {language}.

Sections (use an id as "anchor" to place a figure after that section, or "lead"):
{outline}

Choose between 0 and {max_blocks} blocks, only where a figure genuinely helps; fewer good \
blocks are better than many weak ones. Look first for numbers a reader would want side by side: \
before and after (a tax, a price, a rate, a share before and after a measure), the same measure \
across years, places, groups or products. Two or more of those make a chart (bar across groups, \
line across years) or a comparison whose cells are the numbers with their units. Types:
{types}

Rules:
- Every value, event, row and term names the one fact it comes from, as "fact": "F12".
- A number must be written in its fact exactly (same value; you may drop thousands \
separators). Never compute, convert, sum or estimate. A date's year must be in its fact.
- A glossary term must appear word for word in its fact.
- Do not put numbers from different units, years or definitions in one chart.
- Titles and labels say exactly what the facts measure: which crop, place, group or study, \
and when. Do not widen a finding about one case into a general claim.
- A diagram is only for steps or parts the facts describe as a process or a structure. \
Values measured under different conditions belong in a comparison, not a diagram.
- A date at the very start of a fact ("8 ธ.ค. 2563 ...", "Mar 3, 2024 ...") is when the page \
was published, not an event: do not use it as one.
- A label says what its fact says the number is: an increase is not a total, "about" stays \
"about", and a figure the fact leaves unclear is left out.
- A comparison's cells hold what differs between its rows; do not repeat the row's label in a cell.
- Plain text only: no markdown, no HTML, no links.

FACTS:
{facts}

Answer with one JSON object and nothing else:
{{"blocks": [ ... ]}}"""

TYPE_HELP = {
    "stat_cards": '{"type":"stat_cards","anchor":"s1","title":"...","items":[{"label":"...","value":42.5,"unit":"%","as_of":"2024","fact":"F3"}]}  (1-6 key figures)',
    "chart": '{"type":"chart","chart":"bar|line|pie","anchor":"s2","title":"...","unit":"...","x_label":"...","y_label":"...","series":[{"name":"...","points":[{"x":"2023","y":120,"fact":"F5"}]}]}  (line only over years; pie only for parts of one whole; 2-12 points)',
    "timeline": '{"type":"timeline","anchor":"s1","title":"...","events":[{"date":"2019","label":"...","detail":"...","fact":"F7"}]}  (2-12 dated events)',
    "comparison": '{"type":"comparison","anchor":"s3","title":"...","columns":["...","..."],"rows":[{"label":"...","cells":["...","..."],"fact":"F9"}]}  (2-8 rows, 1-4 columns, cells as short text)',
    "diagram": '{"type":"diagram","kind":"flow|cycle|hierarchy","anchor":"s2","title":"...","nodes":[{"id":"a","label":"..."}],"edges":[{"from":"a","to":"b","label":"..."}],"facts":["F4","F8"]}  (3-10 steps; ids are short lowercase words)',
    "glossary": '{"type":"glossary","anchor":"lead","title":"...","terms":[{"term":"...","definition":"...","fact":"F2"}]}  (2-8 terms the report uses)',
}

LANGUAGE = {"th": "Thai", "en": "English"}


def prompt(report, facts_):
    """What the model is asked. Numeric blocks are not offered for a report
    without Evidence: they would be dropped anyway."""
    numeric = has_evidence(report)
    outline = "\n".join(
        f"- {s['id']}: {s['heading']}" for s in report_mod.walk(report["sections"])
    ) or "- (none)"
    types = "\n".join(f"- {TYPE_HELP[t]}" for t in TYPES if numeric or t not in NUMERIC)
    lines = "\n".join(f"{f['id']} [source {f['source']}]: {f['text']}" for f in facts_)
    return PROMPT.format(
        title=report["title"],
        language=LANGUAGE.get(report["language"], "English"),
        outline=outline,
        max_blocks=MAX_BLOCKS,
        types=types,
        facts=lines or "(none)",
    )


# Answers asked for at once; their checked blocks are pooled.
DRAFTS = 2
# Fewer kept than this, with some dropped: ask once more, saying why.
SECOND_CHANCE_BELOW = 3
SECOND_CHANCE = """These blocks were rejected by the fact check:
{why}

Give up to {room} other blocks that keep to the rules exactly — numbers and years written in \
their own fact, a line chart only over years each found in its point's fact. Fewer is fine; \
none is fine. Answer with only the JSON object {{"blocks": [...]}}."""


# The figures with numbers get a second reading, by the model, against their
# facts: what the number checks cannot see (what a number counts) it can.
REVIEWED = ("stat_cards", "chart", "comparison")
REVIEW = """You are checking figures drawn for a research report against the passages \
they cite. The numbers were already found in their passages; your task is what they mean.

Reject an entry when:
- its label or title says something its passage does not (an increase called a total, \
a forecast called a result, one province called the whole country, a cumulative count \
called one year's);
- the points or rows of one chart or table measure different things (a yearly figure beside \
a running total or a forecast, different units or definitions);
- the passage is too cut off to tell what the number is.
Keep everything else; do not reject for style.

ENTRIES:
{entries}

Answer with one JSON object and nothing else:
{{"verdicts": [{{"id": "v1", "ok": true}}, {{"id": "v2", "ok": false, "why": "a few words"}}]}}"""


def _passage(cite):
    return (cite.get("text") or "")[:320]


def review_entries(blocks):
    """What the reviewer reads: each numeric figure, with the passages behind it."""
    out = []
    for b in blocks:
        if b["type"] == "stat_cards":
            for i, it in enumerate(b["items"], 1):
                when = f" (as of {it['as_of']})" if it.get("as_of") else ""
                out.append(f'[{b["id"]}.{i}] key figure "{it["label"]}": {it["value"]:g} {it["unit"]}{when}\n'
                           f'  passage: "{_passage(it["cite"])}"')
        elif b["type"] == "chart":
            lines = [f'[{b["id"]}] {b["chart"]} chart "{b["title"]}"' + (f' (unit: {b["unit"]})' if b.get("unit") else "")]
            for sr in b["series"]:
                for pt in sr["points"]:
                    lines.append(f'  {sr["name"] or "value"} at {pt["x"]}: {pt["y"]:g}  passage: "{_passage(pt["cite"])}"')
            out.append("\n".join(lines))
        elif b["type"] == "comparison":
            lines = [f'[{b["id"]}] table "{b["title"]}", columns: {" | ".join(b["columns"])}']
            for r in b["rows"]:
                lines.append(f'  row "{r["label"]}": {" | ".join(r["cells"])}  passage: "{_passage(r["cite"])}"')
            out.append("\n".join(lines))
    return "\n\n".join(out)


def verdicts(text):
    """The reviewer's rejections, by id, with why; nothing when unreadable."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    match = re.search(r"\{.*\}", text, re.S)
    try:
        found = json.loads(match.group(0)) if match else {}
    except ValueError:
        return {}
    out = {}
    for v in (found.get("verdicts") if isinstance(found, dict) else None) or []:
        if isinstance(v, dict) and v.get("ok") is False and isinstance(v.get("id"), str):
            out[v["id"].strip("[] ")] = _text(v.get("why"), 120) or "rejected"
    return out


def apply_review(blocks, rejected):
    """Leave out what the reviewer rejected: a key figure, or a whole figure."""
    kept, dropped = [], []
    for b in blocks:
        if b["id"] in rejected:
            dropped.append({"id": b["id"], "type": b["type"], "reason": f"review: {rejected[b['id']]}"})
            continue
        if b["type"] == "stat_cards":
            items = [it for i, it in enumerate(b["items"], 1) if f'{b["id"]}.{i}' not in rejected]
            if not items:
                dropped.append({"id": b["id"], "type": b["type"], "reason": "review: every figure rejected"})
                continue
            if len(items) < len(b["items"]):
                b = {**b, "items": items, "sources": sorted({it["cite"]["source"] for it in items})}
        kept.append(b)
    return kept, dropped


class GenerateError(RuntimeError):
    """The model could not be asked, or said nothing usable."""


def parse(text):
    """The blocks in a reply: the JSON object (or bare list) in it, if any."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.S)
        if not match:
            continue
        try:
            found = json.loads(match.group(0))
        except ValueError:
            continue
        if isinstance(found, dict) and isinstance(found.get("blocks"), list):
            return found["blocks"]
        if isinstance(found, list):
            return found
    return None


def _ask(model, api_key, api_base, messages):
    import litellm

    from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs

    kwargs = {"api_key": api_key, "timeout": TIMEOUT, "num_retries": 1}
    if api_base:
        kwargs["api_base"] = api_base
    kwargs.update(reasoning_kwargs(model.reasoning, model.provider))
    kwargs.update(routing_kwargs(model.provider, kwargs))
    name = LLM_PROVIDERS[model.provider]["prefix"] + model.model
    response = litellm.completion(
        model=name,
        messages=messages,
        max_tokens=MAX_OUTPUT_TOKENS,
        response_format={"type": "json_object"},
        drop_params=True,
        **kwargs,
    )
    usage = getattr(response, "usage", None)
    used = (int(getattr(usage, "prompt_tokens", 0) or 0), int(getattr(usage, "completion_tokens", 0) or 0))
    return response.choices[0].message.content or "", name, used


def generate(model, api_key, api_base, report):
    """Ask for DRAFTS answers at once (each repaired once if its JSON is
    unreadable), keep what the facts bear out in each, the best first and
    nothing twice; give one second chance when too little survives.

    Returns (visuals, tokens) where tokens maps the model's name to
    [prompt_tokens, completion_tokens], as litstorm.cost counts them.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    if not api_key:
        raise GenerateError("no API key stored for this model's provider")
    facts_ = facts(report)
    messages = [{"role": "user", "content": prompt(report, facts_)}]
    tokens, counting = {}, threading.Lock()

    def ask(msgs):
        try:
            text, name, (p, c) = _ask(model, api_key, api_base, msgs)
        except Exception as error:  # noqa: BLE001 - the report still reads without figures
            raise GenerateError(f"{type(error).__name__}: {error}"[:300]) from error
        with counting:
            t = tokens.setdefault(name, [0, 0])
            t[0] += p
            t[1] += c
        return text

    def draft(_):
        try:
            reply = ask(messages)
            raw = parse(reply)
            if raw is None:
                # One repair, on the reply alone: cheaper than asking again.
                reply = ask(messages + [
                    {"role": "assistant", "content": reply[:8000]},
                    {"role": "user", "content": 'That was not valid JSON. Answer again with only the JSON object {"blocks": [...]}.'},
                ])
                raw = parse(reply)
            return reply, raw, None
        except GenerateError as error:
            return "", None, error

    # A small model's picks vary from one answer to the next: two answers,
    # checked alike, give a report the figures either would have found.
    with ThreadPoolExecutor(DRAFTS) as pool:
        drafts = list(pool.map(draft, range(DRAFTS)))
    usable = [(reply, raw) for reply, raw, _ in drafts if raw is not None]
    if not usable:
        failed = next((e for _, _, e in drafts if e is not None), None)
        raise failed or GenerateError("the model gave no readable blocks")
    usable.sort(key=lambda d: -len(check(d[1], report, facts_)[0]))
    blocks, dropped, asked = [], [], 0
    for _, raw in usable:
        more, more_dropped = check(raw, report, facts_, start=asked, room=MAX_BLOCKS - len(blocks), earlier=blocks)
        blocks += more
        dropped += more_dropped
        asked += len(raw)
    reply = usable[0][0]
    if dropped and len(blocks) < SECOND_CHANCE_BELOW:
        # One second chance, told exactly why: a model that misread the
        # rules once usually keeps to them when shown where it slipped.
        why = "\n".join(f"- {d['type']}: {d['reason']}" for d in dropped)
        again = parse(ask(messages + [
            {"role": "assistant", "content": reply[:8000]},
            {"role": "user", "content": SECOND_CHANCE.format(why=why, room=MAX_BLOCKS - len(blocks))},
        ]))
        if again:
            more, more_dropped = check(again, report, facts_, start=asked, room=MAX_BLOCKS - len(blocks), earlier=blocks)
            blocks += more
            dropped += more_dropped
    if any(b["type"] in REVIEWED for b in blocks):
        # Read again for what the numbers mean; a reviewer that fails or
        # answers nonsense leaves the checked blocks as they are.
        try:
            rejected = verdicts(ask([{"role": "user", "content": REVIEW.format(entries=review_entries(blocks))}]))
        except GenerateError:
            rejected = {}
        blocks, more_dropped = apply_review(blocks, rejected)
        dropped += more_dropped
    from datetime import datetime, timezone

    return {
        "schema": SCHEMA,
        "report": report_hash(report),
        "model": model.label,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "blocks": blocks,
        "dropped": dropped,
        "hidden": [],
        "facts": len(facts_),
    }, tokens


# --- the file ----------------------------------------------------------------


def report_hash(report):
    """Which report the visuals were made from: a changed report is a new one."""
    text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def path_for(report_path):
    return os.path.join(os.path.dirname(report_path), "visuals.json")


def write(visuals, path):
    """Write so that a reader never sees half a file."""
    if visuals.get("schema") != SCHEMA or not isinstance(visuals.get("blocks"), list):
        raise VisualsError("not a schema-1 visuals file")
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".visuals-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(visuals, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load(path, report=None):
    """The visuals file, or None when there is none — or when it was made
    from a different report than `report`."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        visuals = json.load(f)
    if visuals.get("schema") != SCHEMA:
        return None
    if report is not None and visuals.get("report") != report_hash(report):
        return None
    return visuals


def set_hidden(visuals, hidden):
    """The owner's choice of blocks to leave out; unknown ids are ignored."""
    known = {b["id"] for b in visuals["blocks"]}
    visuals["hidden"] = sorted({h for h in hidden if h in known})
    return visuals
