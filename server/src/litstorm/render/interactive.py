"""The interactive report: the HTML export's page, with figures.

Figures come from two places:

- visual blocks the model drew and litstorm.visuals checked (key figures,
  charts, timelines, comparisons, diagrams, a glossary), placed after the
  section each belongs to; hidden ones left out;
- figures that need no model, made from report.json itself: the report's
  outline, the Sources cited most, and every Source in a sortable table.

Charts are drawn once, here, by ECharts in the Chromium that prints PDFs,
with the network refused, and kept as SVG in the page: the file opens
offline, prints sharp and reads with scripts off. A small script of our own
adds tabs (figure / its data), sorting, previews of citations, a light/dark
switch, the contents following the reader, and printing. With `full`, the
ECharts library travels in the file too and the charts come alive (values
on hover), at about 1.1 MB.

The page carries a Content-Security-Policy that runs our scripts and
nothing else and allows no requests at all; served for the web app it is
also sandboxed (api/research.py). The model never writes markup: every
string it gave is escaped here (docs/research/2026-10-01-interactive-html-
report.md §6).
"""

import base64
import functools
import glob
import hashlib
import html
import json
import os
import re

from litstorm import report as report_mod
from litstorm import visuals as visuals_mod
from litstorm.render import html as page_mod

@functools.lru_cache(maxsize=1)
def render_code():
    """What draws the page, as a digest: the code here and the faces and
    library it embeds. A page kept on disk is drawn again whenever it
    changes, with no number to remember to bump."""
    digest = hashlib.sha256()
    here = os.path.dirname(os.path.abspath(__file__))
    for name in sorted(os.listdir(here)):
        if name.endswith(".py"):
            digest.update(name.encode())
            with open(os.path.join(here, name), "rb") as f:
                digest.update(f.read())
    for folder in ("fonts", "vendor"):
        for root, _, files in sorted(os.walk(os.path.join(here, folder))):
            for name in sorted(files):
                digest.update(f"{name}:{os.path.getsize(os.path.join(root, name))}".encode())
    return digest.hexdigest()[:16]

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
ECHARTS = os.path.join(_VENDOR, "echarts-6.1.0.min.js")

LABELS = {
    "th": {
        "figure": "ภาพประกอบ",
        "data": "ข้อมูล",
        "from": "ที่มา",
        "outline": "โครงเรื่อง",
        "outline_lead": "หัวข้อของรายงานและความสัมพันธ์ระหว่างกัน",
        "most_cited": "แหล่งที่ถูกอ้างถึงบ่อยที่สุด",
        "times": "จำนวนครั้งที่อ้าง",
        "table": "ตารางแหล่งอ้างอิง",
        "site": "เว็บไซต์",
        "title": "ชื่อ",
        "cited": "อ้าง",
        "evidence": "หลักฐาน",
        "stat_cards": "ตัวเลขสำคัญ",
        "chart": "กราฟ",
        "timeline": "ลำดับเหตุการณ์",
        "comparison": "เปรียบเทียบ",
        "diagram": "แผนภาพ",
        "glossary": "อภิธานศัพท์",
        "links": "ความเชื่อมโยง",
        "cycle": "วนกลับสู่ขั้นแรก",
        "made_by": "ภาพประกอบสร้างโดย {model} จากข้อความหลักฐานของแหล่งอ้างอิง ทุกตัวเลขตรวจแล้วว่าตรงกับข้อความต้นทาง แตะเลขที่มาเพื่อดูข้อความนั้น",
        "made_by_report": "ภาพประกอบสร้างโดย {model} จากประโยคในรายงานที่อ้างแหล่งไว้ รายงานนี้ไม่มีข้อความหลักฐานจากต้นทาง จึงไม่มีกราฟตัวเลข",
        "from_report": "จากข้อความในรายงาน ไม่ใช่ข้อความต้นทาง",
        "theme": "สลับโหมดมืด/สว่าง",
        "print": "พิมพ์",
        "as_of": "ข้อมูลปี",
    },
    "en": {
        "figure": "Figure",
        "data": "Data",
        "from": "Source",
        "outline": "Outline",
        "outline_lead": "The report's sections and how they fit together",
        "most_cited": "Sources cited most",
        "times": "Times cited",
        "table": "Sources as a table",
        "site": "Site",
        "title": "Title",
        "cited": "Cited",
        "evidence": "Evidence",
        "stat_cards": "Key figures",
        "chart": "Chart",
        "timeline": "Timeline",
        "comparison": "Comparison",
        "diagram": "Diagram",
        "glossary": "Glossary",
        "links": "Links",
        "cycle": "back to the first step",
        "made_by": "Figures drawn by {model} from the Sources' evidence; every number was checked against the passage it came from. Tap a source number to read it.",
        "made_by_report": "Figures drawn by {model} from the report's own cited sentences. This report records no evidence from its sources, so it has no number charts.",
        "from_report": "From the report's text, not the source's",
        "theme": "Switch light/dark",
        "print": "Print",
        "as_of": "as of",
    },
}

# Colours that read on white and on near-black alike: the SVG is drawn once.
PALETTE = ["#3b6fd8", "#1fa39a", "#e39b2d", "#d65a7e"]


# --- small pieces --------------------------------------------------------------


def _e(text):
    return html.escape(str(text or ""))


def _num(value, language):
    if value is None:
        return ""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def _pill(cite, labels):
    tip = cite["text"] if cite.get("origin") != "report" else f"{labels['from_report']}: {cite['text']}"
    return f'<a class="cite" href="#src-{cite["source"]}" data-tip="{_e(tip)}">{cite["source"]}</a>'


def _from(ids, labels, note=""):
    pills = "".join(f'<a class="cite" href="#src-{n}">{n}</a>' for n in ids)
    extra = f' <span class="fnote">· {_e(note)}</span>' if note else ""
    return f'<p class="from">{labels["from"]} {pills}{extra}</p>'


