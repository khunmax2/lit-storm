"""The report as Brief + Canvas: what it found at a glance, then the text
with its sources beside it (docs/design/report-directions, direction E).

At the top, a grid of tiles: the overview, the key figures the model drew
and litstorm.visuals checked (or plain counts when there are none), the
first chart, the sources. Below, the article, and a panel that follows the
reader: the sources the section in view cites, the one whose number was
pressed lit, with its passages.

One file, offline, as the interactive page: the web app's faces inside it,
charts drawn to SVG beforehand, our script alone allowed to run
(render/interactive.py shares its blocks, charts and policy with this).
"""

import html
import json
import re

from litstorm import report as report_mod
from litstorm import visuals as visuals_mod
from litstorm.render import html as page_mod
from litstorm.render import interactive

LABELS = {
    "th": {
        "summary": "สรุปใน 30 วินาที",
        "sources": "แหล่งอ้างอิง",
        "with_evidence": "มีข้อความหลักฐาน {n} แหล่ง",
        "sections": "หัวข้อ",
        "read": "อ่านราว {n} นาที",
        "verified": "ตรวจหลักฐานแล้ว",
        "in_section": "แหล่งที่อ้างในส่วนนี้",
        "none_here": "ส่วนนี้ไม่ได้อ้างแหล่งใด",
        "open": "เปิดต้นทาง",
        "chart": "กราฟ",
        "contents": "สารบัญ",
        "most_cited": "แหล่งที่ถูกอ้างบ่อย",
        "figures_note": "ตัวเลขทุกตัวตรวจกับข้อความต้นทางแล้ว",
        "passages": "ข้อความหลักฐาน",
        "map": "แผนผังความรู้",
        "map_hint": "กดหัวข้อเพื่อดูสรุป · สีเข้มคือมีแหล่งรองรับมาก",
        "main": "ประเด็นหลัก",
        "sub": "หัวข้อย่อย",
        "n_sources": "{n} แหล่ง",
        "n_subs": "{n} หัวข้อย่อย",
        "n_figs": "{n} ภาพประกอบ",
        "more_subs": "+{n} หัวข้อย่อย",
        "read_this": "อ่านส่วนนี้",
        "backed_by": "แหล่งที่รองรับ",
        "cite_hint": "คลิกเพื่อดูข้อความหลักฐาน",
        "evidence_by_section": "แหล่งที่รองรับแต่ละประเด็น",
        "overview": "ภาพรวม",
        "theme": "สว่าง/มืด",
        "strongest": "ประเด็นที่หลักฐานแน่นที่สุด",
        "main_source": "แหล่งที่อ้างมากที่สุด",
        "cited_n": "อ้าง {n} ครั้ง",
        "print": "พิมพ์",
    },
    "en": {
        "summary": "In 30 seconds",
        "sources": "Sources",
        "with_evidence": "{n} with evidence",
        "sections": "Sections",
        "read": "{n} min read",
        "verified": "evidence checked",
        "in_section": "Cited in this part",
        "none_here": "This part cites no source",
        "open": "Open the original",
        "chart": "Chart",
        "contents": "Contents",
        "most_cited": "Sources cited most",
        "figures_note": "Every number was checked against its source passage",
        "passages": "Evidence",
        "map": "Knowledge map",
        "map_hint": "Press a topic for its gist · deeper colour, more sources behind it",
        "main": "Main theme",
        "sub": "Subtopic",
        "n_sources": "{n} sources",
        "n_subs": "{n} subtopics",
        "n_figs": "{n} figures",
        "more_subs": "+{n} subtopics",
        "read_this": "Read this part",
        "backed_by": "Backed by",
        "cite_hint": "Click for the evidence",
        "evidence_by_section": "Sources behind each theme",
        "overview": "Overview",
        "theme": "Light/dark",
        "strongest": "Best-supported theme",
        "main_source": "Most-cited source",
        "cited_n": "cited {n} times",
        "print": "Print",
    },
}

E = html.escape

