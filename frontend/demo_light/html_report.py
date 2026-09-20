"""A finished STORM run, compiled into one self-contained interactive HTML file.

The article the app already shows is only the visible third of a run. Behind it
sit the sources that were found, the query that surfaced each one, and the
interviews the perspectives held to get there. A `.md` download throws all of
that away and hands the reader a wall of prose with bracketed numbers that
point nowhere.

This module compiles the whole run into one HTML file that opens anywhere with
no server, no build step and no network: the article with live citations, the
evidence behind them, and the interviews that produced it. Everything is
inlined, so the file can be mailed to an advisor or dropped in a shared drive
and still work.

Nothing here imports Streamlit. The report is built from the run's files on
disk, so a batch script in `examples/` can call `build_report()` just as the
demo's download button does.
"""

import datetime
import html
import json
import os
import re

import markdown

# The report is read outside the app, often by someone who never saw it, so it
# carries its own small vocabulary rather than reaching into `ui_language`.
LABELS = {
    "English": {
        "lead": "Summary",
        "views": "Report views",
        "article": "Article",
        "evidence": "Evidence",
        "interviews": "Interviews",
        "contents": "Contents",
        "sources": "Sources",
        "perspectives": "Perspectives",
        "questions": "Questions asked",
        "sections": "Sections",
        "words": "Words",
        "chars": "Characters",
        "cited": "cited",
        "times": "×",
        "uncited": "Not cited in the article",
        "found_by": "Found by searching",
        "highlights": "Highlights",
        "filter_sources": "Filter sources by title, site or search query",
        "no_match": "No source matches that filter.",
        "cited_in": "Cited in",
        "see_evidence": "See in evidence",
        "asked": "Asked",
        "answered": "Answered",
        "theme": "Switch theme",
        "generated": "Compiled",
        "no_sources": "This run recorded no sources.",
        "no_interviews": "This run recorded no interviews.",
        "discussion": "Discussion",
        "speakers": "Speakers",
        "said": "Turns taken",
        "no_discussion": "This run recorded no discussion.",
        "you": "You",
        "turn": "turn",
        "turns": "turns",
        "made_with": "Compiled from a STORM research run",
    },
    "ไทย": {
        "lead": "บทสรุป",
        "views": "ส่วนต่าง ๆ ของรายงาน",
        "article": "บทความ",
        "evidence": "หลักฐาน",
        "interviews": "บทสัมภาษณ์",
        "contents": "สารบัญ",
        "sources": "แหล่งอ้างอิง",
        "perspectives": "มุมมอง",
        "questions": "คำถาม",
        "sections": "หัวข้อ",
        "words": "คำ",
        "chars": "ตัวอักษร",
        "cited": "อ้างอิง",
        "times": "ครั้ง",
        "uncited": "ไม่ได้อ้างอิงในบทความ",
        "found_by": "พบจากการค้นหา",
        "highlights": "ข้อความสำคัญ",
        "filter_sources": "กรองแหล่งอ้างอิงจากชื่อ เว็บไซต์ หรือคำค้น",
        "no_match": "ไม่พบแหล่งอ้างอิงที่ตรงกับคำค้น",
        "cited_in": "อ้างอิงในหัวข้อ",
        "see_evidence": "ดูข้อมูลในส่วนหลักฐาน",
        "asked": "ถาม",
        "answered": "ตอบ",
        "theme": "สลับธีม",
        "generated": "สร้างเมื่อ",
        "no_sources": "การค้นคว้าครั้งนี้ไม่ได้บันทึกแหล่งอ้างอิงไว้",
        "no_interviews": "การค้นคว้าครั้งนี้ไม่ได้บันทึกบทสัมภาษณ์ไว้",
        "discussion": "บันทึกการสนทนา",
        "speakers": "ผู้ร่วมสนทนา",
        "said": "จำนวนรอบที่ร่วมสนทนา",
        "no_discussion": "ไม่มีบันทึกการสนทนาสำหรับการค้นคว้าครั้งนี้",
        "you": "คุณ",
        "turn": "รอบ",
        "turns": "รอบ",
        "made_with": "รวบรวมจากการค้นคว้าด้วย STORM",
    },
}


def _labels(lang):
    return LABELS.get(lang, LABELS["English"])


def _esc(text):
    return html.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# reading the run off disk
# ---------------------------------------------------------------------------