def _figure(fid, kind, title, labels, view, data="", foot=""):
    """A figure: its kind and title, what it shows, and — in a second tab — its
    data as a table, which is also what a screen reader and a printer get."""
    tabs = ""
    if data:
        tabs = (
            f'<div class="tabs" role="tablist">'
            f'<button type="button" role="tab" aria-selected="true" data-tab="view">{labels["figure"]}</button>'
            f'<button type="button" role="tab" aria-selected="false" data-tab="data">{labels["data"]}</button></div>'
        )
    data_panel = f'<div class="panel" data-panel="data">{data}</div>' if data else ""
    return (
        f'<figure class="ix" id="{fid}" data-kind="{kind}">'
        f'<figcaption><span class="kind">{_e(labels.get(kind, kind))}</span>'
        f'<span class="t">{_e(title)}</span></figcaption>{tabs}'
        f'<div class="panel" data-panel="view">{view}</div>{data_panel}{foot}</figure>'
    )


def _table(head, rows, sortable=True):
    ths = "".join(
        f'<th scope="col"><button type="button" data-sort="{i}">{_e(h)}</button></th>' if sortable and h else f"<th>{_e(h)}</th>"
        for i, h in enumerate(head)
    )
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="tbl"><table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table></div>'


# --- the model's blocks --------------------------------------------------------


def _stat_cards(b, labels, language):
    cards = "".join(
        f'<div class="stat"><div class="v">{_num(i["value"], language)}'
        f'<span class="u">{_e(i["unit"])}</span></div>'
        f'<div class="l">{_e(i["label"])}</div>'
        f'<div class="s">{(_e(labels["as_of"]) + " " + _e(i["as_of"]) + " · ") if i["as_of"] else ""}{_pill(i["cite"], labels)}</div></div>'
        for i in b["items"]
    )
    return _figure(b["id"], "stat_cards", b["title"] or labels["stat_cards"], labels, f'<div class="stats">{cards}</div>',
                   foot=_from(b["sources"], labels, b.get("note")))


def chart_spec(b, language):
    """A chart block as the small spec our chart script turns into ECharts
    options (never functions or markup: data only)."""
    categories = []
    for s in b["series"]:
        for p in s["points"]:
            if p["x"] not in categories:
                categories.append(p["x"])
    series = []
    for s in b["series"]:
        by_x = {p["x"]: p["y"] for p in s["points"]}
        series.append({"name": s["name"], "values": [by_x.get(x) for x in categories]})
    return {"kind": b["chart"], "categories": categories, "series": series, "unit": b.get("unit") or "",
            "x_label": b.get("x_label") or "", "y_label": b.get("y_label") or "", "locale": language}


def _chart(b, labels, language, svg):
    head = [b.get("x_label") or "", *(s["name"] or b.get("y_label") or labels["data"] for s in b["series"]), labels["from"]]
    rows = []
    spec = chart_spec(b, language)
    for i, x in enumerate(spec["categories"]):
        cites = [p["cite"] for s in b["series"] for p in s["points"] if p["x"] == x]
        values = [_num(s["values"][i], language) if s["values"][i] is not None else "–" for s in spec["series"]]
        rows.append([_e(x), *values, "".join(_pill(c, labels) for c in cites)])
    unit = f' <span class="unit">({_e(b["unit"])})</span>' if b.get("unit") else ""
    view = f'<div class="chart" data-chart="{b["id"]}">{svg}</div>'
    return _figure(b["id"], "chart", (b["title"] or labels["chart"]), labels, view, _table(head, rows),
                   foot=_from(b["sources"], labels, b.get("note")).replace("</p>", f"{unit}</p>", 1))


def _timeline(b, labels, language):
    items = "".join(
        f'<li><span class="when">{_e(e["date"])}</span><div class="what"><strong>{_e(e["label"])}</strong>'
        f'{("<p>" + _e(e["detail"]) + "</p>") if e["detail"] else ""}{_pill(e["cite"], labels)}</div></li>'
        for e in b["events"]
    )
    return _figure(b["id"], "timeline", b["title"] or labels["timeline"], labels, f'<ol class="timeline">{items}</ol>',
                   foot=_from(b["sources"], labels, b.get("note")))


_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_RATIO = re.compile(rf"^\s*({_NUMBER})\s*[:：]\s*({_NUMBER})\s*$")
_AMOUNT = re.compile(rf"^\s*([^\d\s]{{0,3}})\s*({_NUMBER})\s*([^\d]{{0,12}}?)\s*$")


def _measure(cell):
    """A cell as (value, unit), or None when it is not one number: "23.9%",
    "1,600 บาท", and "1 : 3" (as 3 to every 1)."""
    m = _RATIO.match(cell or "")
    if m:
        a, b = (float(x.replace(",", "")) for x in m.groups())
        return (b / a, ":") if a else None
    m = _AMOUNT.match(cell or "")
    if not m:
        return None
    return float(m.group(2).replace(",", "")), (m.group(1) + "|" + m.group(3).strip())


def _comparison_columns(b):
    """The columns worth showing: not those that only say again what their
    row's label says ("2569" beside "ปี 2569")."""
    keep = []
    for i, _ in enumerate(b["columns"]):
        cells = [(r["cells"][i] if i < len(r["cells"]) else "").strip() for r in b["rows"]]
        if all(c and c in r["label"] for c, r in zip(cells, b["rows"])):
            continue
        keep.append(i)
    return keep


