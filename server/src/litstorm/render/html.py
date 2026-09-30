"""report.json as one HTML file that opens anywhere, offline.

It reads like the report page in the web app: a serif title under a line of
facts, the overview marked by a line, numbered sections, citations as small
pills that jump to their Source, and the Sources as cards. On a wide screen
the contents stay beside the text as it scrolls — CSS alone, no script.

No scripts, no network: the web app's faces (Geist, IBM Plex Sans Thai, Noto
Serif Thai, Instrument Serif; all SIL OFL, licences beside them in fonts/)
travel inside the file, so a Thai report looks the same on a machine without
Thai fonts. The PDF is printed from this same page (docs/adr/0005).

Model output is untrusted text: raw HTML in it is escaped, not rendered.
"""

import base64
import html
import os
import re
from datetime import datetime, timedelta, timezone
from functools import cache
from urllib.parse import unquote, urlparse

from markdown_it import MarkdownIt

from litstorm import report as report_mod

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")

LABELS = {
    "th": {
        "contents": "สารบัญ",
        "sources": "แหล่งอ้างอิง",
        "sources_n": "{n} แหล่งอ้างอิง",
        "overview": "สรุปภาพรวม",
        "read": "อ่านราว {n} นาที",
        "evidence": "ข้อความหลักฐาน",
        "excerpt_note": "ข้อความบางส่วนที่ระบบใช้จริง ไม่ใช่ต้นฉบับเต็ม",
        "no_evidence": "ระบบไม่ได้บันทึกข้อความหลักฐานของแหล่งนี้",
        "open": "เปิดเว็บไซต์ต้นทาง",
        "top": "กลับขึ้นด้านบน",
    },
    "en": {
        "contents": "Contents",
        "sources": "Sources",
        "sources_n": "{n} sources",
        "overview": "Overview",
        "read": "{n} min read",
        "evidence": "Evidence",
        "excerpt_note": "Excerpts the system actually used, not the full original",
        "no_evidence": "No evidence was recorded for this source",
        "open": "Open the original",
        "top": "Back to top",
    },
}

_THAI_MONTHS = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()
_BANGKOK = timezone(timedelta(hours=7))

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# Thai and Latin cut apart, as the web app loads them (fontsource's subsets).
_THAI = "U+02D7,U+0303,U+0331,U+0E01-0E5B,U+200C-200D,U+25CC"
_LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
    "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
)
# family, file, weight, unicode-range. A family per script, listed Latin
# then Thai as the web app lists them: faces of one family with different
# weights are matched by weight first, and the Thai one was never used.
_FACES = [
    ("LS Latin", "geist-latin-wght-normal.woff2", "100 900", _LATIN),
    ("LS Thai", "ibm-plex-sans-thai-thai-400-normal.woff2", "400", _THAI),
    ("LS Thai", "ibm-plex-sans-thai-thai-600-normal.woff2", "500 700", _THAI),
    ("LS Serif Latin", "instrument-serif-latin-400-normal.woff2", "400", _LATIN),
    ("LS Serif Thai", "noto-serif-thai-thai-wght-normal.woff2", "100 900", _THAI),
]


@cache
def _font_faces():
    rules = []
    for family, name, weight, ranges in _FACES:
        with open(os.path.join(_FONTS_DIR, name), "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-display:swap;font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');unicode-range:{ranges};}}"
        )
    return "\n".join(rules)