def _read_text(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _read_json(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return None


def _sources(url_to_info):
    """`url_to_info.json` keyed by citation number, in citation order.

    The file stores two halves — a url -> number map and a url -> record map —
    which is the wrong shape for anything that renders in citation order.
    """
    if not url_to_info:
        return {}
    index = url_to_info.get("url_to_unified_index", {})
    info = url_to_info.get("url_to_info", {})
    out = {}
    for url, number in index.items():
        record = info.get(url, {})
        out[int(number)] = {
            "url": url,
            "title": record.get("title") or url,
            "snippets": [s for s in record.get("snippets", []) if s],
            "query": (record.get("meta") or {}).get("query", ""),
        }
    return out


def _safe_url(url):
    """Only ever link out over http(s); anything else becomes plain text."""
    return url if re.match(r"https?://", url or "") else ""


def _site(url):
    match = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# the article
# ---------------------------------------------------------------------------

_LIST_LINE = re.compile(r"^\s*(?:[*+-]\s|\d+[.)]\s|>|\||#)")


def _paragraphs(lines):
    """STORM writes one paragraph per line with no blank line between them.

    Markdown reads that as a single paragraph with soft line breaks, which is
    why the article renders as three or four enormous blocks. Separating prose
    lines restores the paragraphing the writer intended, while consecutive list
    items are left alone so a bullet list stays one list.
    """
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.strip() and nxt.strip():
            if not _LIST_LINE.match(line) and not _LIST_LINE.match(nxt):
                out.append("")
    return out


def _blocks(article_text):
    """Split the article into `# heading` blocks, each with its `##` children."""
    lines = article_text.splitlines()
    blocks = []
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            current = {"title": stripped[2:].strip(), "lines": []}
            blocks.append(current)
            continue
        if current is None:
            # Prose before the first heading: STORM does not normally emit
            # any, but a truncated run can.
            current = {"title": "", "lines": []}
            blocks.append(current)
        current["lines"].append(line)
    return blocks


def _md(lines):
    """Markdown to HTML, with any raw HTML in the source neutralised.

    The article is written by a language model reading pages off the open web,
    and `markdown` passes embedded HTML straight through. A page that talks the
    model into emitting a `<script>` tag would otherwise get it executed in
    whoever opens this file. Escaping first costs nothing — STORM writes
    Markdown, not HTML — and the citation chips are added after the conversion,
    so they are unaffected.
    """
    text = html.escape("\n".join(_paragraphs(lines)), quote=False)
    return markdown.markdown(text, extensions=["tables", "sane_lists"])


_TAG = re.compile(r"(<[^>]+>)")
_CITE = re.compile(r"\[(\d+)\]")


def _link_citations(fragment, sources, seen):
    """Turn every `[7]` outside a tag into a chip that can open its source."""

    def one(match):
        number = int(match.group(1))
        seen.add(number)
        known = number in sources
        title = _esc(sources[number]["title"]) if known else ""
        return (
            f'<button type="button" class="cite" data-ref="{number}" '
            f'aria-label="{title}" title="{title}">{number}</button>'
            if known
            else f'<span class="cite cite--dead">{number}</span>'
        )

    parts = _TAG.split(fragment)
    for i, part in enumerate(parts):
        if not part.startswith("<"):
            parts[i] = _CITE.sub(one, part)
    return "".join(parts)


def _render_article(article_text, sources, labels):
    """Article body, table of contents, and which section cites which source."""
    blocks = _blocks(article_text)
    lead_html = ""
    body = []
    toc = []
    xref = {}
    counter = 0

    for block in blocks:
        title = block["title"]
        is_lead = not body and title.lower() in ("summary", "abstract", "บทสรุป")
        counter += 1
        anchor = f"s{counter}"
        seen = set()
        inner = _link_citations(_md(block["lines"]), sources, seen)
        label = labels["lead"] if is_lead else title
        for number in seen:
            xref.setdefault(number, []).append(label)

        if is_lead:
            lead_html = (
                f'<section class="lead" id="{anchor}">'
                f'<h2 class="lead__label">{_esc(labels["lead"])}</h2>'
                f'<div class="prose">{inner}</div></section>'
            )
        else:
            body.append(
                f'<section class="sect" id="{anchor}">'
                f'<h2>{_esc(title)}</h2>'
                f'<div class="prose">{inner}</div></section>'
            )
        toc.append({"id": anchor, "title": label})

    return lead_html, "\n".join(body), toc, xref


def _toc_html(toc, labels):
    items = []
    for entry in toc:
        items.append(
            f'<li><a href="#{entry["id"]}" data-toc="{entry["id"]}">'
            f'{_esc(entry["title"])}</a></li>'
        )
    # A disclosure rather than a plain list: ten sections stacked above the
    # article pushed the first paragraph off a phone screen entirely. It opens
    # on load at rail width and closes on a narrow one — see the script.
    return (
        f'<details class="tocwrap" open>'
        f'<summary class="rail__label">{_esc(labels["contents"])}</summary>'
        f'<nav class="toc" aria-label="{_esc(labels["contents"])}">'
        f'<ol>{"".join(items)}</ol></nav></details>'
    )


# ---------------------------------------------------------------------------
# the evidence
# ---------------------------------------------------------------------------


def _source_cards(sources, xref, counts, labels):
    if not sources:
        return f'<p class="empty">{_esc(labels["no_sources"])}</p>'
    cards = []
    for number in sorted(sources):
        source = sources[number]
        site = _site(source["url"])
        used = counts.get(number, 0)
        where = xref.get(number, [])
        href = _safe_url(source["url"])
        haystack = " ".join(
            [source["title"], site, source["query"], " ".join(where)]
        ).lower()

        badge = (
            f'<span class="pill pill--used">{_esc(labels["cited"])} '
            f'{used} {_esc(labels["times"])}</span>'
            if used
            else f'<span class="pill pill--unused">{_esc(labels["uncited"])}</span>'
        )
        query = (
            f'<p class="src__query"><span>{_esc(labels["found_by"])}</span> '
            f'<code>{_esc(source["query"])}</code></p>'
            if source["query"]
            else ""
        )
        where_html = (
            '<p class="src__where"><span>'
            + _esc(labels["cited_in"])
            + "</span> "
            + ", ".join(f"<em>{_esc(w)}</em>" for w in where)
            + "</p>"
            if where
            else ""
        )
        snippets = (
            "<details class='src__snips'><summary>"
            + _esc(labels["highlights"])
            + "</summary>"
            + "".join(f"<blockquote>{_esc(s)}</blockquote>" for s in source["snippets"])
            + "</details>"
            if source["snippets"]
            else ""
        )
        cards.append(
            f'<article class="src" id="src-{number}" data-num="{number}" '
            f'data-find="{_esc(haystack)}">'
            f'<div class="src__num">{number}</div>'
            f'<div class="src__body">'
            f'<h3 class="src__title">{_esc(source["title"])}</h3>'
            + (
                f'<a class="src__url" href="{_esc(href)}" target="_blank" '
                f'rel="noopener noreferrer">{_esc(site or source["url"])}</a>'
                if href
                else f'<p class="src__url">{_esc(source["url"])}</p>'
            )
            + f'<div class="src__meta">{badge}</div>'
            + f"{query}{where_html}{snippets}"
            + "</div></article>"
        )
    return f'<div class="srcs" id="srcs">{"".join(cards)}</div>'


# ---------------------------------------------------------------------------
# the interviews
# ---------------------------------------------------------------------------


# A run of asterisks opening a line: a bold marker the model started and never
# closed. Stripped here as well as when the run is saved, because a transcript
# written before that fix existed is still on disk and still opens in here.
_UNCLOSED_BOLD = re.compile(r"^\s*\*{2,}\s*", re.MULTILINE)


def _strip_unclosed_bold(text):
    return _UNCLOSED_BOLD.sub("", text or "").strip()


def _strip_citations(text):
    return (
        re.sub(r"\[\d+", "", re.sub(r" \[\d+", "", text or ""))
        .replace(" |", "")
        .replace("]", "")
    )


def _perspectives(conversation_log):
    """(name, description, turns) per perspective, the way the app parses it."""
    out = []
    for entry in conversation_log or []:
        raw = entry.get("perspective", "")
        if ": " in raw:
            name, description = raw.split(": ", 1)
        elif "- " in raw:
            name, description = raw.split("- ", 1)
        else:
            name, description = "", raw
        turns = [
            {
                "question": turn.get("user_utterance", ""),
                "answer": _strip_citations(turn.get("agent_utterance", "")),
            }
            for turn in entry.get("dlg_turns", [])
        ]
        out.append((name.strip() or description[:40], description.strip(), turns))
    return out


def _discussion(conversation, labels):
    """(speaker, description, utterance) per turn, in the order they were said.

    Co-STORM's transcript is one conversation with many speakers rather than
    STORM's set of separate interviews, so it keeps its order instead of being
    grouped: who answered whom is most of what a round table means.
    """
    out = []
    for turn in conversation or []:
        role = (turn.get("role") or "").strip()
        speaker = labels["you"] if role.lower() in ("guest", "you") else role
        out.append(
            (
                speaker or labels["you"],
                (turn.get("role_description") or "").strip(),
                _strip_unclosed_bold(
                    turn.get("utterance") or turn.get("raw_utterance")
                ),
            )
        )
    return out


def _discussion_html(discussion, sources, labels):
    """The round table, as a transcript with its citations still live.

    The citation numbers are kept rather than stripped, which the interviews
    do: Co-STORM numbers its sources once across the whole run, so the [7] an
    expert said is the [7] in the article and in the evidence tab.
    """
    if not discussion:
        return f'<p class="empty">{_esc(labels["no_discussion"])}</p>'
    rows = []
    seen = set()
    for speaker, description, utterance in discussion:
        note = (
            f'<span class="say__note">{_esc(description)}</span>' if description else ""
        )
        body = _link_citations(_esc(utterance), sources, seen)
        rows.append(
            f'<div class="say">'
            f'<div class="say__who">{_esc(speaker)}{note}</div>'
            f'<p class="say__what">{body}</p>'
            f"</div>"
        )
    return "".join(rows)


def _interviews_html(perspectives, labels):
    if not perspectives:
        return f'<p class="empty">{_esc(labels["no_interviews"])}</p>'
    tabs = []
    panels = []
    for i, (name, description, turns) in enumerate(perspectives):
        selected = "true" if i == 0 else "false"
        tabs.append(
            f'<button type="button" role="tab" class="ptab" id="ptab-{i}" '
            f'aria-selected="{selected}" aria-controls="ppanel-{i}" '
            f'tabindex="{0 if i == 0 else -1}">{_esc(name)}'
            f'<span class="ptab__n">{len(turns)} '
            f'{_esc(labels["turn"] if len(turns) == 1 else labels["turns"])}</span>'
            f"</button>"
        )
        rows = []
        for turn in turns:
            rows.append(
                f'<div class="turn">'
                f'<div class="turn__q"><span class="turn__tag">'
                f'{_esc(labels["asked"])}</span><p>{_esc(turn["question"])}</p></div>'
                f'<div class="turn__a"><span class="turn__tag">'
                f'{_esc(labels["answered"])}</span><p>{_esc(turn["answer"])}</p></div>'
                f"</div>"
            )
        panels.append(
            f'<div role="tabpanel" class="ppanel" id="ppanel-{i}" '
            f'aria-labelledby="ptab-{i}"{"" if i == 0 else " hidden"}>'
            f'<p class="persona">{_esc(description)}</p>'
            f'{"".join(rows)}</div>'
        )
    return (
        f'<div class="ptabs" role="tablist" aria-label="'
        f'{_esc(labels["perspectives"])}">{"".join(tabs)}</div>'
        f'{"".join(panels)}'
    )


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------

# A run is a stack of numbered evidence that a few interviewers argued into one
# article, so the numeral is the motif: a chip in the prose, a docket number on
# the evidence, a turn count on each interviewer. The page is warm paper rather
# than the app's cool slate — this file is read away from the product, and it
# should read as a document rather than a screenshot of one.
_CSS = r"""
:root {
  color-scheme: light;
  --paper: #fbfaf7;
  --sheet: #ffffff;
  --ink: #121a2b;
  --ink-soft: #5b6678;
  --line: #e6e2d9;
  --line-firm: #cfc9bc;
  --accent: #1d4ed8;
  --accent-soft: #e8eefc;
  --accent-ink: #ffffff;
  --flag: #b45309;
  --flag-soft: #fdf1e0;
  --quote: #f6f4ef;
  --shadow: 0 1px 2px rgba(18, 26, 43, .06), 0 12px 32px rgba(18, 26, 43, .07);
  --radius: 14px;
  --sans: "IBM Plex Sans Thai", "IBM Plex Sans", -apple-system, BlinkMacSystemFont,
          "Segoe UI", "Noto Sans Thai", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --paper: #0e1727;
    --sheet: #131e31;
    --ink: #e6ebf3;
    --ink-soft: #97a3b6;
    --line: #22304a;
    --line-firm: #33445f;
    --accent: #7fb0fb;
    --accent-soft: rgba(127, 176, 251, .15);
    --accent-ink: #0b1220;
    --flag: #f0b45f;
    --flag-soft: rgba(240, 180, 95, .14);
    --quote: #16223a;
    --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 14px 34px rgba(0, 0, 0, .45);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #0e1727;
  --sheet: #131e31;
  --ink: #e6ebf3;
  --ink-soft: #97a3b6;
  --line: #22304a;
  --line-firm: #33445f;
  --accent: #7fb0fb;
  --accent-soft: rgba(127, 176, 251, .15);
  --accent-ink: #0b1220;
  --flag: #f0b45f;
  --flag-soft: rgba(240, 180, 95, .14);
  --quote: #16223a;
  --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 14px 34px rgba(0, 0, 0, .45);
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 17px;
  line-height: 1.65;
  overflow-x: hidden;
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { animation: none !important; transition: none !important; }
}
a { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }

.wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px; }

/* ---- masthead ---- */
.mast { border-bottom: 1px solid var(--line); background: var(--paper); }
.mast__top {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 22px 0 6px;
}
.kicker {
  font-family: var(--mono); font-size: 11px; letter-spacing: .16em;
  text-transform: uppercase; color: var(--ink-soft);
}
.mast h1 {
  font-size: clamp(28px, 4.4vw, 46px); line-height: 1.15; margin: 6px 0 14px;
  letter-spacing: -.02em; font-weight: 600; max-width: 22ch;
}
.stats { display: flex; flex-wrap: wrap; gap: 0; margin: 0 0 20px; padding: 0; list-style: none; }
.stats li { padding: 0 20px 0 0; margin-right: 20px; border-right: 1px solid var(--line); }
.stats li:last-child { border-right: 0; }
.stats b {
  display: block; font-family: var(--mono); font-size: 22px; font-weight: 500;
  line-height: 1.2; font-variant-numeric: tabular-nums;
}
.stats span { font-size: 12px; color: var(--ink-soft); }

.ghost {
  border: 1px solid var(--line-firm); background: var(--sheet); color: var(--ink);
  border-radius: 999px; padding: 7px 14px; font: inherit; font-size: 13px;
  cursor: pointer; white-space: nowrap;
}
.ghost:hover { border-color: var(--accent); color: var(--accent); }

/* ---- view switcher ---- */
.views { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; }
.views::-webkit-scrollbar { display: none; }
.view-btn {
  appearance: none; background: none; border: 0; border-bottom: 2px solid transparent;
  color: var(--ink-soft); font: inherit; font-size: 14px; padding: 10px 14px;
  cursor: pointer; white-space: nowrap;
}
.view-btn[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--accent); font-weight: 600; }
.view-btn .n { font-family: var(--mono); font-size: 12px; color: var(--ink-soft); margin-left: 6px; }

main { padding: 34px 0 80px; }
.view[hidden] { display: none; }

/* ---- article ---- */
.cols { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 44px; align-items: start; }
.rail { position: sticky; top: 20px; max-height: calc(100vh - 40px); overflow-y: auto; }
.rail__label {
  font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--ink-soft); margin: 0 0 10px; font-weight: 500; cursor: default;
  list-style: none;
}
.rail__label::-webkit-details-marker { display: none; }
.toc ol { list-style: none; margin: 0; padding: 0; counter-reset: toc; }
.toc a {
  display: block; padding: 5px 0 5px 22px; font-size: 14px; line-height: 1.4;
  color: var(--ink-soft); text-decoration: none; border-left: 2px solid var(--line);
  position: relative; counter-increment: toc;
}
.toc a::before {
  content: counter(toc); position: absolute; left: 8px; font-family: var(--mono);
  font-size: 11px; opacity: .6;
}
.toc a:hover { color: var(--ink); }
.toc a.on { color: var(--ink); border-left-color: var(--accent); font-weight: 600; }

.sheet {
  background: var(--sheet); border: 1px solid var(--line); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: clamp(22px, 4vw, 52px);
}
.lead { border-left: 3px solid var(--accent); padding-left: 20px; margin-bottom: 34px; }
.lead__label {
  font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--accent); margin: 0 0 8px; font-weight: 500;
}
.lead .prose p { font-size: 18px; }
.sect { scroll-margin-top: 24px; }
.sect + .sect { margin-top: 40px; padding-top: 34px; border-top: 1px solid var(--line); }
.sect > h2 { font-size: 25px; letter-spacing: -.015em; margin: 0 0 14px; font-weight: 600; }
.prose h2 { font-size: 18px; margin: 28px 0 8px; font-weight: 600; }
.prose h3 { font-size: 16px; margin: 22px 0 6px; font-weight: 600; color: var(--ink-soft); }
.prose p { margin: 0 0 14px; }
.prose ul, .prose ol { margin: 0 0 16px; padding-left: 22px; }
.prose li { margin-bottom: 7px; }
.prose code { font-family: var(--mono); font-size: .88em; background: var(--quote); padding: 1px 5px; border-radius: 4px; }
.prose table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 15px; }
.prose th, .prose td { border: 1px solid var(--line); padding: 7px 10px; text-align: left; }
.tablewrap { overflow-x: auto; }

.cite {
  appearance: none; font-family: var(--mono); font-size: 11px; font-weight: 500;
  line-height: 1; vertical-align: 2px; margin: 0 1px; padding: 2px 5px;
  border: 1px solid var(--line-firm); border-radius: 5px;
  background: var(--sheet); color: var(--accent); cursor: pointer;
}
.cite:hover, .cite.on { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.cite--dead { color: var(--ink-soft); cursor: default; }

/* ---- citation peek ---- */
.peek {
  position: fixed; z-index: 40; width: min(380px, calc(100vw - 32px));
  background: var(--sheet); border: 1px solid var(--line-firm); border-radius: 12px;
  box-shadow: var(--shadow); padding: 16px 18px;
}
.peek[hidden] { display: none; }
.peek__num { font-family: var(--mono); font-size: 11px; color: var(--ink-soft); }
.peek__title { font-size: 15px; font-weight: 600; margin: 4px 0 6px; line-height: 1.35; }
.peek__url { font-size: 13px; word-break: break-word; }
.peek__snip {
  font-size: 14px; color: var(--ink-soft); margin: 10px 0 12px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
}
.peek__acts { display: flex; gap: 8px; }
.peek__acts .ghost { font-size: 12px; padding: 5px 11px; }

/* ---- evidence ---- */
.tools { display: flex; gap: 12px; align-items: center; margin-bottom: 22px; flex-wrap: wrap; }
.tools input {
  flex: 1 1 260px; min-width: 0; font: inherit; font-size: 15px; padding: 10px 14px;
  border: 1px solid var(--line-firm); border-radius: 999px;
  background: var(--sheet); color: var(--ink);
}
.srcs { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.src {
  display: flex; gap: 14px; background: var(--sheet); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 18px; scroll-margin-top: 90px;
}
.src[hidden] { display: none; }
.src.flash { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.src__num {
  font-family: var(--mono); font-size: 20px; font-weight: 500; color: var(--ink-soft);
  line-height: 1; padding-top: 2px; font-variant-numeric: tabular-nums;
}
.src__body { min-width: 0; flex: 1; }
.src__title { font-size: 15px; font-weight: 600; margin: 0 0 5px; line-height: 1.4; }
.src__url { font-size: 13px; word-break: break-word; }
.src__meta { margin: 10px 0 8px; }
.pill {
  display: inline-block; font-family: var(--mono); font-size: 11px;
  padding: 3px 9px; border-radius: 999px;
}
.pill--used { background: var(--accent-soft); color: var(--accent); }
.pill--unused { background: var(--flag-soft); color: var(--flag); }
.src__query, .src__where { font-size: 13px; color: var(--ink-soft); margin: 0 0 6px; }
.src__query span, .src__where span { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
.src__query code { font-family: var(--mono); font-size: 12px; }
.src__where em { font-style: normal; color: var(--ink); }
.src__snips { margin-top: 10px; }
.src__snips summary { font-size: 13px; color: var(--accent); cursor: pointer; }
.src__snips blockquote {
  margin: 10px 0 0; padding: 10px 14px; background: var(--quote);
  border-left: 2px solid var(--line-firm); border-radius: 0 8px 8px 0;
  font-size: 14px; color: var(--ink-soft);
}

/* ---- interviews ---- */
.ptabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 22px; }
.ptab {
  background: var(--sheet); border: 1px solid var(--line); border-radius: 999px;
  padding: 8px 16px; font: inherit; font-size: 14px; color: var(--ink-soft); cursor: pointer;
}
.ptab[aria-selected="true"] { border-color: var(--accent); color: var(--ink); font-weight: 600; }
.ptab__n { font-family: var(--mono); font-size: 11px; margin-left: 8px; opacity: .75; }
.persona {
  background: var(--accent-soft); border-radius: var(--radius); padding: 14px 18px;
  font-size: 15px; margin: 0 0 22px;
}
.turn {
  background: var(--sheet); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 18px 20px; margin-bottom: 14px;
}
.turn__tag {
  display: block; font-family: var(--mono); font-size: 10px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ink-soft); margin-bottom: 5px;
}
.say {
  border-top: 1px solid var(--rule);
  padding: 1.1rem 0;
}
.say:first-child { border-top: 0; }
.say__who {
  font-weight: 600;
  font-size: .93rem;
  margin-bottom: .35rem;
}
.say__note {
  display: block;
  font-weight: 400;
  font-size: .82rem;
  color: var(--dim);
  margin-top: .15rem;
}
.say__what { margin: 0; }
.turn__q p { margin: 0 0 16px; font-weight: 600; font-size: 16px; }
.turn__a p { margin: 0; color: var(--ink-soft); font-size: 15px; }
.empty { color: var(--ink-soft); }

.foot {
  border-top: 1px solid var(--line); padding: 22px 0 40px;
  font-size: 13px; color: var(--ink-soft);
  display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
}

@media (max-width: 940px) {
  .cols { grid-template-columns: minmax(0, 1fr); gap: 22px; }
  .rail { position: static; max-height: none; }
  .toc ol { display: flex; flex-wrap: wrap; gap: 6px; }
  .toc a { border-left: 0; border: 1px solid var(--line); border-radius: 999px; padding: 5px 12px 5px 26px; }
  .toc a::before { left: 11px; }
  .rail__label { cursor: pointer; color: var(--ink); }
  .rail__label::after { content: " ▾"; }
  .tocwrap[open] > .rail__label::after { content: " ▴"; }
}
@media print {
  .views, .tools, .ghost, .rail, .peek { display: none !important; }
  body { background: #fff; font-size: 11pt; }
  .view[hidden] { display: block !important; }
  .cols { display: block; }
  .sheet, .src, .turn { border: 0; box-shadow: none; padding: 0; }
  .src { break-inside: avoid; margin-bottom: 12pt; }
  .src__snips { display: none; }
}
"""

_JS = r"""
(function () {
  var root = document.documentElement;
  var KEY = "storm-report-theme";
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) {}

  var themeBtn = document.getElementById("theme");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var now = root.getAttribute("data-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next = now ? (now === "dark" ? "light" : "dark") : (prefersDark ? "light" : "dark");
    root.setAttribute("data-theme", next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
  });

  // ---- views -------------------------------------------------------
  var buttons = [].slice.call(document.querySelectorAll(".view-btn"));
  function show(name, focus) {
    buttons.forEach(function (b) {
      var on = b.dataset.view === name;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    });
    [].forEach.call(document.querySelectorAll(".view"), function (v) {
      v.hidden = v.dataset.view !== name;
    });
  }
  buttons.forEach(function (b, i) {
    b.addEventListener("click", function () { show(b.dataset.view); });
    b.addEventListener("keydown", function (e) {
      var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      var next = buttons[(i + step + buttons.length) % buttons.length];
      show(next.dataset.view, true);
    });
  });

  // ---- table of contents -------------------------------------------
  var tocwrap = document.querySelector(".tocwrap");
  if (tocwrap && window.matchMedia("(max-width: 940px)").matches) tocwrap.open = false;
  var links = [].slice.call(document.querySelectorAll("[data-toc]"));
  var sections = links.map(function (a) { return document.getElementById(a.dataset.toc); })
                      .filter(Boolean);
  // Measured on scroll rather than with an IntersectionObserver: the observer
  // never fires in some embedded and headless viewers, which left the contents
  // with nothing marked at all.
  if (sections.length) {
    var ticking = false;
    var mark = function () {
      ticking = false;
      var line = window.innerHeight * 0.25;
      var active = sections[0];
      sections.forEach(function (s) {
        if (s.getBoundingClientRect().top <= line) active = s;
      });
      links.forEach(function (a) {
        a.classList.toggle("on", a.dataset.toc === active.id);
      });
    };
    var queue = function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(mark);
    };
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    mark();
  }

  links.forEach(function (a) {
    a.addEventListener("click", function () {
      if (tocwrap && window.matchMedia("(max-width: 940px)").matches) tocwrap.open = false;
    });
  });

  // ---- citation peek -----------------------------------------------
  var peek = document.getElementById("peek");
  var opener = null;
  function closePeek(restore) {
    if (!peek || peek.hidden) return;
    peek.hidden = true;
    if (opener) opener.classList.remove("on");
    if (restore && opener) opener.focus();
    opener = null;
  }
  function openPeek(chip) {
    var num = chip.dataset.ref;
    var card = document.getElementById("src-" + num);
    if (!peek || !card) return;
    closePeek(false);
    opener = chip;
    chip.classList.add("on");
    var title = card.querySelector(".src__title").textContent;
    var link = card.querySelector(".src__url");
    var quote = card.querySelector("blockquote");
    peek.querySelector(".peek__num").textContent = "[" + num + "]";
    peek.querySelector(".peek__title").textContent = title;
    var a = peek.querySelector(".peek__url");
    a.textContent = link.textContent;
    a.href = link.href;
    peek.querySelector(".peek__snip").textContent = quote ? quote.textContent : "";
    peek.dataset.ref = num;
    peek.hidden = false;
    var box = chip.getBoundingClientRect();
    var w = peek.offsetWidth, h = peek.offsetHeight;
    var left = Math.min(Math.max(12, box.left - w / 2 + box.width / 2), window.innerWidth - w - 12);
    var top = box.bottom + 10;
    if (top + h > window.innerHeight - 12) top = Math.max(12, box.top - h - 10);
    peek.style.left = left + "px";
    peek.style.top = top + "px";
    peek.querySelector(".peek__go").focus();
  }
  document.addEventListener("click", function (e) {
    var chip = e.target.closest ? e.target.closest("button.cite") : null;
    if (chip) { openPeek(chip); return; }
    if (peek && !peek.hidden && !e.target.closest("#peek")) closePeek(false);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closePeek(true); });
  window.addEventListener("resize", function () { closePeek(false); });
  var go = peek && peek.querySelector(".peek__go");
  if (go) go.addEventListener("click", function () {
    var num = peek.dataset.ref;
    closePeek(false);
    show("evidence");
    var card = document.getElementById("src-" + num);
    if (!card) return;
    var input = document.getElementById("filter");
    if (input && input.value) { input.value = ""; input.dispatchEvent(new Event("input")); }
    card.scrollIntoView({ block: "center" });
    card.classList.add("flash");
    setTimeout(function () { card.classList.remove("flash"); }, 1600);
  });

  // ---- evidence filter ----------------------------------------------
  var filter = document.getElementById("filter");
  var cards = [].slice.call(document.querySelectorAll(".src"));
  var none = document.getElementById("nomatch");
  if (filter) filter.addEventListener("input", function () {
    var q = filter.value.trim().toLowerCase();
    var hits = 0;
    cards.forEach(function (card) {
      var hit = !q || card.dataset.find.indexOf(q) !== -1;
      card.hidden = !hit;
      if (hit) hits++;
    });
    if (none) none.hidden = hits !== 0;
  });

  // ---- interview tabs ------------------------------------------------
  var ptabs = [].slice.call(document.querySelectorAll(".ptab"));
  function pick(i, focus) {
    ptabs.forEach(function (t, j) {
      t.setAttribute("aria-selected", i === j ? "true" : "false");
      t.tabIndex = i === j ? 0 : -1;
      document.getElementById("ppanel-" + j).hidden = i !== j;
    });
    if (focus) ptabs[i].focus();
  }
  ptabs.forEach(function (tab, i) {
    tab.addEventListener("click", function () { pick(i); });
    tab.addEventListener("keydown", function (e) {
      var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      pick((i + step + ptabs.length) % ptabs.length, true);
    });
  });

  // Wide tables get their own scroller rather than pushing the page sideways.
  [].forEach.call(document.querySelectorAll(".prose table"), function (table) {
    var box = document.createElement("div");
    box.className = "tablewrap";
    table.parentNode.insertBefore(box, table);
    box.appendChild(table);
  });
})();
"""


def _measure(text):
    """(count, unit) for the article's length.

    Mirrors `ui_theme.measure_length`: Thai and CJK do not space their words,
    so whitespace splitting would report a paragraph as a handful of words.
    Kept here rather than imported because this module stays free of Streamlit.
    """
    unspaced = sum(
        1
        for char in text
        if "฀" <= char <= "๿"
        or "一" <= char <= "鿿"
        or "぀" <= char <= "ヿ"
    )
    if unspaced > len(text) * 0.2:
        return unspaced, "chars"
    return len(text.split()), "words"


def _stat(value, label):
    return f"<li><b>{value:,}</b><span>{_esc(label)}</span></li>"


def report_filename(article_name):
    return f"{article_name}.report.html"


def build_report(article_name, file_path_dict, lang="English"):
    """Compile one finished run into a single self-contained HTML document.

    `file_path_dict` is the per-article mapping the demo already builds with
    `DemoFileIOHelper.read_structure_to_dict`, so the caller passes what it
    already has. `run_config.json` is deliberately never read: it stores the
    API key the run was made with, and this file is meant to be shared.
    """
    labels = _labels(lang)
    article_path = file_path_dict.get(
        "storm_gen_article_polished.txt"
    ) or file_path_dict.get("storm_gen_article.txt")
    article_text = _read_text(article_path)
    if not article_text:
        raise ValueError(f"no article text for {article_name!r}")

    # The demo drops the prompt echo the same way before rendering.
    marker = "Write the lead section:"
    if marker in article_text:
        article_text = article_text[article_text.find(marker) + len(marker) :]
    article_text = re.compile(r']:\s+"(.*?)"\s+http').sub("]: http", article_text)

    sources = _sources(_read_json(file_path_dict.get("url_to_info.json")))

    # Two shapes of transcript, because there are two engines behind these
    # files. STORM leaves separate interviews, one per perspective; Co-STORM
    # leaves one round table with several speakers. Neither can be rendered
    # as the other without lying about who said what.
    perspectives = _perspectives(_read_json(file_path_dict.get("conversation_log.json")))
    discussion = _discussion(
        _read_json(file_path_dict.get("costorm_conversation.json")), labels
    )

    counts = {}
    for number in (int(m) for m in _CITE.findall(article_text)):
        counts[number] = counts.get(number, 0) + 1

    lead_html, body_html, toc, xref = _render_article(article_text, sources, labels)

    plain = re.sub(
        r"\[\d+\]",
        "",
        "\n".join(
            line for line in article_text.splitlines() if not line.strip().startswith("#")
        ),
    )
    count, unit = _measure(plain)
    questions = sum(len(turns) for _, _, turns in perspectives)
    speakers = len({speaker for speaker, _, _ in discussion})

    title = article_name.replace("_", " ")
    when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if article_path and os.path.exists(article_path):
        when = datetime.datetime.fromtimestamp(
            os.path.getmtime(article_path)
        ).strftime("%Y-%m-%d %H:%M")

    stats = "".join(
        [
            _stat(len(toc), labels["sections"]),
            _stat(count, labels[unit] if unit in labels else labels["words"]),
            _stat(len(sources), labels["sources"]),
        ]
        + (
            [
                _stat(speakers, labels["speakers"]),
                _stat(len(discussion), labels["said"]),
            ]
            if discussion
            else [
                _stat(len(perspectives), labels["perspectives"]),
                _stat(questions, labels["questions"]),
            ]
        )
    )

    def tab(name, label, n):
        selected = "true" if name == "article" else "false"
        return (
            f'<button type="button" class="view-btn" role="tab" data-view="{name}" '
            f'id="vtab-{name}" aria-controls="vpanel-{name}" '
            f'aria-selected="{selected}" tabindex="{0 if name == "article" else -1}">'
            f'{_esc(label)}'
            + (f'<span class="n">{n}</span>' if n else "")
            + "</button>"
        )

    talk_label = labels["discussion"] if discussion else labels["interviews"]
    talk_count = len(discussion) if discussion else len(perspectives)
    talk_html = (
        _discussion_html(discussion, sources, labels)
        if discussion
        else _interviews_html(perspectives, labels)
    )
    switcher = (
        tab("article", labels["article"], "")
        + tab("evidence", labels["evidence"], len(sources))
        + tab("interviews", talk_label, talk_count)
    )

    lang_attr = "th" if lang == "ไทย" else "en"
    return f"""<!doctype html>
<html lang="{lang_attr}" data-theme="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="generator" content="STORM interactive report">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Thai:wght@400;500;600&display=swap">
<style>{_CSS}</style>
</head>
<body>
<header class="mast">
  <div class="wrap">
    <div class="mast__top">
      <p class="kicker">{_esc(labels["made_with"])} · {_esc(labels["generated"])} {when}</p>
      <button type="button" class="ghost" id="theme">{_esc(labels["theme"])}</button>
    </div>
    <h1>{_esc(title)}</h1>
    <ul class="stats">{stats}</ul>
    <div class="views" role="tablist" aria-label="{_esc(labels["views"])}">{switcher}</div>
  </div>
</header>

<main class="wrap">
  <div class="view" data-view="article" role="tabpanel" id="vpanel-article" aria-labelledby="vtab-article">
    <div class="cols">
      <aside class="rail">{_toc_html(toc, labels)}</aside>
      <div class="sheet">{lead_html}{body_html}</div>
    </div>
  </div>

  <div class="view" data-view="evidence" role="tabpanel" id="vpanel-evidence" aria-labelledby="vtab-evidence" hidden>
    <div class="tools">
      <input type="search" id="filter" placeholder="{_esc(labels["filter_sources"])}"
             aria-label="{_esc(labels["filter_sources"])}">
    </div>
    <p class="empty" id="nomatch" hidden>{_esc(labels["no_match"])}</p>
    {_source_cards(sources, xref, counts, labels)}
  </div>

  <div class="view" data-view="interviews" role="tabpanel" id="vpanel-interviews" aria-labelledby="vtab-interviews" hidden>
    {talk_html}
  </div>
</main>

<div class="peek" id="peek" role="dialog" aria-modal="false" hidden>
  <p class="peek__num"></p>
  <p class="peek__title"></p>
  <a class="peek__url" href="#" target="_blank" rel="noopener noreferrer"></a>
  <p class="peek__snip"></p>
  <div class="peek__acts">
    <button type="button" class="ghost peek__go">{_esc(labels["see_evidence"])}</button>
  </div>
</div>

<footer class="foot wrap">
  <span>{_esc(title)}</span>
  <span>{_esc(labels["made_with"])}</span>
</footer>
<script>{_JS}</script>
</body>
</html>
"""