def comparison_spec(b, language):
    """A comparison whose columns are numbers in one unit, as a bar chart
    (None when it is not one: text stays a table). The bars carry the cells
    as written; the table stays a tab away."""
    if len(b["rows"]) == 1 and len(b["columns"]) >= 2:
        # One row compares its columns (before | after): its columns are the bars.
        row = b["rows"][0]
        b = {**b, "columns": [row["label"]],
             "rows": [{"label": c, "cells": [row["cells"][i] if i < len(row["cells"]) else ""]} for i, c in enumerate(b["columns"])]}
    if len(b["rows"]) < 2:
        return None
    series, unit = [], None
    for i in _comparison_columns(b):
        cells = [r["cells"][i] if i < len(r["cells"]) else "" for r in b["rows"]]
        measured = [_measure(c) for c in cells]
        if any(m is None for m in measured):
            continue
        units = {m[1] for m in measured}
        values = [m[0] for m in measured]
        # Years down a column are when, not how much.
        if units == {"|"} and all(v.is_integer() and 1800 <= v <= 2700 for v in values):
            continue
        if len(units) != 1 or (unit is not None and units != {unit}):
            continue
        unit = units.pop()
        series.append({"name": b["columns"][i], "values": values, "labels": [c.strip() for c in cells]})
    if not series:
        return None
    return {"kind": "bar", "categories": [r["label"] for r in b["rows"]], "series": series[:3],
            "unit": "", "x_label": "", "y_label": "", "locale": language, "as_written": True}


def _comparison(b, labels, language, svg=""):
    columns = _comparison_columns(b)
    rows = [[f"<strong>{_e(r['label'])}</strong>", *(_e(r["cells"][i] if i < len(r["cells"]) else "") for i in columns),
             _pill(r["cite"], labels)] for r in b["rows"]]
    table = _table(["", *(b["columns"][i] for i in columns), labels["from"]], rows)
    if svg:
        view, data = f'<div class="chart" data-chart="{b["id"]}">{svg}</div>', table
    else:
        view, data = table, ""
    return _figure(b["id"], "comparison", b["title"] or labels["comparison"], labels, view, data,
                   foot=_from(b["sources"], labels, b.get("note")))


def chart_specs(blocks, language):
    """Every block drawn as a chart, by id: the charts, and the comparisons
    that are numbers."""
    specs = {}
    for b in blocks:
        if b["type"] == "chart":
            specs[b["id"]] = chart_spec(b, language)
        elif b["type"] == "comparison":
            spec = comparison_spec(b, language)
            if spec:
                specs[b["id"]] = spec
    return specs


def _layers(nodes, edges):
    """Columns for a flow: each step one further than the furthest step that
    leads to it (edges that would loop back are left out of the reckoning)."""
    ids = [n["id"] for n in nodes]
    out = {i: [] for i in ids}
    for e in edges:
        out[e["from"]].append(e["to"])
    order, seen, onstack = [], set(), set()

    def visit(i):
        seen.add(i)
        onstack.add(i)
        for j in out[i]:
            if j not in seen:
                visit(j)
        onstack.discard(i)
        order.append(i)

    for i in ids:
        if i not in seen:
            visit(i)
    order.reverse()
    rank = {i: 0 for i in ids}
    position = {i: k for k, i in enumerate(order)}
    for i in order:
        for j in out[i]:
            if position[j] > position[i]:  # forward only: a loop back is not a step on
                rank[j] = max(rank[j], rank[i] + 1)
    columns = {}
    for i in ids:
        columns.setdefault(rank[i], []).append(i)
    return [columns[k] for k in sorted(columns)]


def _diagram(b, labels, language):
    label = {n["id"]: n["label"] for n in b["nodes"]}
    if b["kind"] == "hierarchy":
        children = {n["id"]: [] for n in b["nodes"]}
        has_parent = set()
        for e in b["edges"]:
            if e["to"] not in has_parent:
                children[e["from"]].append(e["to"])
                has_parent.add(e["to"])

        def branch(i, seen):
            if i in seen:
                return ""
            kids = "".join(branch(k, seen | {i}) for k in children[i])
            return f'<li><span class="node">{_e(label[i])}</span>{("<ul>" + kids + "</ul>") if kids else ""}</li>'

        roots = [n["id"] for n in b["nodes"] if n["id"] not in has_parent] or [b["nodes"][0]["id"]]
        view = '<ul class="tree">' + "".join(branch(r, set()) for r in roots) + "</ul>"
    else:
        cols = _layers(b["nodes"], b["edges"])
        parts = []
        for k, col in enumerate(cols):
            if k:
                parts.append('<span class="arrow" aria-hidden="true">→</span>')
            parts.append('<div class="col">' + "".join(f'<span class="node">{_e(label[i])}</span>' for i in col) + "</div>")
        if b["kind"] == "cycle":
            parts.append(f'<span class="arrow back" aria-hidden="true">↻</span><span class="loop">{_e(labels["cycle"])}</span>')
        view = f'<div class="flow">{"".join(parts)}</div>'
    rows = [[_e(label[e["from"]]), "→", _e(label[e["to"]]), _e(e["label"])] for e in b["edges"]]
    data = _table(["", "", "", ""], rows, sortable=False)
    foot = f'<p class="from">{labels["from"]} ' + "".join(_pill(c, labels) for c in b["cites"]) + "</p>"
    return _figure(b["id"], "diagram", b["title"] or labels["diagram"], labels, view, data, foot=foot)


def _glossary(b, labels, language):
    items = "".join(
        f'<div class="term"><dt>{_e(t["term"])}</dt><dd>{_e(t["definition"])} {_pill(t["cite"], labels)}</dd></div>'
        for t in b["terms"]
    )
    return _figure(b["id"], "glossary", b["title"] or labels["glossary"], labels, f'<dl class="glossary">{items}</dl>',
                   foot=_from(b["sources"], labels, b.get("note")))