CSS = """
:root {
  --bg: oklch(1 0 0); --ink: oklch(0.145 0 0); --body: oklch(0.145 0 0 / 0.88);
  --card: oklch(1 0 0); --soft: oklch(0.97 0 0); --muted: oklch(0.556 0 0);
  --line: oklch(0.922 0 0); --brand: oklch(0.546 0.215 262.9); --brand-soft: oklch(0.955 0.025 262);
  --fav-l: 0.93; --fav-c: 0.045; --fav-ink-l: 0.42; --fav-ink-c: 0.12;
  --sans: "LS Latin", "LS Thai", "IBM Plex Sans Thai", "Noto Sans Thai", "Sarabun", "Leelawadee UI", "Thonburi", "Tahoma", system-ui, sans-serif;
  --serif: "LS Serif Latin", "LS Serif Thai", "Noto Serif Thai", "Instrument Serif", Georgia, serif;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: oklch(0.145 0 0); --ink: oklch(0.985 0 0); --body: oklch(0.985 0 0 / 0.86);
    --card: oklch(0.185 0 0); --soft: oklch(0.269 0 0 / 0.6); --muted: oklch(0.708 0 0);
    --line: oklch(1 0 0 / 0.1); --brand: oklch(0.707 0.165 254.6); --brand-soft: oklch(0.28 0.06 262);
    --fav-l: 0.33; --fav-c: 0.06; --fav-ink-l: 0.88; --fav-ink-c: 0.07;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  font-size: 16px; line-height: 1.75; -webkit-font-smoothing: antialiased; }
a { color: var(--brand); }
.page { max-width: 72rem; margin: 0 auto; padding: 3rem 1.5rem 5rem; display: grid; gap: 3.5rem; }
@media (min-width: 1100px) { .page { grid-template-columns: minmax(0, 1fr) 15rem; } }
article { min-width: 0; max-width: 46rem; }

/* The facts above the title, and the title. */
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem 1.1rem; font-size: .78rem; color: var(--muted); }
.meta .mode { color: var(--brand); background: var(--brand-soft); border-radius: 999px; padding: .1rem .65rem; font-weight: 500; }
.meta a { color: inherit; text-decoration: none; }
h1 { font-family: var(--serif); font-weight: 400; font-size: clamp(2.2rem, 5vw, 3.1rem); line-height: 1.15;
  letter-spacing: -.01em; margin: 1rem 0 0; text-wrap: balance; }

/* The first sources, as cards under the title. */
.strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; margin-top: 1.8rem; }
@media (min-width: 640px) { .strip { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.strip a { display: flex; flex-direction: column; gap: .5rem; padding: .75rem; border: 1px solid var(--line);
  border-radius: .8rem; background: var(--card); color: inherit; text-decoration: none;
  transition: transform .2s ease-out, box-shadow .2s ease-out, background-color .2s; }
.strip a:hover { transform: translateY(-2px); box-shadow: 0 6px 20px -8px oklch(0 0 0 / .25); background: var(--soft); }
.strip .t { font-size: .75rem; font-weight: 500; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.strip .d { margin-top: auto; display: flex; align-items: center; gap: .35rem; font-size: .68rem; color: var(--muted); min-width: 0; }
.strip .d span.host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.strip .more { justify-content: space-between; font-size: .75rem; color: var(--muted); }
.stack { display: flex; }
.stack .fav { margin-right: -.25rem; box-shadow: 0 0 0 2px var(--card); }

/* A site's letter, in that site's own hue. */
.fav { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; width: 1rem; height: 1rem;
  border-radius: 5px; font-size: .58rem; font-weight: 600; text-transform: uppercase; line-height: 1;
  background: oklch(var(--fav-l) var(--fav-c) var(--h)); color: oklch(var(--fav-ink-l) var(--fav-ink-c) var(--h)); }
.num { display: inline-flex; align-items: center; justify-content: center; min-width: 1.25rem; height: 1.25rem;
  padding: 0 .35rem; border-radius: 999px; background: var(--brand-soft); color: var(--brand);
  font-size: .68rem; font-weight: 500; font-variant-numeric: tabular-nums; line-height: 1; flex-shrink: 0; }
.num.sm { min-width: 1rem; height: 1rem; font-size: .6rem; margin-left: auto; }

/* The text. */
.prose { margin-top: 2.5rem; font-size: 1.0625rem; line-height: 1.9; }
.prose p, .prose li { color: var(--body); }
.prose p { margin: 0 0 1.1rem; }
.prose ul, .prose ol { margin: 0 0 1.1rem; padding-left: 1.4rem; }
.prose li { margin: .3rem 0; }
.prose strong { font-weight: 600; color: var(--ink); }
.prose blockquote { margin: 0 0 1.1rem; padding: .25rem 0 .25rem 1rem; border-left: 3px solid var(--line); color: var(--muted); }
.prose code { padding: .1rem .35rem; font-size: .9em; background: var(--soft); border-radius: .3rem; }
.prose table { display: block; max-width: 100%; overflow-x: auto; margin: 0 0 1.2rem; font-size: .95rem; border-collapse: collapse; }
.prose th, .prose td { padding: .45rem .75rem; border: 1px solid var(--line); text-align: left; }
.prose th { font-weight: 600; background: var(--soft); }
.overview { border-left: 2px solid color-mix(in oklch, var(--brand) 60%, transparent); padding-left: 1.4rem; }
.overview p { font-size: 1.075rem; color: var(--ink); }
.label { display: block; margin: 0 0 .5rem; font-size: .75rem; font-weight: 500; letter-spacing: .02em; color: var(--brand); }

h2, h3, h4, h5, h6 { display: flex; align-items: baseline; gap: .75rem; scroll-margin-top: 1.5rem; text-wrap: balance; }
h2 { font-family: var(--serif); font-weight: 400; font-size: 1.85rem; line-height: 1.3; margin: 3.5rem 0 1rem;
  padding-top: 2rem; border-top: 1px solid var(--line); letter-spacing: -.005em; }
h3 { font-size: 1.15rem; font-weight: 600; margin: 2.3rem 0 .75rem; line-height: 1.45; }
h4, h5, h6 { font-size: 1rem; font-weight: 600; margin: 1.8rem 0 .5rem; }
h2 .n, h3 .n, h4 .n, h5 .n, h6 .n { font-family: var(--sans); font-size: .85rem; font-weight: 400;
  color: var(--muted); font-variant-numeric: tabular-nums; flex-shrink: 0; }
h2 .n { font-weight: 500; color: var(--brand); }

/* A citation: a small pill; its brackets stay in the text for copying. */
a.cite { display: inline-flex; align-items: center; justify-content: center; min-width: 1.35rem; height: 1.15rem;
  margin: 0 .1rem; padding: 0 .3rem; font-size: .7rem; font-weight: 500; line-height: 1; vertical-align: .15em;
  color: var(--brand); background: var(--brand-soft); border-radius: 999px; text-decoration: none;
  transition: background-color .15s, color .15s, transform .15s; }
a.cite:hover { background: var(--brand); color: #fff; transform: translateY(-1px); }
a.cite .b { font-size: 0; }

/* The Sources. */
section.sources { margin-top: 4rem; padding-top: 2rem; border-top: 1px solid var(--line); }
section.sources h2 { border: 0; margin: 0 0 1.2rem; padding: 0; font-size: 1.6rem; }
section.sources h2 .count { font-family: var(--sans); font-size: .85rem; color: var(--muted); }
ol.sources { list-style: none; margin: 0; padding: 0; display: grid; gap: .6rem; }
@media (min-width: 640px) { ol.sources { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
ol.sources li { display: flex; flex-direction: column; gap: .35rem; padding: .85rem .9rem; border: 1px solid var(--line);
  border-radius: .8rem; background: var(--card); scroll-margin-top: 1.5rem; min-width: 0;
  transition: border-color .3s, box-shadow .3s; }
ol.sources li:target { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); }
ol.sources li.wide { grid-column: 1 / -1; }
.src-head { display: flex; align-items: center; gap: .4rem; font-size: .75rem; color: var(--muted); min-width: 0; }
.src-head .host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.src-title { font-size: .9rem; font-weight: 500; line-height: 1.4; }
.src-title a { color: var(--ink); text-decoration: none; }
.src-title a:hover { color: var(--brand); }
.src-url { color: var(--muted); font-size: .72rem; word-break: break-all; line-height: 1.4; }
details { margin-top: .2rem; }
summary { cursor: pointer; color: var(--muted); font-size: .8rem; }
details blockquote { margin: .5rem 0 0; padding: .45rem .8rem; border-left: 2px solid var(--brand); background: var(--soft);
  border-radius: .5rem; font-size: .85rem; line-height: 1.65; }
.note { color: var(--muted); font-size: .75rem; }

/* The contents: beside the text on a wide screen, following it down. */
nav.toc { font-size: .875rem; }
nav.toc .inner { position: sticky; top: 1.5rem; max-height: calc(100vh - 3rem); overflow-y: auto; }
nav.toc .title { margin: 0 0 .75rem; font-size: .72rem; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
nav.toc ol { list-style: none; margin: 0; padding: 0; }
nav.toc ol ol { margin: .15rem 0 0 .75rem; }
nav.toc li { display: grid; grid-template-columns: auto 1fr; column-gap: .5rem; padding: .2rem 0; line-height: 1.4; }
nav.toc li > ol { grid-column: 1 / -1; }
nav.toc .n { color: color-mix(in oklch, var(--muted) 70%, transparent); font-variant-numeric: tabular-nums; }
nav.toc a { color: var(--muted); text-decoration: none; }
nav.toc a:hover { color: var(--ink); }
nav.toc .foot { margin-top: 1.2rem; padding-top: .9rem; border-top: 1px solid var(--line); display: grid; gap: .3rem; }
nav.toc.inline { display: none; margin-top: 2rem; }
nav.toc.inline .inner { position: static; max-height: none; background: var(--soft); border: 1px solid var(--line);
  border-radius: .8rem; padding: 1rem 1.2rem; }
@media (max-width: 1099px) {
  nav.toc.side { display: none; }
  nav.toc.inline { display: block; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { transition: none !important; }
}

/* Paper: always light, one column, the contents first, nothing that only
   makes sense on a screen. */
@media print {
  :root { --bg: #fff; --ink: #111; --body: #222; --card: #fff; --soft: #f5f5f7; --muted: #5f6368;
    --line: #dcdcdc; --brand: #2455a4; --brand-soft: #e8eefb; --fav-l: 0.93; --fav-c: 0.045; --fav-ink-l: 0.42; --fav-ink-c: 0.12; }
  body { font-size: 11pt; }
  .page { display: block; max-width: none; padding: 0; }
  article { max-width: none; }
  nav.toc.side, .strip { display: none; }
  nav.toc.inline { display: block; margin: 1.5rem 0 0; }
  nav.toc.inline .inner { background: none; border: 0; border-top: 1px solid var(--line); border-radius: 0; padding: 1rem 0 0; }
  .prose { margin-top: 1.5rem; font-size: 11pt; }
  h1 { font-size: 26pt; }
  h2 { font-size: 17pt; margin-top: 2rem; }
  h2, h3, h4 { break-after: avoid; }
  a { color: inherit; }
  a.cite { color: #2455a4; }
  details > summary { display: none; }
  ol.sources { grid-template-columns: 1fr; }
  ol.sources li { border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: .5rem 0; }
  /* Keep a source's name with its link, but let long evidence flow on:
     keeping the whole entry together left most of each page blank. */
  .src-head, .src-title, .src-url, .note { break-after: avoid; break-inside: avoid; }
}
"""