CSS = """
:root {
  --bg: #eef3fb; --ink: #14213d; --body: #22304f; --muted: #5b6886; --line: rgb(30 58 138 / .12);
  --card: rgb(255 255 255 / .8); --soft: #f2f6fd; --brand: #2563eb; --brand-soft: rgb(37 99 235 / .1);
  --navy: #1e3a8a; --good: #0f9f6e; --warm: #b45309; --navy-ink: #1e3a8a; --on-brand: #fff;
  --surface: #fff; --paper: rgb(255 255 255 / .9); --chip: rgb(255 255 255 / .85); --glass: rgb(255 255 255 / .72);
  --glass-2: rgb(255 255 255 / .55); --glass-3: rgb(255 255 255 / .82); --shine: rgb(255 255 255 / .8);
  --shadow: rgb(30 58 138 / .45); --dots: rgb(30 58 138 / .12); --track: #e3eaf7;
  --wash-1: #e2dcff; --wash-2: #d6e9ff;
  --heat-0: #dbe5f6; --heat-1: #93b4f0; --heat-2: #4f86ee; --heat-3: #1d4ed8;
  --sans: "LS Latin", "LS Thai", "IBM Plex Sans Thai", "Noto Sans Thai", system-ui, sans-serif;
  --serif: "LS Serif Latin", "LS Serif Thai", "Noto Serif Thai", Georgia, serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #0b1220; --ink: #e8eefb; --body: #cad4e8; --muted: #8f9bb5; --line: rgb(148 170 220 / .16); --card: rgb(19 28 48 / .78); --soft: rgb(148 170 220 / .08); --brand: #6ea0ff; --brand-soft: rgb(110 160 255 / .16); --navy: #2b4db8; --good: #34d399; --warm: #f5a524; --navy-ink: #c7d7fe; --on-brand: #0b1220; --surface: #141d31; --paper: rgb(16 24 41 / .92); --chip: rgb(19 28 48 / .85); --glass: rgb(19 28 48 / .7); --glass-2: rgb(14 21 37 / .6); --glass-3: rgb(16 24 41 / .88); --shine: rgb(255 255 255 / .04); --shadow: rgb(0 0 0 / .6); --dots: rgb(148 170 220 / .1); --track: #1f2b45; --wash-1: #241d4d; --wash-2: #0f2546; --heat-0: #24334f; --heat-1: #34589f; --heat-2: #4f86ee; --heat-3: #9cbcff; color-scheme: dark; } }
:root[data-theme="dark"] { --bg: #0b1220; --ink: #e8eefb; --body: #cad4e8; --muted: #8f9bb5; --line: rgb(148 170 220 / .16); --card: rgb(19 28 48 / .78); --soft: rgb(148 170 220 / .08); --brand: #6ea0ff; --brand-soft: rgb(110 160 255 / .16); --navy: #2b4db8; --good: #34d399; --warm: #f5a524; --navy-ink: #c7d7fe; --on-brand: #0b1220; --surface: #141d31; --paper: rgb(16 24 41 / .92); --chip: rgb(19 28 48 / .85); --glass: rgb(19 28 48 / .7); --glass-2: rgb(14 21 37 / .6); --glass-3: rgb(16 24 41 / .88); --shine: rgb(255 255 255 / .04); --shadow: rgb(0 0 0 / .6); --dots: rgb(148 170 220 / .1); --track: #1f2b45; --wash-1: #241d4d; --wash-2: #0f2546; --heat-0: #24334f; --heat-1: #34589f; --heat-2: #4f86ee; --heat-3: #9cbcff; color-scheme: dark; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; color: var(--ink); font-family: var(--sans); -webkit-font-smoothing: antialiased;
  background: radial-gradient(70rem 36rem at 92% -5%, var(--wash-1) 0%, transparent 60%),
              radial-gradient(60rem 40rem at -5% 30%, var(--wash-2) 0%, transparent 60%), var(--bg); background-attachment: fixed; }
a { color: var(--brand); }
.wrap { max-width: 82rem; margin: 0 auto; padding: 2.2rem 2.4rem 4rem; }
.top { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .6rem; }
.chips { display: flex; flex-wrap: wrap; gap: .4rem; }
.tools { display: flex; gap: .35rem; }
.tools button { font: inherit; font-size: .75rem; color: var(--muted); background: var(--chip); border: 1px solid var(--line);
  border-radius: 999px; padding: .3rem .75rem; cursor: pointer; transition: color .15s, border-color .15s, background-color .15s; }
.tools button:hover { color: var(--brand); border-color: var(--brand); }
.chips span { font-size: .8rem; padding: .3rem .75rem; border-radius: 999px; background: var(--chip);
  border: 1px solid var(--line); color: var(--muted); }
.chips span.mode { background: var(--navy); border-color: var(--navy); color: #fff; }
h1 { font-family: var(--serif); font-weight: 400; font-size: clamp(2.3rem, 4.6vw, 3.6rem); line-height: 1.15;
  letter-spacing: -.01em; margin: .9rem 0 1.4rem; text-wrap: balance; }

/* The brief: tiles of what the report found. */
.bento { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .9rem; }
.tile { background: var(--card); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--line); border-radius: 1.4rem; padding: 1.2rem 1.35rem;
  box-shadow: 0 14px 34px -24px var(--shadow), inset 0 1px 0 var(--shine);
  transition: transform .25s ease-out, box-shadow .25s ease-out; min-width: 0; }
.tile:hover { transform: translateY(-2px); box-shadow: 0 22px 44px -26px var(--shadow), inset 0 1px 0 var(--shine); }
.tile .lbl { font-size: .7rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.tile.sum { grid-column: span 2; grid-row: span 2; display: flex; flex-direction: column; }
.toc { margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--line); }
.toc ol { list-style: none; margin: .55rem 0 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .35rem .9rem; }
.toc a { display: flex; gap: .55rem; align-items: baseline; color: var(--ink); text-decoration: none; font-size: .88rem; line-height: 1.45;
  padding: .3rem .45rem; margin: 0 -.45rem; border-radius: .55rem; transition: background-color .15s, color .15s; }
.toc a:hover { background: var(--brand-soft); color: var(--navy); }
.toc .n { flex: none; font-size: .75rem; font-weight: 600; color: var(--brand); font-variant-numeric: tabular-nums; }
.tile.sum p { font-size: 1rem; line-height: 1.85; color: var(--body); margin: .6rem 0 0; }
.tile .big { font-size: 2.6rem; font-weight: 600; letter-spacing: -.02em; line-height: 1.05; margin-top: .55rem;
  font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.tile .big.mid { font-size: 1.7rem; }
.tile .big small { font-size: .95rem; font-weight: 500; color: var(--muted); margin-left: .25rem; }
.tile .txt { display: block; margin-top: .55rem; font-size: 1.05rem; font-weight: 600; line-height: 1.45; color: var(--ink);
  text-decoration: none; text-wrap: balance; }
.tile .txt:hover { color: var(--brand); }
.tile .sub { font-size: .82rem; line-height: 1.55; color: var(--muted); margin-top: .45rem; }
.tile.c1 .big { color: var(--brand); } .tile.c2 .big { color: var(--good); } .tile.c3 .big { color: var(--warm); }
.tile.chart { grid-column: span 2; grid-row: span 2; }
.tile.chart .t { font-weight: 600; margin: .35rem 0 .6rem; line-height: 1.45; }
.tile.chart svg { display: block; width: 100%; height: auto; }
.ring { float: right; margin-top: -.2rem; }
.note { margin: .9rem 0 0; font-size: .78rem; color: var(--muted); }
.note::before { content: "◆ "; color: var(--brand); font-size: .65rem; }

/* The map: the report's themes and what backs each, one press from its gist. */
.kmap { margin-top: 1.6rem; background: var(--glass-2); border: 1px solid var(--line); border-radius: 1.4rem;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); overflow: hidden;
  box-shadow: 0 14px 34px -26px var(--shadow); }
.kmap-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: .4rem 1rem; padding: 1.1rem 1.4rem 0; }
.kmap-head .hint { margin: 0; font-size: .78rem; color: var(--muted); }
.kmap-body { display: grid; grid-template-columns: minmax(0, 1fr) 21rem; }
.kmap-canvas { position: relative; overflow-x: auto; padding: 1.4rem 1.4rem 1.6rem;
  background-image: radial-gradient(var(--dots) 1px, transparent 1px); background-size: 18px 18px; }
.kmap-lines { position: absolute; left: 0; top: 0; pointer-events: none; overflow: visible; }
.kmap-lines path { fill: none; stroke: rgb(37 99 235 / .32); stroke-width: 1.6; transition: stroke .2s, stroke-width .2s, stroke-dashoffset .9s ease-out; }
.kmap-lines path.on { stroke: var(--brand); stroke-width: 2.2; }
.km-tree { display: flex; align-items: center; gap: 3.2rem; min-width: max-content; }
.km-branches { display: flex; flex-direction: column; gap: 1.1rem; }
.km-br { display: flex; align-items: center; gap: 2.6rem; }
.km-kids { display: flex; flex-direction: column; gap: .45rem; }
.km-node { position: relative; display: block; text-align: left; font: inherit; color: var(--ink); cursor: pointer;
  background: var(--surface); border: 1px solid var(--line); border-radius: .95rem; padding: .6rem .8rem .6rem .95rem;
  box-shadow: 0 8px 20px -18px var(--shadow); transition: transform .2s ease-out, box-shadow .2s, border-color .2s, opacity .45s ease-out; }
.km-node::before { content: ""; position: absolute; left: 0; top: .55rem; bottom: .55rem; width: 3px; border-radius: 3px; background: var(--heat); }
.km-node:hover { transform: translateY(-1px); border-color: rgb(37 99 235 / .45); }
.km-node:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.km-node.on { border-color: var(--brand); box-shadow: 0 0 0 4px rgb(37 99 235 / .14), 0 12px 26px -18px var(--shadow); }
.km-node .k { display: block; font-size: .64rem; font-weight: 600; letter-spacing: .06em; color: var(--muted); }
.km-node .hd { display: block; font-weight: 600; line-height: 1.45; margin-top: .15rem; }
.km-node .mt { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; font-size: .7rem; color: var(--muted); }
.km-node .mt span { padding: .05rem .45rem; border-radius: 999px; background: var(--soft); }
.km-node.root { width: 13rem; background: var(--navy); border-color: var(--navy); color: #fff; padding: 1rem 1.1rem; }
.km-node.root::before { display: none; }
.km-node.root .hd { font-family: var(--serif); font-weight: 400; font-size: 1.15rem; }
.km-node.root .k, .km-node.root .mt { color: rgb(255 255 255 / .75); }
.km-node.root .mt span { background: rgb(255 255 255 / .14); }
.km-node.l1 { width: 15rem; }
.km-node.l1 .hd { font-size: .95rem; }
.km-node.l2 { width: 17rem; padding-top: .45rem; padding-bottom: .45rem; }
.km-node.l2 .hd { font-weight: 500; font-size: .84rem; }
.km-node.l2 .mt { margin-top: .25rem; }
.h0 { --heat: var(--heat-0); } .h1 { --heat: var(--heat-1); } .h2 { --heat: var(--heat-2); } .h3 { --heat: var(--heat-3); }
.kmap-detail { border-left: 1px solid var(--line); background: var(--glass-3); padding: 1.3rem 1.35rem 1.4rem; min-width: 0; }
.kmap-detail .k { font-size: .7rem; font-weight: 600; letter-spacing: .06em; color: var(--brand); }
.kmap-detail h3 { font-family: var(--serif); font-weight: 400; font-size: 1.4rem; line-height: 1.35; margin: .35rem 0 .6rem; text-wrap: balance; }
.kmap-detail .facts { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .8rem; }
.kmap-detail .facts span { font-size: .74rem; color: var(--navy-ink); background: var(--brand-soft); padding: .15rem .55rem; border-radius: 999px; }
.kmap-detail p { font-size: .9rem; line-height: 1.8; color: var(--body); margin: 0 0 .9rem; }
.kmap-detail .by { font-size: .72rem; font-weight: 600; color: var(--muted); margin-bottom: .4rem; }
.kmap-detail ul { list-style: none; margin: 0 0 1rem; padding: 0; display: grid; gap: .3rem; }
.kmap-detail li { display: flex; gap: .45rem; align-items: center; font-size: .78rem; color: var(--body); min-width: 0; }
.kmap-detail li b { flex: none; min-width: 1.25rem; height: 1.25rem; border-radius: .4rem; background: var(--brand); color: var(--on-brand); display: grid; place-items: center; font-size: .64rem; }
.kmap-detail li span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kmap-detail .go { display: inline-flex; align-items: center; gap: .35rem; font-size: .85rem; font-weight: 600; text-decoration: none;
  padding: .45rem .9rem; border-radius: 999px; background: var(--navy); color: #fff; transition: background-color .15s; }
.kmap-detail .go:hover { background: var(--brand); color: var(--on-brand); }
.js .kmap:not(.in) .km-node { opacity: 0; transform: translateX(-10px); }
.kmap .km-node { transition-delay: calc(var(--i, 0) * 45ms); }
.kmap .km-node:hover, .kmap .km-node.on { transition-delay: 0s; }

/* The Sources, at the end: where a number leads when there is no panel, and what a printer gets. */
.refs { margin-top: 2.6rem; padding-top: 1.8rem; border-top: 1px solid var(--line); }
.refs h2 { font-family: var(--serif); font-weight: 400; font-size: 1.5rem; margin: 0 0 1rem; color: var(--ink); }
.refs ol { list-style: none; margin: 0; padding: 0; display: grid; gap: .55rem; }
.refs li { display: grid; grid-template-columns: 2rem minmax(0, 1fr); gap: .5rem; font-size: .86rem; line-height: 1.5; scroll-margin-top: 1.5rem;
  padding: .35rem .5rem; margin: 0 -.5rem; border-radius: .6rem; }
.refs li:target { background: var(--brand-soft); }
.refs .i { font-size: .75rem; font-weight: 600; color: var(--brand); font-variant-numeric: tabular-nums; padding-top: .1rem; }
.refs .h { display: block; font-size: .74rem; color: var(--muted); }
.refs a { color: var(--ink); text-decoration: none; overflow-wrap: anywhere; }
.refs a:hover { color: var(--brand); }

/* The canvas: the text, and its sources beside it. */
.read { display: grid; grid-template-columns: minmax(0, 1fr) 23rem; gap: 1.4rem; margin-top: 1.6rem; align-items: start; }
.paper { background: var(--paper); border: 1px solid var(--line); border-radius: 1.4rem; padding: 2.4rem 3rem 2rem; min-width: 0; }
.paper .lead { font-size: 1.08rem; line-height: 1.95; color: var(--ink); border-left: 2px solid rgb(37 99 235 / .5); padding-left: 1.2rem; }
.prose { font-size: 1.05rem; line-height: 1.95; color: var(--body); }
.prose p { margin: 0 0 1.05rem; }
.prose ul, .prose ol { margin: 0 0 1.05rem; padding-left: 1.4rem; }
.prose h2, .prose h3, .prose h4 { display: flex; gap: .7rem; align-items: baseline; scroll-margin-top: 1.5rem; color: var(--ink); text-wrap: balance; }
.prose h2 { font-family: var(--serif); font-weight: 400; font-size: 1.8rem; line-height: 1.3; margin: 2.6rem 0 .9rem; padding-top: 1.8rem; border-top: 1px solid var(--line); }
.prose h3 { font-size: 1.15rem; font-weight: 600; margin: 2rem 0 .6rem; }
.prose h4 { font-size: 1rem; font-weight: 600; margin: 1.6rem 0 .5rem; }
.prose .n { font-family: var(--sans); font-size: .82rem; color: var(--muted); font-variant-numeric: tabular-nums; flex: none; }
.prose h2 .n { color: var(--brand); font-weight: 500; }
a.cite { display: inline-flex; align-items: center; justify-content: center; min-width: 1.3rem; height: 1.15rem; padding: 0 .3rem;
  margin: 0 .1rem; border-radius: 999px; background: var(--brand-soft); color: var(--brand); font-size: .68rem; font-weight: 600;
  text-decoration: none; vertical-align: .18em; transition: background-color .15s, color .15s, transform .15s; }
a.cite:hover { transform: translateY(-1px); background: rgb(37 99 235 / .2); }
a.cite.on { background: var(--brand); color: var(--on-brand); }
a.cite .b { font-size: 0; }
.hl { background: linear-gradient(transparent 58%, rgb(37 99 235 / .18) 58%); }

.side { position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto; padding-bottom: 1rem; }
.side .ttl { display: flex; justify-content: space-between; font-size: .8rem; font-weight: 600; color: var(--muted); margin: .2rem .3rem .7rem; }
.side .where { font-size: .78rem; color: var(--muted); margin: -.4rem .3rem .7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc { background: var(--glass); border: 1px solid var(--line); border-radius: 1rem; padding: .8rem .9rem; margin-bottom: .6rem;
  cursor: pointer; transition: border-color .2s, box-shadow .2s, background-color .2s; animation: ls-in .25s ease-out; }
.sc:hover { border-color: rgb(37 99 235 / .4); }
.sc.on { background: var(--surface); border-color: var(--brand); box-shadow: 0 0 0 4px rgb(37 99 235 / .12); }
.sc .h { display: flex; align-items: center; gap: .45rem; font-size: .75rem; color: var(--muted); min-width: 0; }
.sc .h .host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc .num { flex: none; min-width: 1.35rem; height: 1.35rem; border-radius: .45rem; background: var(--brand); color: var(--on-brand); display: grid; place-items: center; font-size: .68rem; font-weight: 600; }
.sc .tt { font-size: .88rem; font-weight: 600; line-height: 1.5; margin-top: .4rem; }
.sc .ev { display: none; margin-top: .6rem; }
.sc.on .ev { display: block; }
.sc .ev blockquote { margin: .4rem 0 0; font-size: .8rem; line-height: 1.7; color: var(--body); padding: .5rem .65rem; border-radius: .6rem;
  background: var(--soft); border-left: 3px solid var(--brand); }
.sc .ev a { display: inline-block; margin-top: .5rem; font-size: .78rem; font-weight: 500; }
.empty { font-size: .85rem; color: var(--muted); padding: .4rem .3rem; }
.ls-cite { position: fixed; z-index: 60; width: 300px; padding: .75rem; border-radius: .9rem; pointer-events: none;
  background: var(--surface); color: var(--ink); border: 1px solid var(--line);
  box-shadow: 0 18px 40px -18px rgb(15 23 42 / .45), 0 2px 6px -2px rgb(15 23 42 / .12);
  opacity: 0; transform: translateY(var(--from, 4px)) scale(.97); transform-origin: top center;
  transition: opacity .15s ease-out, transform .15s ease-out; }
.ls-cite.on { opacity: 1; transform: none; }
.ls-cite .h { display: flex; align-items: center; gap: .4rem; font-size: .75rem; color: var(--muted); min-width: 0; }
.ls-cite .n { flex: none; display: inline-flex; align-items: center; justify-content: center; min-width: 1rem; height: 1rem;
  padding: 0 .25rem; border-radius: 999px; background: var(--brand-soft); color: var(--brand); font-size: .65rem; font-weight: 600; }
.ls-cite .fav { flex: none; display: inline-flex; align-items: center; justify-content: center; width: .9rem; height: .9rem;
  border-radius: 4px; font-size: .55rem; font-weight: 700; text-transform: uppercase;
  background: oklch(.93 .045 var(--hue)); color: oklch(.42 .12 var(--hue)); }
.ls-cite .host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ls-cite .t { margin-top: .4rem; font-size: .88rem; font-weight: 600; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ls-cite .q { margin-top: .4rem; font-size: .76rem; line-height: 1.6; color: var(--muted);
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.ls-cite .k { margin-top: .5rem; font-size: .7rem; color: var(--brand); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .ls-cite .fav { background: oklch(.33 .06 var(--hue)); color: oklch(.88 .07 var(--hue)); } }
:root[data-theme="dark"] .ls-cite .fav { background: oklch(.33 .06 var(--hue)); color: oklch(.88 .07 var(--hue)); }
@media (prefers-reduced-motion: reduce) { .ls-cite { transition: none; } }
@media print { .ls-cite { display: none; } }
.ls-progress { position: fixed; inset: 0 0 auto 0; height: 2px; background: var(--brand); transform-origin: left; transform: scaleX(0); z-index: 40; }

/* The web app's frame, a laptop: a narrower map, so all three columns show. */
@media (max-width: 1280px) {
  .kmap-body { grid-template-columns: minmax(0, 1fr) 18rem; }
  .km-tree { gap: 2.2rem; } .km-br { gap: 1.8rem; }
  .km-node.root { width: 10rem; } .km-node.l1 { width: 12.5rem; } .km-node.l2 { width: 14rem; }
}
@media (max-width: 1100px) {
  .bento { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kmap-body { grid-template-columns: 1fr; }
  .kmap-detail { border-left: 0; border-top: 1px solid var(--line); }
  .read { grid-template-columns: minmax(0, 1fr) 17rem; gap: 1rem; }
  .paper { padding: 2rem 2rem 1.6rem; }
}
/* Too narrow for a panel: a number leads to the list at the end. */
@media (max-width: 860px) {
  .read { grid-template-columns: 1fr; }
  .side { display: none; }
}
@media (max-width: 640px) {
  .wrap { padding: 1.4rem 1rem 3rem; }
  .bento { grid-template-columns: 1fr; }
  .tile.sum, .tile.chart { grid-column: auto; grid-row: auto; }
  .toc ol { grid-template-columns: 1fr; }
  /* A phone: the map as an indented list, no lines. */
  .kmap-canvas { padding: 1rem; }
  .km-tree, .km-br { flex-direction: column; align-items: stretch; gap: .6rem; min-width: 0; }
  .km-branches { gap: .9rem; }
  .km-kids { padding-left: 1rem; border-left: 2px solid var(--line); }
  .km-node.root, .km-node.l1, .km-node.l2 { width: auto; }
  .kmap-lines { display: none; }
  .paper { padding: 1.4rem 1.2rem; }
}
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } * { transition: none !important; animation: none !important; } }
@media print {
  :root:root { --bg: #eef3fb; --ink: #14213d; --body: #22304f; --muted: #5b6886; --line: rgb(30 58 138 / .12); --card: rgb(255 255 255 / .8); --soft: #f2f6fd; --brand: #2563eb; --brand-soft: rgb(37 99 235 / .1); --navy: #1e3a8a; --good: #0f9f6e; --warm: #b45309; --navy-ink: #1e3a8a; --on-brand: #fff; --surface: #fff; --paper: rgb(255 255 255 / .9); --chip: rgb(255 255 255 / .85); --glass: rgb(255 255 255 / .72); --glass-2: rgb(255 255 255 / .55); --glass-3: rgb(255 255 255 / .82); --shine: rgb(255 255 255 / .8); --shadow: rgb(30 58 138 / .45); --dots: rgb(30 58 138 / .12); --track: #e3eaf7; --wash-1: #e2dcff; --wash-2: #d6e9ff; --heat-0: #dbe5f6; --heat-1: #93b4f0; --heat-2: #4f86ee; --heat-3: #1d4ed8; color-scheme: light; }
  body { background: #fff; } .tools, .side, .ls-progress, .kmap-detail, .kmap-lines { display: none; }
  .kmap-body { grid-template-columns: 1fr; } .js .kmap .km-node { opacity: 1; transform: none; } .read { grid-template-columns: 1fr; }
  .tile, .paper { box-shadow: none; backdrop-filter: none; background: #fff; }
}
"""