_BLOCKS = {
    "stat_cards": _stat_cards,
    "timeline": _timeline,
    "comparison": _comparison,
    "diagram": _diagram,
    "glossary": _glossary,
}


# --- figures made from the report itself -----------------------------------------


def _short(text, limit):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def citation_counts(report):
    """How often each Source is cited across the report."""
    counts = {s["id"]: 0 for s in report["sources"]}
    for text in report_mod.all_text(report):
        for match in report_mod.CITATION.finditer(text or ""):
            n = int(match.group(1))
            if n in counts:
                counts[n] += 1
    return counts


def most_cited_spec(report, top=8):
    counts = citation_counts(report)
    ranked = sorted(report["sources"], key=lambda s: (-counts[s["id"]], s["id"]))[:top]
    return {
        "kind": "bar",
        "categories": [f"[{s['id']}] {_short(s['title'], 44)}" for s in ranked],
        "series": [{"name": "", "values": [counts[s["id"]] for s in ranked]}],
        "unit": "",
        "x_label": "",
        "y_label": "",
        "locale": report["language"],
    }, ranked, counts


def _outline(report, labels):
    sections = page_mod._numbered(report["sections"])

    def branch(items):
        out = []
        for s in items:
            link = f'<a href="#{s["id"]}"><span class="n">{s["n"]}</span>{_e(s["heading"])}</a>'
            if s["children"]:
                out.append(f'<li><details open><summary>{link}</summary><ul>{branch(s["children"])}</ul></details></li>')
            else:
                out.append(f"<li>{link}</li>")
        return "".join(out)

    view = f'<div class="mindmap"><span class="root">{_e(report["title"])}</span><ul>{branch(sections)}</ul></div>'
    return _figure("fig-outline", "outline", labels["outline_lead"], labels, view)


def _sources_extra(report, labels, svg):
    spec, ranked, counts = most_cited_spec(report)
    data = _table(
        [labels["title"], labels["site"], labels["times"]],
        [[f'<a href="#src-{s["id"]}">[{s["id"]}] {_e(s["title"])}</a>', _e(page_mod._host(s["url"])), str(counts[s["id"]])] for s in ranked],
    )
    chart = _figure("fig-most-cited", "chart", labels["most_cited"], labels,
                    f'<div class="chart" data-chart="most-cited">{svg}</div>', data)
    rows = [
        [str(s["id"]), f'<a href="#src-{s["id"]}">{_e(s["title"])}</a>', _e(page_mod._host(s["url"])),
         str(counts[s["id"]]), str(len(s["evidence"]))]
        for s in report["sources"]
    ]
    table = _table(["#", labels["title"], labels["site"], labels["cited"], labels["evidence"]], rows)
    return (
        f"{chart}<details class=\"ix-table\"><summary>{labels['table']}</summary>{table}</details>"
    )


# --- drawing charts ----------------------------------------------------------------

# Turns a spec (chart_spec, most_cited_spec) into ECharts options: Thai labels
# broken at word boundaries (ECharts would break them between letters and
# their vowels), numbers in the report's locale, one palette for both themes.
CHART_JS = r"""
(function () {
  var PALETTE = %PALETTE%;
  var INK = "#80868f", RULE = "rgba(128,128,128,0.22)";
  var FONT = '"LS Latin","LS Thai","IBM Plex Sans Thai","Noto Sans Thai",sans-serif';
  function wrap(text, max, locale) {
    text = String(text == null ? "" : text);
    if (text.length <= max) return text;
    var words = [];
    try {
      var seg = new Intl.Segmenter(locale, { granularity: "word" });
      for (var it = seg.segment(text)[Symbol.iterator](), s = it.next(); !s.done; s = it.next()) words.push(s.value.segment);
    } catch (e) { words = text.split(/(\s+)/); }
    var lines = [], line = "";
    words.forEach(function (w) {
      if (line && (line + w).trim().length > max) { lines.push(line.trim()); line = w.trimStart(); }
      else line += w;
    });
    if (line.trim()) lines.push(line.trim());
    return lines.slice(0, 3).join("\n");
  }
  function fmt(locale) {
    var f = new Intl.NumberFormat(locale === "th" ? "th-TH" : "en-GB", { maximumFractionDigits: 2 });
    return function (v) { return v == null ? "" : f.format(v); };
  }
  function compact(locale) {
    var f = new Intl.NumberFormat(locale === "th" ? "th-TH" : "en-GB", { notation: "compact", maximumFractionDigits: 1 });
    return function (v) { return f.format(v); };
  }
  window.lsOptions = function (spec, live) {
    var loc = spec.locale || "en", n = fmt(loc), text = { color: INK, fontFamily: FONT, fontSize: 12 };
    var many = spec.series.length > 1;
    var base = { animation: !!live, color: PALETTE, textStyle: text, tooltip: live ? { trigger: spec.kind === "pie" ? "item" : "axis", valueFormatter: n } : undefined,
                 legend: many ? { top: 0, textStyle: text, icon: "roundRect" } : undefined };
    if (spec.kind === "pie") {
      var s = spec.series[0];
      base.series = [{ type: "pie", radius: ["42%", "70%"], center: ["50%", "54%"], avoidLabelOverlap: true,
        itemStyle: { borderColor: "rgba(128,128,128,0.25)", borderWidth: 1 },
        label: { color: INK, fontFamily: FONT, formatter: function (p) { return wrap(p.name, 14, loc) + "\n" + n(p.value); } },
        data: spec.categories.map(function (c, i) { return { name: c, value: s.values[i] }; }) }];
      return base;
    }
    var cats = spec.categories.map(function (c) { return wrap(c, spec.kind === "bar" ? 24 : 10, loc); });
    var valueAxis = { type: "value", axisLabel: Object.assign({ formatter: compact(loc), show: !spec.as_written }, text), splitLine: { lineStyle: { color: RULE } },
                      name: spec.unit || "", nameTextStyle: text };
    var catAxis = { type: "category", data: cats, axisLabel: Object.assign({ interval: 0 }, text), axisLine: { lineStyle: { color: RULE } }, axisTick: { show: false } };
    base.grid = { left: 8, right: 56, top: many ? 34 : 16, bottom: 8, containLabel: true };
    // What the categories are ("Temperature (°C)"): over the bars' labels, or under a line's years.
    if (spec.x_label) {
      catAxis.name = spec.x_label;
      catAxis.nameTextStyle = Object.assign({}, text, { fontSize: 11, align: spec.kind === "bar" ? "left" : "center" });
      if (spec.kind === "bar") { catAxis.nameLocation = "start"; catAxis.nameGap = 10; base.grid.top += 20; }
      else { catAxis.nameLocation = "middle"; catAxis.nameGap = 30; base.grid.bottom += 24; }
    }
    if (spec.kind === "bar") {
      catAxis.inverse = true;
      base.yAxis = catAxis; base.xAxis = valueAxis;
      base.series = spec.series.map(function (s) {
        return { type: "bar", name: s.name, data: s.values, barMaxWidth: 22, itemStyle: { borderRadius: [0, 4, 4, 0] },
                 label: { show: true, position: "right", color: INK, fontFamily: FONT,
                          formatter: function (p) { return s.labels ? s.labels[p.dataIndex] : n(p.value); } } };
      });
    } else {
      base.xAxis = catAxis; base.yAxis = valueAxis;
      base.series = spec.series.map(function (s) {
        return { type: "line", name: s.name, data: s.values, symbolSize: 7, lineStyle: { width: 2.5 }, connectNulls: true,
                 label: { show: true, position: "top", color: INK, fontFamily: FONT, formatter: function (p) { return n(p.value); } } };
      });
    }
    return base;
  };
  window.lsHeight = function (spec) {
    if (spec.kind === "bar") {
      // Room for the longest label's lines (wrap() breaks them at 24, up to 3).
      var lines = Math.min(3, Math.max.apply(null, spec.categories.map(function (c) { return Math.ceil(String(c).length / 24) || 1; })));
      var row = (spec.series.length > 1 ? 44 : 34) + (lines - 1) * 15;
      return Math.max(140, 40 + spec.categories.length * row + (spec.series.length > 1 ? 30 : 0) + (spec.x_label ? 20 : 0));
    }
    return spec.x_label ? 324 : 300;
  };
})();
""".replace("%PALETTE%", json.dumps(PALETTE))

