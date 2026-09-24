"""report.json as one HTML file that opens anywhere, offline.

Contents, citations that jump to their Source, and — when the owner asks for
it at export — the Evidence behind each Source, marked as excerpts. No
scripts, no network: fonts come from the reader's system, with Thai faces
named first so a Thai report never falls back to boxes. The PDF is printed
from this same page (docs/adr/0005).

Model output is untrusted text: raw HTML in it is escaped, not rendered.
"""

import html
import re
from urllib.parse import unquote

from markdown_it import MarkdownIt

from litstorm import report as report_mod

_md = MarkdownIt("commonmark", {"html": False, "linkify": False})

LABELS = {
    "th": {
        "contents": "สารบัญ",
        "sources": "แหล่งอ้างอิง",
        "evidence": "ข้อความหลักฐาน",
        "excerpt_note": "ข้อความบางส่วนที่ระบบใช้จริง ไม่ใช่ต้นฉบับเต็ม",
        "no_evidence": "ระบบไม่ได้บันทึกข้อความหลักฐานของแหล่งนี้",
        "open": "เปิดเว็บไซต์ต้นทาง",
    },
    "en": {
        "contents": "Contents",
        "sources": "Sources",
        "evidence": "Evidence",
        "excerpt_note": "Excerpts the system actually used, not the full original",
        "no_evidence": "No evidence was recorded for this source",
        "open": "Open the original",
    },
}

CSS = """
:root { --ink:#1d1d1f; --muted:#5f6368; --line:#e3e3e3; --accent:#2455a4; --paper:#ffffff; --soft:#f6f7f9; }
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink);
  font-family: "Noto Sans Thai", "Sarabun", "Leelawadee UI", "Thonburi", "Tahoma", "Noto Sans", system-ui, sans-serif;
  font-size: 16px; line-height: 1.75; }
main { max-width: 46rem; margin: 0 auto; padding: 2.5rem 1rem 4rem; }
h1 { font-size: 2rem; line-height: 1.3; margin: 0 0 1.5rem; }
h2 { font-size: 1.45rem; margin: 2.2rem 0 .6rem; line-height: 1.35; }
h3 { font-size: 1.2rem; margin: 1.8rem 0 .5rem; }
h4, h5, h6 { font-size: 1.05rem; margin: 1.4rem 0 .4rem; }
p { margin: 0 0 1rem; }
a { color: var(--accent); }
a.cite { text-decoration: none; font-size: .78em; vertical-align: super; line-height: 1; padding: .1em .12em; }
nav.toc { background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: .8rem 1.2rem; margin: 0 0 2rem; }
nav.toc h2 { font-size: 1rem; margin: 0 0 .3rem; }
nav.toc ol { margin: 0; padding-left: 1.2rem; }
section.sources { border-top: 1px solid var(--line); margin-top: 3rem; padding-top: 1rem; }
ol.sources { padding-left: 1.6rem; }
ol.sources li { margin: 0 0 1rem; scroll-margin-top: 1rem; }
ol.sources li:target { background: #fff6d6; }
.src-title { font-weight: 600; }
.src-url { color: var(--muted); font-size: .85rem; word-break: break-all; }
details { margin-top: .3rem; }
summary { cursor: pointer; color: var(--muted); font-size: .9rem; }
blockquote { margin: .5rem 0; padding: .4rem .9rem; border-left: 3px solid var(--line); color: #333; background: var(--soft); font-size: .92rem; }
.note { color: var(--muted); font-size: .85rem; }
@media print {
  main { max-width: none; padding: 0; }
  a { color: inherit; }
  details > summary { display: none; }
  h2, h3 { break-after: avoid; }
  /* Keep a source's name with its link, but let long evidence flow on:
     keeping the whole entry together left most of each page blank. */
  .src-title, .src-url, .note { break-after: avoid; break-inside: avoid; }
}
"""


def _markdown(text):
    rendered = _md.render(text or "")
    return report_mod.CITATION.sub(
        lambda m: f'<a class="cite" href="#src-{m.group(1)}">[{m.group(1)}]</a>', rendered
    )


def _toc(sections):
    if not sections:
        return ""
    items = "".join(
        f'<li><a href="#{s["id"]}">{html.escape(s["heading"])}</a>{_toc(s["children"])}</li>'
        for s in sections
    )
    return f"<ol>{items}</ol>"


def _sections(sections, level=2):
    out = []
    tag = f"h{min(level, 6)}"
    for s in sections:
        out.append(f'<{tag} id="{s["id"]}">{html.escape(s["heading"])}</{tag}>')
        out.append(_markdown(s["body"]))
        out.append(_sections(s["children"], level + 1))
    return "\n".join(out)


def _source(source, labels, with_evidence, expanded):
    url = html.escape(source["url"], quote=True)
    safe_href = url if re.match(r"^https?://", source["url"]) else "#"
    # Thai addresses arrive percent-encoded; show them as a reader would type them.
    shown = html.escape(unquote(source["url"]))
    parts = [
        f'<li id="src-{source["id"]}">',
        f'<div class="src-title">{html.escape(source["title"])}</div>',
        f'<div class="src-url"><a href="{safe_href}" rel="noopener noreferrer" target="_blank">{shown}</a></div>',
    ]
    if with_evidence:
        if source["evidence"]:
            quotes = "".join(f"<blockquote>{html.escape(e)}</blockquote>" for e in source["evidence"])
            parts.append(
                f"<details{' open' if expanded else ''}>"
                f"<summary>{labels['evidence']} ({len(source['evidence'])})</summary>"
                f'<div class="note">{labels["excerpt_note"]}</div>{quotes}</details>'
            )
        else:
            parts.append(f'<div class="note">{labels["no_evidence"]}</div>')
    parts.append("</li>")
    return "".join(parts)


def render(report, with_evidence=False, expanded=False):
    """The page. `expanded` opens every evidence block, for printing:
    Chromium does not print what a closed <details> holds."""
    labels = LABELS[report["language"]]
    title = html.escape(report["title"])
    toc = _toc(report["sections"])
    sources = "".join(_source(s, labels, with_evidence, expanded) for s in report["sources"])
    return f"""<!doctype html>
<html lang="{report['language']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{title}</h1>
{_markdown(report['lead'])}
{f'<nav class="toc"><h2>{labels["contents"]}</h2>{toc}</nav>' if toc else ''}
{_sections(report['sections'])}
<section class="sources">
<h2>{labels['sources']}</h2>
<ol class="sources">{sources}</ol>
</section>
</main>
</body>
</html>
"""