def _markdown(text):
    rendered = _md.render(text or "")
    return report_mod.CITATION.sub(
        lambda m: (
            f'<a class="cite" href="#src-{m.group(1)}">'
            f'<span class="b">[</span>{m.group(1)}<span class="b">]</span></a>'
        ),
        rendered,
    )


def _numbered(sections, prefix=""):
    out = []
    for i, s in enumerate(sections, 1):
        n = f"{prefix}.{i}" if prefix else str(i)
        out.append({**s, "n": n, "children": _numbered(s["children"], n)})
    return out


def _toc(sections):
    if not sections:
        return ""
    items = "".join(
        f'<li><span class="n">{s["n"]}</span><a href="#{s["id"]}">{html.escape(s["heading"])}</a>{_toc(s["children"])}</li>'
        for s in sections
    )
    return f"<ol>{items}</ol>"


def _sections(sections, level=2):
    out = []
    tag = f"h{min(level, 6)}"
    for s in sections:
        n = s["n"].zfill(2) if level == 2 else s["n"]
        out.append(f'<{tag} id="{s["id"]}"><span class="n">{n}</span><span>{html.escape(s["heading"])}</span></{tag}>')
        out.append(_markdown(s["body"]))
        out.append(_sections(s["children"], level + 1))
    return "\n".join(out)