_PRERENDER = r"""
async (specs) => {
  await Promise.all([document.fonts.load('13px "LS Thai"', "ทดสอบ"), document.fonts.load('13px "LS Latin"', "Aa1")]);
  return specs.map((spec) => {
    const w = 680, h = window.lsHeight(spec);
    const el = document.createElement("div");
    el.style.width = w + "px"; el.style.height = h + "px";
    document.body.appendChild(el);
    const chart = echarts.init(el, null, { renderer: "svg", width: w, height: h });
    chart.setOption(window.lsOptions(spec, false));
    const svg = el.querySelector("svg");
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.removeAttribute("width"); svg.removeAttribute("height");
    svg.setAttribute("role", "img");
    svg.removeAttribute("style");
    const out = svg.outerHTML;
    chart.dispose(); el.remove();
    return out;
  });
}
"""


def prerender(specs):
    """Each spec as SVG, drawn by ECharts in Chromium with the network refused
    (the PDF's browser; LITSTORM_PDF_BROWSER_CHANNEL picks another)."""
    if not specs:
        return []
    from playwright.sync_api import sync_playwright

    with open(ECHARTS, encoding="utf-8") as f:
        library = f.read()
    shell = (
        f"<!doctype html><html><head><meta charset='utf-8'><style>{page_mod._font_faces()}</style></head>"
        f"<body></body></html>"
    )
    channel = os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        try:
            page = browser.new_page()
            page.route("**/*", lambda route: route.abort())
            page.set_content(shell, wait_until="load")
            page.add_script_tag(content=library)
            page.add_script_tag(content=CHART_JS)
            return page.evaluate(_PRERENDER, specs)
        finally:
            browser.close()


# --- the page ----------------------------------------------------------------------