SCRIPT = r"""
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  var store = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  var saved = store.get("ls-theme");
  if (saved && !root.dataset.theme) root.dataset.theme = saved;
  var themeBtn = document.querySelector("[data-act=theme]");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    store.set("ls-theme", root.dataset.theme);
  });
  var printBtn = document.querySelector("[data-act=print]");
  if (printBtn) printBtn.addEventListener("click", function () { window.print(); });
  var data = JSON.parse(document.getElementById("ls-data").textContent);
  var panel = document.getElementById("side-cards"), where = document.getElementById("side-where");
  var shown = "", active = null;
  function card(id) {
    var s = data.sources[id]; if (!s) return null;
    var el = document.createElement("div"); el.className = "sc"; el.dataset.id = id;
    var h = document.createElement("div"); h.className = "h";
    var n = document.createElement("span"); n.className = "num"; n.textContent = id;
    var host = document.createElement("span"); host.className = "host"; host.textContent = s.h;
    h.appendChild(n); h.appendChild(host); el.appendChild(h);
    var t = document.createElement("div"); t.className = "tt"; t.textContent = s.t; el.appendChild(t);
    var ev = document.createElement("div"); ev.className = "ev";
    s.e.forEach(function (x) { var q = document.createElement("blockquote"); q.textContent = x; ev.appendChild(q); });
    if (s.u) { var a = document.createElement("a"); a.href = s.u; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = data.labels.open + " ↗"; ev.appendChild(a); }
    el.appendChild(ev);
    el.addEventListener("click", function () { light(id, false); });
    return el;
  }
  function show(section) {
    if (section === shown) return;
    shown = section;
    var ids = data.cited[section] || [];
    where.textContent = data.headings[section] || "";
    panel.innerHTML = "";
    if (!ids.length) { var e = document.createElement("div"); e.className = "empty"; e.textContent = data.labels.none_here; panel.appendChild(e); }
    ids.forEach(function (id) { var c = card(id); if (c) panel.appendChild(c); });
    if (active) light(active, false, true);
  }
  function light(id, scroll, quiet) {
    active = id;
    panel.querySelectorAll(".sc").forEach(function (c) { c.classList.toggle("on", c.dataset.id === String(id)); });
    document.querySelectorAll("a.cite").forEach(function (a) { a.classList.toggle("on", a.dataset.id === String(id)); });
    var on = panel.querySelector(".sc.on");
    if (!on && !quiet) { var c = card(String(id)); if (c) { panel.insertBefore(c, panel.firstChild); c.classList.add("on"); } }
    if (scroll && on) on.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  document.querySelectorAll("a.cite").forEach(function (a) {
    a.dataset.id = a.getAttribute("href").replace("#src-", "");
    a.addEventListener("click", function (e) {
      if (!panel.offsetParent) return;  // no panel on a narrow screen: follow the link
      e.preventDefault(); light(a.dataset.id, true);
    });
  });
  // A citation's source, beside it while the pointer rests on it (as the
  // report page in the web app shows it). A figure's number quotes the very
  // passage behind that figure; the text's quotes the source's first.
  var tip = document.createElement("div");
  tip.className = "ls-cite"; tip.setAttribute("role", "tooltip"); tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);
  var tipFor = null;
  function hueOf(host) { var h = 0; for (var i = 0; i < host.length; i++) h = (h * 31 + host.charCodeAt(i)) % 360; return h; }
  function hideTip() { tipFor = null; tip.classList.remove("on"); }
  function showTip(a) {
    var id = (a.getAttribute("href") || "").replace("#src-", ""), s = data.sources[id];
    if (!s) return;
    tipFor = a;
    tip.innerHTML = "";
    var add = function (parent, tag, cls, text) { var x = document.createElement(tag); x.className = cls; if (text != null) x.textContent = text; parent.appendChild(x); return x; };
    var head = add(tip, "div", "h");
    add(head, "span", "n", id);
    var fav = add(head, "span", "fav", (s.h || "?").charAt(0));
    fav.style.setProperty("--hue", hueOf(s.h || ""));
    add(head, "span", "host", s.h);
    add(tip, "div", "t", s.t);
    var quote = a.getAttribute("data-tip") || s.e[0];
    if (quote) add(tip, "div", "q", "\u201c" + quote + "\u201d");
    add(tip, "div", "k", data.labels.cite_hint);
    var at = a.getBoundingClientRect(), w = 300;
    var left = Math.max(12, Math.min(at.left + at.width / 2 - w / 2, innerWidth - w - 12));
    var below = at.bottom + 220 < innerHeight;
    tip.style.left = left + "px";
    tip.style.top = below ? (at.bottom + 8) + "px" : "";
    tip.style.bottom = below ? "" : (innerHeight - at.top + 8) + "px";
    tip.style.setProperty("--from", below ? "-4px" : "4px");
    tip.classList.remove("on"); void tip.offsetWidth; tip.classList.add("on");
  }
  document.addEventListener("mouseover", function (e) {
    var a = e.target.closest && e.target.closest("a.cite");
    if (a) { if (a !== tipFor) showTip(a); } else if (tipFor) hideTip();
  });
  document.addEventListener("focusin", function (e) { if (e.target.matches && e.target.matches("a.cite")) showTip(e.target); });
  document.addEventListener("focusout", hideTip);
  addEventListener("scroll", hideTip, { passive: true });
  document.addEventListener("click", hideTip);

  // A figure drawn from a table: the figure, or its data a tab away.
  document.querySelectorAll("figure.ix").forEach(function (fig) {
    var tabs = fig.querySelectorAll("[role=tab]");
    if (!tabs.length) return;
    function tab(name) {
      tabs.forEach(function (t) { t.setAttribute("aria-selected", String(t.dataset.tab === name)); });
      fig.querySelectorAll(".panel").forEach(function (p) { p.hidden = p.dataset.panel !== name; });
    }
    tabs.forEach(function (t) { t.addEventListener("click", function () { tab(t.dataset.tab); }); });
    tab("view");
  });
  // The map: lines from each theme to what grew from it, the gist of the one pressed.
  var map = document.querySelector(".kmap");
  if (map) {
    var canvas = map.querySelector(".kmap-canvas"), lines = map.querySelector(".kmap-lines"), detail = map.querySelector(".kmap-detail");
    var SVG = "http://www.w3.org/2000/svg", drawn = {}, picked = "";
    var mark = function () {
      Object.keys(drawn).forEach(function (k) { drawn[k].classList.remove("on"); });
      var n = picked && map.querySelector('.km-node[data-node="' + picked + '"]');
      while (n && n.dataset.parent) { if (drawn[n.dataset.node]) drawn[n.dataset.node].classList.add("on"); n = map.querySelector('.km-node[data-node="' + n.dataset.parent + '"]'); }
    };
    var draw = function () {
      var box = canvas.getBoundingClientRect();
      lines.setAttribute("width", canvas.scrollWidth); lines.setAttribute("height", canvas.scrollHeight);
      while (lines.firstChild) lines.removeChild(lines.firstChild);
      drawn = {};
      map.querySelectorAll(".km-node[data-parent]").forEach(function (n) {
        var p = map.querySelector('.km-node[data-node="' + n.dataset.parent + '"]');
        if (!p) return;
        var a = p.getBoundingClientRect(), b = n.getBoundingClientRect();
        if (b.left < a.right) return;  // stacked: the list says it
        var x1 = a.right - box.left + canvas.scrollLeft, y1 = a.top + a.height / 2 - box.top;
        var x2 = b.left - box.left + canvas.scrollLeft, y2 = b.top + b.height / 2 - box.top, mx = (x1 + x2) / 2;
        var path = document.createElementNS(SVG, "path");
        path.setAttribute("d", "M" + x1 + " " + y1 + " C" + mx + " " + y1 + " " + mx + " " + y2 + " " + x2 + " " + y2);
        path.setAttribute("pathLength", "1");
        path.style.strokeDasharray = "1";
        path.style.strokeDashoffset = map.classList.contains("in") ? "0" : "1";
        lines.appendChild(path); drawn[n.dataset.node] = path;
      });
      mark();
    };
    var pick = function (id) {
      var m = data.map[id]; if (!m) return;
      picked = id;
      map.querySelectorAll(".km-node").forEach(function (n) { n.classList.toggle("on", n.dataset.node === id); n.setAttribute("aria-pressed", String(n.dataset.node === id)); });
      mark();
      var el = function (tag, cls, text) { var x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; };
      detail.innerHTML = "";
      detail.appendChild(el("div", "k", m.kind));
      detail.appendChild(el("h3", "", m.heading));
      var facts = el("div", "facts"); m.facts.forEach(function (f) { facts.appendChild(el("span", "", f)); }); detail.appendChild(facts);
      if (m.gist) detail.appendChild(el("p", "", m.gist));
      if (m.sources.length) {
        detail.appendChild(el("div", "by", data.labels.backed_by));
        var ul = el("ul");
        m.sources.forEach(function (sid) { var s = data.sources[sid]; if (!s) return; var li = el("li"); li.appendChild(el("b", "", sid)); li.appendChild(el("span", "", s.h + " · " + s.t)); ul.appendChild(li); });
        detail.appendChild(ul);
      }
      var go = el("a", "go", data.labels.read_this + " ↓"); go.href = "#" + (id === "lead" ? "read" : id); detail.appendChild(go);
    };
    map.querySelectorAll(".km-node").forEach(function (n) { n.addEventListener("click", function () { pick(n.dataset.node); }); });
    var first = map.querySelector(".km-node.l1");
    pick(first ? first.dataset.node : "lead");
    draw();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
    if (window.ResizeObserver) new ResizeObserver(function () { draw(); }).observe(canvas);
    var grow = function () {
      map.classList.add("in");
      Object.keys(drawn).forEach(function (k, i) { var p = drawn[k]; setTimeout(function () { p.style.strokeDashoffset = "0"; }, 150 + i * 30); });
    };
    if (window.IntersectionObserver && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      var seen = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { seen.disconnect(); grow(); } }, { threshold: 0.15 });
      seen.observe(map);
    } else grow();
  }

  var heads = Array.prototype.slice.call(document.querySelectorAll("[data-section]"));
  var bar = document.createElement("div"); bar.className = "ls-progress"; document.body.appendChild(bar);
  var frame = 0;
  function measure() {
    frame = 0;
    var current = "lead";
    for (var i = 0; i < heads.length; i++) { if (heads[i].getBoundingClientRect().top < innerHeight * .35) current = heads[i].dataset.section; else break; }
    show(current);
    var p = document.querySelector(".paper").getBoundingClientRect(), span = p.height - innerHeight;
    bar.style.transform = "scaleX(" + (span > 0 ? Math.min(1, Math.max(0, -p.top / span)) : 1) + ")";
  }
  addEventListener("scroll", function () { if (!frame) frame = requestAnimationFrame(measure); }, { passive: true });
  measure();

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


def _tiles(report, visuals, labels, svg):
    """Up to three key figures from checked stat cards; plain counts fill in."""
    figures = []
    for b in (visuals or {}).get("blocks") or []:
        if b["id"] in set((visuals or {}).get("hidden") or []):
            continue
        if b["type"] == "stat_cards":
            for i, item in enumerate(b["items"]):
                figures.append((item, b["id"] if i == 0 else ""))
    out = []
    for i, (item, block_id) in enumerate(figures[:3], 1):
        value = interactive._num(item["value"], report["language"])
        cls = "big mid" if len(value) > 7 else "big"
        out.append(
            f'<div class="tile c{i}"{f' id="{block_id}"' if block_id else ""}><div class="lbl">{E(item["label"])}</div>'
            f'<div class="{cls}">{value}<small>{E(item["unit"])}</small></div>'
            f'<div class="sub">{E(item["as_of"]) + " · " if item["as_of"] else ""}'
            f'<a class="cite" href="#src-{item["cite"]["source"]}" data-tip="{E(item["cite"]["text"])}">'
            f'{item["cite"]["source"]}</a></div></div>'
        )
    # Too few figures: what the report itself can say about where its
    # weight lies.
    n_sections = sum(1 for _ in report_mod.walk(report["sections"]))
    fillers = []
    themes = [(len(_backing(s)), s) for s in report["sections"]]
    if len(themes) >= 2:
        n, theme = max(themes, key=lambda t: t[0])
        subs = sum(1 for _ in report_mod.walk(theme["children"]))
        fillers.append(
            f'<div class="tile c2"><div class="lbl">{labels["strongest"]}</div>'
            f'<a class="txt" href="#{theme["id"]}">{E(theme["heading"])}</a>'
            f'<div class="sub">{labels["n_sources"].format(n=n)}'
            f'{" · " + labels["n_subs"].format(n=subs) if subs else ""}</div></div>')
    counts = interactive.citation_counts(report)
    if counts and max(counts.values()) > 1:
        top_src = max(report["sources"], key=lambda x: (counts[x["id"]], -x["id"]))
        fillers.append(
            f'<div class="tile c3"><div class="lbl">{labels["main_source"]}</div>'
            f'<div class="big mid">{E(page_mod._host(top_src["url"]) or top_src["title"])}</div>'
            f'<div class="sub">{labels["cited_n"].format(n=counts[top_src["id"]])} · '
            f'<a class="cite" href="#src-{top_src["id"]}">{top_src["id"]}</a></div></div>')
    fillers.append(
        f'<div class="tile c1"><div class="lbl">{labels["sections"]}</div><div class="big">{n_sections}</div>'
        f'<div class="sub">{labels["read"].format(n=page_mod._minutes(report))}</div></div>')
    while len(out) < 3 and fillers:
        out.append(fillers.pop(0))
    with_ev = sum(1 for s in report["sources"] if s["evidence"])
    total = max(1, len(report["sources"]))
    arc = 94 * with_ev / total
    out.append(
        f'<div class="tile"><svg class="ring" width="58" height="58" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke-width="5" style="stroke: var(--track)"/>'
        f'<circle cx="18" cy="18" r="15" fill="none" stroke-width="5" style="stroke: var(--brand)" stroke-dasharray="{arc:.1f} 100" transform="rotate(-90 18 18)" stroke-linecap="round"/></svg>'
        f'<div class="lbl">{labels["sources"]}</div><div class="big">{len(report["sources"])}</div>'
        f'<div class="sub">{labels["with_evidence"].format(n=with_ev)}</div></div>'
    )
    chart = ""
    if svg:
        title, from_ids = svg[1], svg[2]
        pills = "".join(f'<a class="cite" href="#src-{n}">{n}</a>' for n in from_ids)
        chart = (f'<div class="tile chart" id="{svg[3]}"><div class="lbl">{labels["chart"]}</div><div class="t">{E(title)}</div>'
                 f'<div class="chart" data-chart="{svg[3]}">{svg[0]}</div><div class="sub">{pills}</div></div>')
    return out, chart


def _gist(text, limit=260):
    """A section's opening, as plain words: no citations, no markdown."""
    text = report_mod.CITATION.sub("", text or "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip() and not p.lstrip().startswith(("#", "|"))]
    text = re.sub(r"[*_`>#]+", "", paras[0] if paras else "")
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = text.rfind(" ", limit // 2, limit)
        text = text[: cut if cut > 0 else limit].rstrip() + " …"
    return text


def _backing(section):
    """The Sources a section and everything under it cite, in order."""
    ids = []
    for s in [section, *report_mod.walk(section["children"])]:
        for n in report_mod.cited_ids(s["body"]):
            if n not in ids:
                ids.append(n)
    return ids


def _heat(n, most):
    """How much stands behind a part, against the part with the most."""
    if not n:
        return "h0"
    share = n / max(1, most)
    return "h3" if share > .66 else "h2" if share > .33 else "h1"


def _map(report, sections, labels, figures):
    """The report as a map: its title, its themes, their subtopics; each with
    how many Sources back it. The gist and the Sources of each, for the panel."""
    if not sections:
        return "", {}
    backing = {s["id"]: _backing(s) for s in report_mod.walk(sections)}
    most = max((len(v) for v in backing.values()), default=1)
    data = {}

    def facts(s):
        out = [labels["n_sources"].format(n=len(backing[s["id"]]))]
        if s["children"]:
            out.append(labels["n_subs"].format(n=sum(1 for _ in report_mod.walk(s["children"]))))
        n_figs = sum(figures.get(x["id"], 0) for x in [s, *report_mod.walk(s["children"])])
        if n_figs:
            out.append(labels["n_figs"].format(n=n_figs))
        return out

    def gist(s):
        found = _gist(s["body"])
        for c in report_mod.walk(s["children"]):
            if found:
                break
            found = _gist(c["body"])
        return found

    def node(s, level, parent, i):
        data[s["id"]] = {"kind": labels["main"] if level == 1 else labels["sub"], "heading": f'{s["n"]} {s["heading"]}',
                         "facts": facts(s), "gist": gist(s), "sources": [str(n) for n in backing[s["id"]][:6]]}
        meta = [labels["n_sources"].format(n=len(backing[s["id"]]))]
        deeper = sum(1 for _ in report_mod.walk(s["children"])) if level == 2 else 0
        if deeper:
            meta.append(labels["more_subs"].format(n=deeper))
        kind = f'<span class="k">{labels["main"]} · {s["n"]}</span>' if level == 1 else ""
        return (f'<button type="button" class="km-node l{level} {_heat(len(backing[s["id"]]), most)}" data-node="{s["id"]}" '
                f'data-parent="{parent}" aria-pressed="false" style="--i:{i}">{kind}<span class="hd">{E(s["heading"])}</span>'
                f'<span class="mt">{"".join(f"<span>{E(m)}</span>" for m in meta)}</span></button>')

    i = 1
    branches = []
    for s in sections:
        top = node(s, 1, "lead", i)
        i += 1
        kids = []
        for c in s["children"]:
            kids.append(node(c, 2, s["id"], i))
            i += 1
        branches.append(f'<div class="km-br">{top}{"<div class=km-kids>" + "".join(kids) + "</div>" if kids else ""}</div>')
    n_all = sum(1 for _ in report_mod.walk(sections))
    data["lead"] = {"kind": labels["overview"], "heading": report["title"],
                    "facts": [labels["n_sources"].format(n=len(report["sources"])), labels["n_subs"].format(n=n_all)],
                    "gist": _gist(report["lead"]), "sources": [str(n) for n in report_mod.cited_ids(report["lead"])[:6]]}
    root = (f'<button type="button" class="km-node root" data-node="lead" aria-pressed="false" style="--i:0">'
            f'<span class="k">{labels["overview"]}</span><span class="hd">{E(report["title"])}</span>'
            f'<span class="mt"><span>{labels["n_sources"].format(n=len(report["sources"]))}</span>'
            f'<span>{labels["n_subs"].format(n=n_all)}</span></span></button>')
    out = (f'<section class="kmap" aria-label="{labels["map"]}"><div class="kmap-head"><div class="lbl">{labels["map"]}</div>'
           f'<p class="hint">{labels["map_hint"]}</p></div><div class="kmap-body"><div class="kmap-canvas">'
           f'<svg class="kmap-lines" aria-hidden="true"></svg><div class="km-tree">{root}<div class="km-branches">{"".join(branches)}</div></div></div>'
           f'<div class="kmap-detail" aria-live="polite"></div></div></section>')
    return out, data


def render(report, visuals=None, engine_label="", finished_at=None, svgs=None, full=False):
    """The page. `svgs` maps a chart's id to its drawn SVG (drawn here with
    Chromium when not given); `full` brings the chart library along, +1.1 MB,
    for charts that answer the pointer."""
    language = report["language"]
    labels = LABELS[language]
    ix_labels = interactive.LABELS[language]
    hidden = set((visuals or {}).get("hidden") or [])
    blocks = [b for b in (visuals or {}).get("blocks") or [] if b["id"] not in hidden]

    # The brief's chart is the first chart the model drew, else the Sources
    # cited most; other charts go in the text, after their section.
    charts = [b for b in blocks if b["type"] == "chart"]
    specs = interactive.chart_specs(blocks, language)
    top = charts[0] if charts else None
    top_sections = report["sections"]
    if top is None and len(top_sections) >= 3 and report["sources"]:
        # What stands behind each theme: a measure every report has.
        specs["by-section"] = {
            "kind": "bar", "categories": [interactive._short(s["heading"], 40) for s in top_sections[:8]],
            "series": [{"name": "", "values": [len(_backing(s)) for s in top_sections[:8]]}],
            "unit": "", "x_label": "", "y_label": "", "locale": language,
        }
    elif top is None and report["sources"]:
        # A tile, not a page: six Sources, a line each.
        spec, ranked, _ = interactive.most_cited_spec(report, top=6)
        # Where each comes from reads at a glance; titles cut short do not.
        spec["categories"] = [f"[{s['id']}] {interactive._short(page_mod._host(s['url']) or s['title'], 24)}" for s in ranked]
        specs["most-cited"] = spec
    if svgs is None:
        ids = list(specs)
        svgs = dict(zip(ids, interactive.prerender([specs[i] for i in ids])))
    if top is not None:
        chart_svg = (svgs.get(top["id"], ""), top["title"] or labels["chart"], top["sources"], top["id"])
    elif "by-section" in specs:
        chart_svg = (svgs["by-section"], labels["evidence_by_section"], [], "by-section")
    elif "most-cited" in specs:
        chart_svg = (svgs["most-cited"], labels["most_cited"], [], "most-cited")
    else:
        chart_svg = None
    tiles, chart_tile = _tiles(report, visuals, labels, chart_svg)

    # The rest of the model's blocks in the text, after their section.
    after = {}
    for b in blocks:
        if b["type"] == "stat_cards" or b is top:
            continue
        if b["type"] == "chart":
            fig = interactive._chart(b, ix_labels, language, svgs.get(b["id"], ""))
        elif b["type"] == "comparison":
            fig = interactive._comparison(b, ix_labels, language, svgs.get(b["id"], ""))
        else:
            fig = interactive._BLOCKS[b["type"]](b, ix_labels, language)
        after.setdefault(b["anchor"], []).append(fig)

    sections = page_mod._numbered(report["sections"])
    figures = {}
    for b in blocks:
        if b["type"] != "stat_cards" and b is not top:
            figures[b["anchor"]] = figures.get(b["anchor"], 0) + 1
    kmap, map_data = _map(report, sections, labels, figures)
    cited = {"lead": report_mod.cited_ids(report["lead"])}
    headings = {"lead": report["title"]}

    def body(items, level=2):
        out = []
        for s in items:
            tag = f"h{min(level, 4)}"
            n = s["n"].zfill(2) if level == 2 else s["n"]
            cited[s["id"]] = report_mod.cited_ids(s["body"])
            headings[s["id"]] = s["heading"]
            out.append(f'<{tag} id="{s["id"]}" data-section="{s["id"]}"><span class="n">{n}</span><span>{E(s["heading"])}</span></{tag}>')
            out.append(page_mod._markdown(s["body"]))
            out.extend(after.get(s["id"], []))
            out.append(body(s["children"], level + 1))
        return "\n".join(out)

    article = body(sections)
    # The brief opens with the overview's first sentences, cut at a space
    # (Thai marks phrases with spaces) — the whole of it follows below.
    first_para = (report["lead"].split("\n\n")[0] if report["lead"].strip() else "")
    if len(first_para) > 380:
        cut = first_para.rfind(" ", 200, 380)
        first_para = first_para[: cut if cut > 0 else 380].rstrip() + " …"
    summary = page_mod._markdown(first_para)
    toc = "".join(f'<li><a href="#{s["id"]}"><span class="n">{s["n"].zfill(2)}</span><span>{E(s["heading"])}</span></a></li>'
                  for s in sections)

    facts = [f'<span class="mode">{E(engine_label)}</span>' if engine_label else ""]
    if finished_at:
        facts.append(f"<span>{page_mod._date(finished_at, language)}</span>")
    facts.append(f'<span>{labels["read"].format(n=page_mod._minutes(report))}</span>')
    facts.append(f'<span>{len(report["sources"])} {labels["sources"]}'
                 f'{" · " + labels["verified"] if any(s["evidence"] for s in report["sources"]) else ""}</span>')

    sources = {
        str(s["id"]): {"t": s["title"], "h": page_mod._host(s["url"]),
                       "u": s["url"] if s["url"].startswith(("http://", "https://")) else "",
                       "e": [e[:420] for e in s["evidence"][:3]]}
        for s in report["sources"]
    }
    data = {"sources": sources, "cited": cited, "headings": headings, "map": map_data,
            "labels": {"open": labels["open"], "none_here": labels["none_here"],
                       "backed_by": labels["backed_by"], "read_this": labels["read_this"],
                       "cite_hint": labels["cite_hint"]}}
    note = f'<p class="note">{labels["figures_note"]}</p>' if blocks else ""
    refs = ""
    if report["sources"]:
        items = []
        for src in report["sources"]:
            title = E(src["title"] or src["url"])
            link = (f'<a href="{E(src["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>'
                    if src["url"].startswith(("http://", "https://")) else title)
            items.append(f'<li id="src-{src["id"]}"><span class="i">{src["id"]}</span>'
                         f'<span><span class="h">{E(page_mod._host(src["url"]))}</span>{link}</span></li>')
        refs = f'<section class="refs"><h2>{labels["sources"]}</h2><ol>{"".join(items)}</ol></section>'

    lead_after = "".join(after.get("lead", []))
    scripts = [SCRIPT]
    charts_data = ""
    if full and specs:
        with open(interactive.ECHARTS, encoding="utf-8") as f:
            scripts = [f.read(), interactive.CHART_JS, SCRIPT]
        charts_data = interactive._json_script("ls-charts", specs)
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; "
        f"script-src {' '.join(interactive._hash(x) for x in scripts)}; base-uri 'none'; form-action 'none'"
    )
    return f"""<!doctype html>
<html lang="{language}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{policy}">
<title>{E(report["title"])}</title>
<style>{page_mod._font_faces()}
{CSS}
{interactive.CSS}</style></head>
<body><div class="wrap">
<div class="top"><div class="chips">{"".join(facts)}</div>
<div class="tools"><button type="button" data-act="theme">{labels["theme"]}</button><button type="button" data-act="print">{labels["print"]}</button></div></div>
<h1>{E(report["title"])}</h1>
<div class="bento">
<div class="tile sum"><div class="lbl">{labels["summary"]}</div>{summary}
<nav class="toc"><div class="lbl">{labels["contents"]}</div><ol>{toc}</ol></nav></div>
{"".join(tiles[:2])}
{chart_tile}
{"".join(tiles[2:])}
</div>
{note}
{kmap}
<div class="read" id="read">
<article class="paper"><div class="prose" data-section="lead"><div class="lead">{page_mod._markdown(report["lead"])}</div>{lead_after}
{article}</div>{refs}</article>
<aside class="side"><div class="ttl"><span>{labels["in_section"]}</span></div><div class="where" id="side-where"></div><div id="side-cards"></div></aside>
</div></div>
{interactive._json_script("ls-data", data)}
{charts_data}
{"".join(f"<script>{x}</script>" for x in scripts)}
</body></html>
"""