def _host(url):
    host = urlparse(url).hostname or url
    return host[4:] if host.startswith("www.") else host


def _fav(url):
    # The web app's letter and hue for a site (report.tsx, Favicon).
    host = _host(url)
    hue = 0
    for ch in host:
        hue = (hue * 31 + ord(ch)) % 360
    return f'<span class="fav" style="--h:{hue}">{html.escape(host[:1])}</span>'


def _safe_href(url):
    return html.escape(url, quote=True) if re.match(r"^https?://", url) else "#"


def _source(source, labels, with_evidence, expanded):
    href = _safe_href(source["url"])
    # Thai addresses arrive percent-encoded; show them as a reader would type them.
    shown = html.escape(unquote(source["url"]))
    wide = with_evidence and source["evidence"]
    parts = [
        f'<li id="src-{source["id"]}"' + (' class="wide"' if wide else "") + ">",
        f'<div class="src-head"><span class="num">{source["id"]}</span>{_fav(source["url"])}'
        f'<span class="host">{html.escape(_host(source["url"]))}</span></div>',
        f'<div class="src-title"><a href="{href}" rel="noopener noreferrer" target="_blank">{html.escape(source["title"])}</a></div>',
        f'<div class="src-url">{shown}</div>',
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


def _strip(sources, labels):
    if not sources:
        return ""
    cards = [
        f'<a href="#src-{s["id"]}"><span class="t">{html.escape(s["title"])}</span>'
        f'<span class="d">{_fav(s["url"])}<span class="host">{html.escape(_host(s["url"]))}</span>'
        f'<span class="num sm">{s["id"]}</span></span></a>'
        for s in sources[:3]
    ]
    if len(sources) > 3:
        favs = "".join(_fav(s["url"]) for s in sources[3:8])
        cards.append(
            f'<a class="more" href="#sources"><span class="stack">{favs}</span>'
            f'<span>{labels["sources_n"].format(n=len(sources))}</span></a>'
        )
    return f'<div class="strip">{"".join(cards)}</div>'


def _minutes(report):
    # As the web app counts (report.tsx, readingMinutes): Thai in letters, others in words.
    def text(sections):
        return " ".join(f"{s['heading']} {s['body']} {text(s['children'])}" for s in sections)

    body = report_mod.CITATION.sub("", f"{report['lead']} {text(report['sections'])}")
    n = len(re.sub(r"\s", "", body)) / 900 if report["language"] == "th" else len(body.split()) / 230
    return max(1, round(n))


def _date(when, language):
    if not when:
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    d = when.astimezone(_BANGKOK)
    if language == "th":
        return f"{d.day} {_THAI_MONTHS[d.month - 1]} {d.year + 543}"
    return f"{d.day} {d.strftime('%b')} {d.year}"


def render(report, with_evidence=False, expanded=False, engine_label="", finished_at: datetime | None = None):
    """The page. `expanded` opens every evidence block, for printing:
    Chromium does not print what a closed <details> holds."""
    labels = LABELS[report["language"]]
    title = html.escape(report["title"])
    sections = _numbered(report["sections"])
    toc = _toc(sections)
    sources = "".join(_source(s, labels, with_evidence, expanded) for s in report["sources"])
    facts = []
    if engine_label:
        facts.append(f'<span class="mode">{html.escape(engine_label)}</span>')
    if finished_at:
        facts.append(f"<span>{_date(finished_at, report['language'])}</span>")
    facts.append(f"<span>{labels['read'].format(n=_minutes(report))}</span>")
    facts.append(f'<a href="#sources">{labels["sources_n"].format(n=len(report["sources"]))}</a>')
    lead = (
        f'<div class="overview"><span class="label">{labels["overview"]}</span>{_markdown(report["lead"])}</div>'
        if report["lead"].strip()
        else ""
    )
    side = inline = ""
    if toc:
        side = (
            f'<nav class="toc side"><div class="inner"><p class="title">{labels["contents"]}</p>{toc}'
            f'<div class="foot"><a href="#sources">{labels["sources"]} · {len(report["sources"])}</a>'
            f'<a href="#top">↑ {labels["top"]}</a></div></div></nav>'
        )
        inline = f'<nav class="toc inline"><div class="inner"><p class="title">{labels["contents"]}</p>{toc}</div></nav>'

    return f"""<!doctype html>
<html lang="{report['language']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{_font_faces()}
{CSS}</style>
</head>
<body id="top">
<div class="page">
<article>
<header>
<div class="meta">{''.join(facts)}</div>
<h1>{title}</h1>
</header>
{_strip(report['sources'], labels)}
{inline}
<div class="prose">
{lead}
{_sections(sections)}
</div>
<section class="sources" id="sources">
<h2>{labels['sources']} <span class="count">{len(report['sources'])}</span></h2>
<ol class="sources">{sources}</ol>
</section>
</article>
{side}
</div>
</body>
</html>
"""