CSS = """
.tool { display: none; margin-left: auto; gap: .25rem; }
.js .tool { display: inline-flex; }
.tool button { font: inherit; font-size: .75rem; color: var(--muted); background: none; border: 1px solid var(--line);
  border-radius: 999px; padding: .1rem .65rem; cursor: pointer; transition: color .15s, border-color .15s; }
.tool button:hover { color: var(--brand); border-color: var(--brand); }
.ix-note { margin: 1.5rem 0 0; font-size: .78rem; color: var(--muted); display: flex; gap: .5rem; align-items: baseline; }
.ix-note::before { content: "◆"; color: var(--brand); font-size: .6rem; }

figure.ix { margin: 2rem 0; padding: 1.1rem 1.2rem 1rem; border: 1px solid var(--line); border-radius: 1rem;
  background: var(--card); box-shadow: 0 1px 2px oklch(0 0 0 / .04); break-inside: avoid; }
figure.ix figcaption { display: flex; flex-wrap: wrap; align-items: baseline; gap: .15rem .6rem; margin-bottom: .8rem; }
figure.ix .kind { font-size: .68rem; font-weight: 500; letter-spacing: .04em; text-transform: uppercase; color: var(--brand); }
figure.ix figcaption .t { font-weight: 600; font-size: 1rem; line-height: 1.45; color: var(--ink); }
.tabs { display: none; gap: .25rem; margin: -.2rem 0 .8rem; }
.js .tabs { display: inline-flex; background: var(--soft); border-radius: .6rem; padding: .2rem; }
.tabs button { font: inherit; font-size: .75rem; border: 0; background: none; color: var(--muted); padding: .2rem .7rem;
  border-radius: .45rem; cursor: pointer; transition: background-color .2s, color .2s; }
.tabs button[aria-selected="true"] { background: var(--card); color: var(--ink); box-shadow: 0 1px 2px oklch(0 0 0 / .08); }
.js .panel[hidden] { display: none; }
.panel { animation: ls-in .25s ease-out; }
@keyframes ls-in { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: none; } }
.from { margin: .8rem 0 0 !important; font-size: .75rem !important; color: var(--muted) !important; line-height: 1.6; }
.fnote, .unit { color: var(--muted); }
.chart svg { display: block; width: 100%; height: auto; }

.stats { display: grid; gap: .6rem; grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr)); }
.stat { padding: .8rem .9rem; border-radius: .8rem; background: var(--soft); }
.stat .v { font-size: 1.7rem; font-weight: 600; line-height: 1.2; letter-spacing: -.01em; color: var(--ink); font-variant-numeric: tabular-nums; }
.stat .u { font-size: .8rem; font-weight: 500; color: var(--muted); margin-left: .3rem; }
.stat .l { margin-top: .3rem; font-size: .82rem; line-height: 1.45; color: var(--body); }
.stat .s { margin-top: .35rem; font-size: .7rem; color: var(--muted); }

ol.timeline { list-style: none; margin: 0; padding: 0 0 0 .4rem; position: relative; }
ol.timeline::before { content: ""; position: absolute; left: .4rem; top: .5rem; bottom: .5rem; width: 2px; background: var(--line); }
ol.timeline li { position: relative; display: grid; grid-template-columns: 5.2rem 1fr; gap: .8rem; padding: .35rem 0 .35rem 1.2rem; }
ol.timeline li::before { content: ""; position: absolute; left: calc(-.05rem); top: .85rem; width: .6rem; height: .6rem;
  border-radius: 999px; background: var(--brand); box-shadow: 0 0 0 3px var(--card); }
.timeline .when { font-size: .8rem; font-weight: 600; color: var(--brand); font-variant-numeric: tabular-nums; padding-top: .15rem; }
.timeline .what { font-size: .9rem; line-height: 1.6; }
.timeline .what p { margin: .15rem 0 0 !important; font-size: .82rem !important; color: var(--muted) !important; }

.tbl { overflow-x: auto; }
.prose .tbl table, .tbl table { display: table; width: 100%; margin: 0; border-collapse: collapse; font-size: .85rem; line-height: 1.5; }
.prose .tbl th, .prose .tbl td, .tbl th, .tbl td { padding: .5rem .6rem; border: 0; border-bottom: 1px solid var(--line);
  background: none; text-align: left; vertical-align: top; }
.prose .tbl th, .tbl th { font-weight: 500; color: var(--muted); font-size: .75rem; white-space: nowrap; }
.tbl th button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
.tbl th button::after { content: " ↕"; opacity: .4; }
.tbl th[aria-sort="ascending"] button::after { content: " ↑"; opacity: 1; }
.tbl th[aria-sort="descending"] button::after { content: " ↓"; opacity: 1; }
.tbl tbody tr { transition: background-color .15s; }
.tbl tbody tr:hover { background: var(--soft); }
.tbl a { color: var(--ink); text-decoration: none; }
.tbl a:hover { color: var(--brand); }

.flow { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.flow .col { display: flex; flex-direction: column; gap: .4rem; }
.node { display: inline-block; padding: .5rem .75rem; border-radius: .6rem; background: var(--brand-soft); color: var(--ink);
  font-size: .85rem; line-height: 1.45; max-width: 14rem; border: 1px solid color-mix(in oklch, var(--brand) 25%, transparent); }
.arrow { color: var(--brand); font-size: 1.1rem; }
.loop { font-size: .75rem; color: var(--muted); }
@media (max-width: 640px) { .flow { flex-direction: column; align-items: stretch; } .arrow { transform: rotate(90deg); align-self: center; } }
ul.tree, ul.tree ul { list-style: none; margin: 0; padding-left: 1.2rem; position: relative; }
ul.tree { padding-left: 0; }
ul.tree ul li { position: relative; padding-top: .4rem; }
ul.tree ul li::before { content: ""; position: absolute; left: -.8rem; top: 0; bottom: 50%; width: .7rem;
  border-left: 1px solid var(--line); border-bottom: 1px solid var(--line); border-bottom-left-radius: .4rem; }

dl.glossary { display: grid; gap: .5rem; margin: 0; }
dl.glossary .term { display: grid; grid-template-columns: minmax(6rem, 11rem) 1fr; gap: .8rem; padding: .5rem 0; border-bottom: 1px solid var(--line); }
dl.glossary .term:last-child { border-bottom: 0; }
dl.glossary dt { font-weight: 600; font-size: .9rem; }
dl.glossary dd { margin: 0; font-size: .88rem; line-height: 1.6; color: var(--body); }
@media (max-width: 640px) { dl.glossary .term { grid-template-columns: 1fr; gap: .2rem; } }

.mindmap .root { display: inline-block; font-family: var(--serif); font-size: 1.15rem; padding: .35rem .9rem;
  border-radius: 999px; background: var(--brand); color: var(--bg); }
.mindmap ul { list-style: none; margin: 0; padding-left: 1.3rem; border-left: 1px solid var(--line); margin-left: .9rem; }
.mindmap > ul { margin-top: .5rem; }
.mindmap li { position: relative; padding: .25rem 0; }
.mindmap li::before { content: ""; position: absolute; left: -1.3rem; top: 1rem; width: 1.1rem; border-top: 1px solid var(--line); }
.mindmap a { display: inline-flex; gap: .45rem; padding: .2rem .6rem; border-radius: .5rem; font-size: .88rem;
  color: var(--ink); text-decoration: none; background: var(--soft); transition: background-color .15s, color .15s; }
.mindmap a:hover { background: var(--brand-soft); color: var(--brand); }
.mindmap .n { color: var(--muted); font-variant-numeric: tabular-nums; }
.mindmap summary { list-style: none; cursor: pointer; display: inline; }
.mindmap summary::-webkit-details-marker { display: none; }

details.ix-table { margin-top: 1rem; }
details.ix-table > summary { cursor: pointer; font-size: .85rem; color: var(--brand); }

/* A citation's passage, shown beside it. */
.ls-tip { position: fixed; z-index: 50; max-width: 20rem; padding: .7rem .8rem; border-radius: .7rem; border: 1px solid var(--line);
  background: var(--card); color: var(--ink); box-shadow: 0 10px 30px -10px oklch(0 0 0 / .35); font-size: .8rem; line-height: 1.55;
  pointer-events: none; animation: ls-in .15s ease-out; }
.ls-tip .h { display: block; font-size: .7rem; color: var(--muted); margin-bottom: .25rem; }
.ls-tip b { display: block; font-weight: 600; margin-bottom: .2rem; }

nav.toc a[aria-current] { color: var(--ink); font-weight: 500; }
.ls-progress { position: fixed; inset: 0 0 auto 0; height: 2px; background: var(--brand); transform-origin: left; transform: scaleX(0); z-index: 40; }

@media print {
  .tool, .tabs, .ls-tip, .ls-progress { display: none !important; }
  .panel[data-panel="data"] { display: none !important; }
  .panel[data-panel="view"] { display: block !important; }
  figure.ix { box-shadow: none; }
}
@media (prefers-reduced-motion: reduce) { .panel, .ls-tip { animation: none; } }
"""

# Our script, the only one the page runs (its hash is in the page's policy).
SCRIPT = r"""
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  var store = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  var saved = store.get("ls-theme");
  if (saved) root.dataset.theme = saved;
  var themeBtn = document.querySelector("[data-act=theme]");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    store.set("ls-theme", root.dataset.theme);
  });
  var printBtn = document.querySelector("[data-act=print]");
  if (printBtn) printBtn.addEventListener("click", function () { window.print(); });
  window.addEventListener("beforeprint", function () { document.querySelectorAll("details").forEach(function (d) { d.open = true; }); });

  // Tabs: a figure, or its data.
  document.querySelectorAll("figure.ix").forEach(function (fig) {
    var tabs = fig.querySelectorAll("[role=tab]");
    if (!tabs.length) return;
    function show(name) {
      tabs.forEach(function (t) { t.setAttribute("aria-selected", String(t.dataset.tab === name)); });
      fig.querySelectorAll(".panel").forEach(function (p) { p.hidden = p.dataset.panel !== name; });
    }
    tabs.forEach(function (t) { t.addEventListener("click", function () { show(t.dataset.tab); }); });
    show("view");
  });

  // Sorting a table by a column: numbers as numbers, words in the report's language.
  var lang = root.lang || "en";
  var collator = new Intl.Collator(lang, { numeric: true });
  document.querySelectorAll(".tbl th button[data-sort]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var th = btn.parentElement, table = th.closest("table"), i = Number(btn.dataset.sort);
      var up = th.getAttribute("aria-sort") !== "ascending";
      table.querySelectorAll("th").forEach(function (h) { h.removeAttribute("aria-sort"); });
      th.setAttribute("aria-sort", up ? "ascending" : "descending");
      var body = table.tBodies[0], rows = Array.prototype.slice.call(body.rows);
      rows.sort(function (a, b) {
        var x = a.cells[i].textContent.trim(), y = b.cells[i].textContent.trim();
        var nx = parseFloat(x.replace(/,/g, "")), ny = parseFloat(y.replace(/,/g, ""));
        var c = !isNaN(nx) && !isNaN(ny) ? nx - ny : collator.compare(x, y);
        return up ? c : -c;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });

  // A citation's passage beside it: a figure's own fact, or the Source's first.
  var sources = {};
  try { sources = JSON.parse(document.getElementById("ls-sources").textContent); } catch (e) {}
  var tip = null;
  function hide() { if (tip) { tip.remove(); tip = null; } }
  function place(el) {
    var r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 8));
    var top = r.bottom + 8 + h < innerHeight ? r.bottom + 8 : r.top - h - 8;
    tip.style.left = left + "px"; tip.style.top = Math.max(8, top) + "px";
  }
  function show(el) {
    var n = (el.getAttribute("href") || "").replace("#src-", ""), s = sources[n];
    if (!s && !el.dataset.tip) return;
    hide();
    tip = document.createElement("div");
    tip.className = "ls-tip";
    var head = document.createElement("span"); head.className = "h"; head.textContent = "[" + n + "] " + (s ? s.h : "");
    tip.appendChild(head);
    if (s) { var b = document.createElement("b"); b.textContent = s.t; tip.appendChild(b); }
    var body = document.createElement("span"); body.textContent = el.dataset.tip || (s && s.e) || "";
    tip.appendChild(body);
    document.body.appendChild(tip);
    place(el);
  }
  document.addEventListener("mouseover", function (e) { var c = e.target.closest && e.target.closest("a.cite"); if (c) show(c); });
  document.addEventListener("mouseout", function (e) { var c = e.target.closest && e.target.closest("a.cite"); if (c) hide(); });
  document.addEventListener("focusin", function (e) { if (e.target.matches && e.target.matches("a.cite")) show(e.target); });
  document.addEventListener("focusout", hide);
  addEventListener("scroll", hide, { passive: true });

  // The contents follow the reader, with a line along the top.
  var bar = document.createElement("div"); bar.className = "ls-progress"; document.body.appendChild(bar);
  var heads = Array.prototype.slice.call(document.querySelectorAll("article h2[id], article h3[id], article h4[id]"));
  var links = {};
  document.querySelectorAll("nav.toc.side a[href^='#']").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
  var article = document.querySelector("article"), frame = 0;
  function measure() {
    frame = 0;
    var current = null;
    for (var i = 0; i < heads.length; i++) { if (heads[i].getBoundingClientRect().top < 120) current = heads[i].id; else break; }
    Object.keys(links).forEach(function (id) { if (id === current) links[id].setAttribute("aria-current", "true"); else links[id].removeAttribute("aria-current"); });
    var box = article.getBoundingClientRect(), span = box.height - innerHeight;
    bar.style.transform = "scaleX(" + (span > 0 ? Math.min(1, Math.max(0, -box.top / span)) : 1) + ")";
  }
  addEventListener("scroll", function () { if (!frame) frame = requestAnimationFrame(measure); }, { passive: true });
  measure();

  // Live charts, when the library came with the page.
  var specs = document.getElementById("ls-charts");
  if (specs && window.echarts && window.lsOptions) {
    var all = JSON.parse(specs.textContent);
    document.querySelectorAll(".chart[data-chart]").forEach(function (el) {
      var spec = all[el.dataset.chart];
      if (!spec) return;
      el.innerHTML = "";
      el.style.height = window.lsHeight(spec) + "px";
      var chart = echarts.init(el, null, { renderer: "svg" });
      chart.setOption(window.lsOptions(spec, true));
      addEventListener("resize", function () { chart.resize(); });
    });
  }
})();
"""


def _json_script(element_id, value):
    # Data, not code: the policy does not run it, and "</" cannot close it.
    text = json.dumps(value, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="{element_id}">{text}</script>'


def _hash(script):
    return "'sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii") + "'"


def render(report, visuals=None, engine_label="", finished_at=None, full=False, svgs=None):
    """The page. `visuals` as litstorm.visuals keeps them (or None: only the
    figures made from the report); `svgs` maps a chart's id to its drawn SVG
    (drawn here with Chromium when not given)."""
    language = report["language"]
    labels = LABELS[language]
    hidden = set((visuals or {}).get("hidden") or [])
    blocks = [b for b in (visuals or {}).get("blocks") or [] if b["id"] not in hidden]

    specs = chart_specs(blocks, language)
    if report["sources"]:
        specs["most-cited"] = most_cited_spec(report)[0]
    if svgs is None:
        ids = list(specs)
        svgs = dict(zip(ids, prerender([specs[i] for i in ids])))

    after_section = {}
    after_lead = []
    if visuals and blocks:
        key = "made_by" if visuals_mod.has_evidence(report) else "made_by_report"
        after_lead.append(f'<p class="ix-note">{_e(labels[key].format(model=visuals.get("model") or "AI"))}</p>')
    if report["sections"]:
        after_lead.append(_outline(report, labels))
    for b in blocks:
        if b["type"] == "chart":
            figure = _chart(b, labels, language, svgs.get(b["id"], ""))
        elif b["type"] == "comparison":
            figure = _comparison(b, labels, language, svgs.get(b["id"], ""))
        else:
            figure = _BLOCKS[b["type"]](b, labels, language)
        if b["anchor"] == "lead":
            after_lead.append(figure)
        else:
            after_section[b["anchor"]] = after_section.get(b["anchor"], "") + figure

    sources = {
        str(s["id"]): {"t": s["title"], "h": page_mod._host(s["url"]), "e": (s["evidence"][0][:240] if s["evidence"] else "")}
        for s in report["sources"]
    }
    scripts = [SCRIPT]
    body_end = [_json_script("ls-sources", sources)]
    if full and specs:
        with open(ECHARTS, encoding="utf-8") as f:
            scripts = [f.read(), CHART_JS, SCRIPT]
        body_end.append(_json_script("ls-charts", specs))
    body_end += [f"<script>{s}</script>" for s in scripts]
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; "
        f"script-src {' '.join(_hash(s) for s in scripts)}; base-uri 'none'; form-action 'none'"
    )
    tools = (
        f'<span class="tool"><button type="button" data-act="theme">{labels["theme"]}</button>'
        f'<button type="button" data-act="print">{labels["print"]}</button></span>'
    )
    return page_mod.page(
        report,
        engine_label=engine_label,
        finished_at=finished_at,
        head=f'<meta http-equiv="Content-Security-Policy" content="{policy}">\n<style>{CSS}</style>',
        tools=tools,
        after_lead="\n".join(after_lead),
        after_section=after_section,
        sources_extra=_sources_extra(report, labels, svgs.get("most-cited", "")) if report["sources"] else "",
        body_end="\n".join(body_end),
    )


def cached(report_path, report, visuals=None, engine_label="", finished_at=None, full=False):
    """The page, drawn once for this report, these visuals and this variant,
    and kept beside report.json (drawing charts takes Chromium a moment)."""
    key = json.dumps(
        [render_code(), visuals_mod.report_hash(report), visuals, engine_label, str(finished_at), bool(full)],
        ensure_ascii=False, sort_keys=True, default=str,
    )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    directory = os.path.dirname(report_path)
    variant = "full" if full else "static"
    path = os.path.join(directory, f"interactive-{variant}-{digest}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    # The page people get is the brief and its reading canvas (render/brief.py).
    from litstorm.render import brief

    page = brief.render(report, visuals, engine_label, finished_at, full=full)
    for old in glob.glob(os.path.join(directory, f"interactive-{variant}-*.html")):
        try:
            os.remove(old)
        except OSError:
            pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, path)
    return page
