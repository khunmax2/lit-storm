"""Shared look-and-feel for the STORM demo UI.

Everything visual that is not tied to a single page lives here: the global
stylesheet, the colour tokens the pages reference, and a couple of small
building blocks (page headers, article cards) that keep the two pages
consistent.
"""

import os
from datetime import datetime

import streamlit as st
import ui_language
from ui_language import t

# Colour tokens, one set per theme. Keep these in sync with the
# [theme.light] / [theme.dark] sections of .streamlit/config.toml.
LIGHT = {
    "brand": "#E11D62",
    "brand-hover": "#C4104F",
    "brand-soft": "#FDE7EF",
    "on-brand": "#FFFFFF",
    "ink": "#14161A",
    "muted": "#69707D",
    "line": "#E5E8EF",
    "line-strong": "#C9CEDA",
    "canvas": "#F7F8FA",
    "surface": "#FFFFFF",
    "nav-hover": "#ECEFF4",
    "shadow": "rgba(20, 22, 26, 0.18)",
    "shadow-soft": "rgba(20, 22, 26, 0.25)",
}

DARK = {
    "brand": "#FF5C87",
    "brand-hover": "#FF7C9F",
    "brand-soft": "rgba(255, 92, 135, 0.16)",
    # The dark-mode brand is a light pink, so it needs dark text on top.
    "on-brand": "#14171E",
    "ink": "#E9ECF1",
    "muted": "#98A1B0",
    "line": "#272C36",
    "line-strong": "#3A424F",
    "canvas": "#14171E",
    "surface": "#181C24",
    "nav-hover": "#1E232C",
    "shadow": "rgba(0, 0, 0, 0.55)",
    "shadow-soft": "rgba(0, 0, 0, 0.6)",
}

# Trirong (serif) and IBM Plex Sans Thai both ship Thai *and* Latin glyphs.
# A Latin-only pairing would leave Thai text to a system fallback, so the same
# page would render in two unrelated typefaces depending on the language.
FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans+Thai:wght@400;500;600&"
    "family=Trirong:wght@500;600;700&display=swap');"
)

FONT_STACK = (
    '"IBM Plex Sans Thai", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    '"Helvetica Neue", Arial, sans-serif'
)

DISPLAY_STACK = '"Trirong", Georgia, "Times New Roman", serif'


def _vars():
    """Every token as `light-dark(light, dark)`.

    These are declared on `.stApp`, the one element Streamlit gives a real
    `color-scheme`, so `light-dark()` resolves against the theme Streamlit is
    actually painting with. That keeps the two in lockstep through a settings
    change — `prefers-color-scheme` would miss a manual override, and reading
    `st.context.theme.type` in Python reports the *previous* theme for one
    rerun after the switch, which paints dark text on a light page.
    """
    return "\n".join(
        f"    --{name}: light-dark({LIGHT[name]}, {DARK[name]});" for name in LIGHT
    )


_CSS = f"""
<style>
{FONT_IMPORT}

.stApp {{
{_vars()}
}}

html, body, [class*="st-"], button, input, textarea {{
    font-family: {FONT_STACK};
}}

h1, h2, h3, .hero h1, .page-head h1, .article-head h1, .lp-step .t {{
    font-family: {DISPLAY_STACK};
}}

/* ...but never on the icon spans, whose glyphs are font ligatures. Streamlit
   names these several ways — stIconMaterial, stExpanderIconError and so on —
   so match the family rather than each one, or a status that turns red shows
   the word "error" where the symbol belongs. */
[data-testid*="Icon"],
span[class*="material-symbols"],
span[class*="material-icons"] {{
    font-family: "Material Symbols Rounded" !important;
}}

/* Roomier page gutters, capped so long articles stay readable. */
[data-testid="stMainBlockContainer"] {{
    padding-top: 2.4rem;
    padding-bottom: 4rem;
    max-width: 1180px;
}}

/* ---------- page header ---------- */
.page-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin: 0.4rem 0 1.6rem 0;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid var(--line);
}}
.page-head h1 {{
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin: 0;
    padding: 0;
}}
.page-head .sub {{
    font-size: 0.9rem;
    color: var(--muted);
}}

/* ---------- hero (create page) ---------- */
.hero {{
    text-align: center;
    margin: 2.4rem 0 1.8rem 0;
}}
.hero .eyebrow {{
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--brand);
    background: var(--brand-soft);
    padding: 0.28rem 0.7rem;
    border-radius: 999px;
    margin-bottom: 1rem;
}}
.hero h1 {{
    font-size: 2.3rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: var(--ink);
    margin: 0 0 0.6rem 0;
    line-height: 1.15;
}}
.hero p {{
    font-size: 1rem;
    color: var(--muted);
    margin: 0 auto;
    max-width: 34rem;
    line-height: 1.6;
}}

/* ---------- landing ---------- */
/* Swiss-modernist section marker: small, spaced, sitting on a hairline. */
.lp-label {{
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    padding-bottom: 0.6rem;
    margin: 3.2rem 0 1.6rem 0;
    border-bottom: 1px solid var(--line);
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}}

.lp-note {{
    text-align: center;
    font-size: 0.82rem;
    color: var(--muted);
    margin-top: 1rem;
}}

/* Three columns on a shared baseline; collapses to one on small screens
   rather than shrinking into unreadable columns. */
.lp-steps {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
}}
@media (max-width: 820px) {{
    .lp-steps {{ grid-template-columns: 1fr; gap: 1.6rem; }}
}}
.lp-step .n {{
    font-family: {DISPLAY_STACK};
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--brand);
    display: block;
    padding-bottom: 0.7rem;
    margin-bottom: 0.8rem;
    border-top: 2px solid var(--brand);
    padding-top: 0.7rem;
}}
.lp-step .t {{
    font-size: 1.02rem;
    font-weight: 600;
    line-height: 1.35;
    color: var(--ink);
    margin-bottom: 0.5rem;
}}
.lp-step .b {{
    font-size: 0.88rem;
    line-height: 1.65;
    color: var(--muted);
    /* 65-75 characters is the readable measure; the column is usually
       narrower than this, so it only bites on very wide screens. */
    max-width: 34ch;
}}

/* Touch targets. 40px clears the WCAG 2.2 minimum but sits under the 44px
   platform guidance, which is what thumbs actually need — so raise our own
   controls on the widths where the pointer is a finger. */
@media (max-width: 768px) {{
    .stButton > button,
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stSegmentedControl"] button,
    .st-key-nav_page button[data-variant="segmented_control"] {{
        min-height: 44px;
    }}
    [data-testid="stTextInputRootElement"],
    [data-baseweb="select"] > div {{
        min-height: 44px;
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
    }}
}}

/* ---------- article cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(.acard) {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 1.1rem 1.15rem 0.9rem 1.15rem;
    height: 100%;
    transition: border-color 0.15s ease, box-shadow 0.15s ease,
        transform 0.15s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.acard):hover {{
    border-color: var(--line-strong);
    box-shadow: 0 6px 20px -8px var(--shadow);
    transform: translateY(-2px);
}}
.acard .title {{
    font-size: 1.02rem;
    font-weight: 650;
    line-height: 1.35;
    color: var(--ink);
    margin-bottom: 0.45rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.7em;
}}
/* One line, never wrapping — otherwise cards in a row end up different
   heights as soon as the sidebar narrows them. */
.acard .meta {{
    font-size: 0.76rem;
    color: var(--muted);
    margin-bottom: 0.6rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.acard .meta .sep {{ opacity: 0.45; padding: 0 0.35rem; }}
.acard .excerpt {{
    font-size: 0.84rem;
    line-height: 1.55;
    color: var(--muted);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    /* Three lines at the line-height above. 3.9em only reserved two, so a
       card with a short excerpt sat 10px shorter than its neighbours. */
    min-height: 4.65em;
}}

/* ---------- empty state ---------- */
.empty {{
    text-align: center;
    padding: 3.2rem 1rem 2.4rem 1rem;
    border: 1px dashed var(--line-strong);
    border-radius: 16px;
    background: var(--canvas);
}}
.empty .icon {{
    display: block;
    font-size: 2.4rem;
    line-height: 1;
    color: var(--muted);
    margin-bottom: 0.2rem;
}}
.empty h3 {{
    font-size: 1.1rem;
    font-weight: 650;
    color: var(--ink);
    margin: 0.7rem 0 0.35rem 0;
}}
.empty p {{
    font-size: 0.9rem;
    color: var(--muted);
    margin: 0;
}}

/* ---------- buttons ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {{
    border-radius: 9px;
    border: 1px solid var(--line);
    font-weight: 550;
    transition: background 0.15s ease, border-color 0.15s ease,
        color 0.15s ease;
}}
.stButton > button:hover:not(:disabled),
[data-testid="stFormSubmitButton"] > button:hover:not(:disabled) {{
    border-color: var(--brand);
    color: var(--brand);
}}
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {{
    background: var(--brand) !important;
    border-color: var(--brand) !important;
    color: var(--on-brand) !important;
}}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    background: var(--brand-hover) !important;
    border-color: var(--brand-hover) !important;
    color: var(--on-brand) !important;
}}

/* ---------- inputs ---------- */
[data-testid="stTextInputRootElement"] {{
    border-radius: 10px;
    border-color: var(--line);
}}
[data-testid="stTextInputRootElement"]:focus-within {{
    border-color: var(--brand);
    box-shadow: 0 0 0 3px var(--brand-soft);
}}
[data-testid="stForm"] {{
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.6rem;
    background: var(--surface);
    box-shadow: 0 8px 30px -18px var(--shadow-soft);
}}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
    background: var(--canvas);
    border-right: 1px solid var(--line);
}}
/* Streamlit's sidebar header holds only the collapse button but reserves
   76px, and the padding here added another 26 on top of it — a third of the
   rail was empty before the logo. */
[data-testid="stSidebarHeader"] {{
    height: 2.6rem;
    padding-top: 0.5rem;
    padding-bottom: 0;
}}
[data-testid="stSidebarUserContent"] {{ padding-top: 0.25rem; }}

/* The rail is a column: navigation at the top, the account at the foot.
   Streamlit wraps a keyed container in a stLayoutWrapper, so the margin has
   to go on that wrapper — it is the flex child, not the container itself. */
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(
    > [data-testid="stLayoutWrapper"] > .st-key-side_account
) {{
    min-height: calc(100vh - 7rem);
}}
[data-testid="stLayoutWrapper"]:has(> .st-key-side_account) {{
    margin-top: auto !important;
}}
.st-key-side_account {{
    padding-top: 0.7rem;
    border-top: 1px solid #263048;
}}
.side-label {{
    font-size: 0.7rem;
    font-weight: 650;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
}}

/* ---------- expanders / status ---------- */
[data-testid="stExpander"] details {{
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--surface);
}}

/* ---------- article body ---------- */
.article-head {{
    margin: 0.5rem 0 1.4rem 0;
}}
.article-head h1 {{
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    line-height: 1.2;
    color: var(--ink);
    margin: 0 0 0.6rem 0;
}}
.article-head .meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.6rem;
    font-size: 0.78rem;
    color: var(--muted);
}}
.article-head .meta .chip {{
    background: var(--canvas);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.16rem 0.6rem;
}}
.article-body {{ max-width: 46rem; }}

/* Inline citation links inside the article text. */
[data-testid="stMarkdownContainer"] a[href^="http"] {{
    color: var(--brand);
    text-decoration: none;
    font-size: 0.82em;
    vertical-align: 0.28em;
    padding: 0 0.04em;
}}
[data-testid="stMarkdownContainer"] a[href^="http"]:hover {{
    text-decoration: underline;
}}

/* ---------- sidebar brand block ---------- */
.side-brand {{
    padding-bottom: 1rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--line);
}}
.side-brand .name {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.05rem;
    letter-spacing: 0.01em;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--ink);
}}
.side-brand .tag {{
    font-size: 0.78rem;
    color: var(--muted);
    line-height: 1.5;
    margin-top: 0.25rem;
}}

/* ---------- reference panel ---------- */
.ref-card {{
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.8rem 0.9rem;
    background: var(--surface);
}}
.ref-card .ref-title {{
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1.4;
    margin-bottom: 0.3rem;
}}
.ref-card .ref-url {{
    font-size: 0.74rem;
    color: var(--muted);
    word-break: break-all;
    margin-bottom: 0.5rem;
}}
.ref-card .ref-url a {{ color: var(--brand); text-decoration: none; }}

/* ---------- top navigation ---------- */
/* st.segmented_control, centred and dressed as a pill switcher. Deliberately
   a native widget rather than a custom component: components render inside an
   iframe that this stylesheet cannot reach, so their colours would have to be
   resolved in Python and would lag a theme change by one rerun. */
/* `.st-key-nav_page` is Streamlit's per-widget class, derived from the
   segmented control's key in storm.py. */
/* A vertical list, not a pill bar: two destinations do not warrant a bar of
   their own, and the sidebar has to exist regardless — it is where the
   article page puts its contents and references. */
.st-key-nav_page {{
    width: 100% !important;
    margin: 0.2rem 0 1.5rem 0;
}}
/* A flex parent stretches the wrapper; setting a width on the wrapper
   directly loses to a Streamlit rule that sizes it to its content. */
.st-key-nav_page [data-testid="stButtonGroup"] {{
    display: flex;
    width: 100%;
}}
.st-key-nav_page [data-testid="stButtonGroup"] > div {{
    display: flex;
    flex-direction: column;
    /* The wrapper carries `max-width: fit-content`, which is what actually
       pins the rows to their label width — width alone never wins. */
    max-width: none;
    flex: 1 1 auto;
    align-items: stretch;
    gap: 0.15rem;
    background: transparent;
    border: none;
    padding: 0;
}}
.st-key-nav_page button[data-variant="segmented_control"] {{
    border: none !important;
    background: transparent !important;
    color: var(--muted) !important;
    font-weight: 550 !important;
    border-radius: 8px !important;
    /* Taller rows with a wider gutter: a rail of destinations reads as a
       list, not as a row of buttons that happen to be stacked. */
    padding: 0.62rem 0.8rem !important;
    width: 100% !important;
    justify-content: flex-start !important;
    /* Room for the marker the active row grows on its left edge. */
    border-left: 3px solid transparent !important;
}}
.st-key-nav_page button[data-variant="segmented_control"] > div {{
    gap: 0.65rem !important;
}}
/* The button's own content wrapper centres its children, so left-aligning
   the button alone leaves the label in the middle of the row. */
.st-key-nav_page button[data-variant="segmented_control"] > div {{
    justify-content: flex-start !important;
    width: 100%;
}}
.st-key-nav_page button[data-variant="segmented_control"]:hover {{
    background: var(--nav-hover) !important;
    color: var(--ink) !important;
}}
/* The active row is marked with the brand rather than a raised card; a
   sidebar list reads better flat. */
.st-key-nav_page button[data-variant="segmented_control"][data-selected="true"] {{
    background: var(--brand-soft) !important;
    color: var(--brand) !important;
    font-weight: 650 !important;
}}

/* ---------- top bar ---------- */
/* Streamlit has no header slot, so this is a row drawn at the top of the
   main area and styled to read as one. */
.topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    height: 2.6rem;
    /* Streamlit's header is opaque and 60px tall; a bar drawn any higher
       than this is simply painted over. */
    margin: 1.1rem 0 1.4rem 0;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid var(--line);
    font-size: 0.85rem;
    color: var(--muted);
}}
.topbar .crumb {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.topbar .sep {{ opacity: 0.45; }}
.topbar .crumbs {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
}}

/* Who is signed in, at the end of the bar. The initial stands in for the
   avatar a real deployment would have; there are no uploaded pictures to
   show, and a generic silhouette says less than a letter does. */
.topbar-user {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
}}
.topbar-user .initial {{
    width: 1.7rem;
    height: 1.7rem;
    border-radius: 999px;
    background: var(--brand-soft);
    color: var(--brand);
    font-size: 0.78rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.topbar-user .name {{
    font-size: 0.82rem;
    font-weight: 550;
    color: var(--ink);
}}
.topbar-user .role {{
    font-size: 0.72rem;
    color: var(--muted);
    padding-left: 0.4rem;
    margin-left: 0.4rem;
    border-left: 1px solid var(--line);
}}
.topbar .here {{
    color: var(--ink);
    font-weight: 600;
    min-width: 0;
}}

/* ---------- sidebar as a brand rail ---------- */
/* Fixed dark in both themes: it reads as the product's frame rather than
   part of the page, which is what keeps the eye on the article. */
[data-testid="stSidebar"] {{
    background: #131A2B !important;
    border-right: 1px solid #1F2940 !important;
}}
[data-testid="stSidebar"] .side-brand {{ border-bottom-color: #263048; }}
[data-testid="stSidebar"] .side-brand .name {{ color: #F2F5FA; }}
[data-testid="stSidebar"] .side-brand .tag {{ color: #8C97AE; }}
[data-testid="stSidebar"] .side-label {{ color: #8C97AE; }}
.st-key-nav_page button[data-variant="segmented_control"] {{
    color: #A7B1C6 !important;
}}
.st-key-nav_page button[data-variant="segmented_control"]:hover {{
    background: #1C2438 !important;
    color: #F2F5FA !important;
}}
.st-key-nav_page button[data-variant="segmented_control"][data-selected="true"] {{
    background: #1F2A44 !important;
    color: #FFFFFF !important;
    border-left-color: var(--brand) !important;
}}
/* Everything the article page puts in the rail has to be legible on it. */
[data-testid="stSidebar"] [data-testid="stExpander"] details {{
    background: transparent;
    border-color: #263048;
}}
[data-testid="stSidebar"] summary,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {{
    color: #C6CEDD;
}}
[data-testid="stSidebar"] a.toc {{ color: #A7B1C6 !important; }}
[data-testid="stSidebar"] a.toc:hover {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    border-color: #2C3550 !important;
    color: #C6CEDD !important;
}}
.st-key-side_account .stButton > button {{
    border: none !important;
    color: #8C97AE !important;
    justify-content: flex-start !important;
    padding-left: 0.8rem !important;
}}
.st-key-side_account .stButton > button > div {{
    justify-content: flex-start !important;
    width: 100%;
}}
.st-key-side_account .stButton > button:hover {{
    color: #F2F5FA !important;
    background: #1C2438 !important;
}}

/* ---------- who is signed in ---------- */
.side-account {{
    padding: 0 0 0.5rem 0;
}}
.side-account .who {{
    font-size: 0.9rem;
    font-weight: 600;
    color: #F2F5FA;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.side-account .meta {{
    font-size: 0.74rem;
    color: #8C97AE;
    margin-top: 0.15rem;
}}
.side-account .sep {{ opacity: 0.5; }}

/* ---------- the aside column: contents and references ---------- */
/* The article is a tall scroll; the panels beside it stay put. */
[data-testid="stColumn"]:last-child:has(.aside-title) {{
    position: sticky;
    top: 4.5rem;
    align-self: flex-start;
}}

.aside-card {{
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--surface);
    padding: 0.9rem 1rem;
    margin-bottom: 1rem;
}}
.aside-card .aside-title {{
    font-size: 0.7rem;
    font-weight: 650;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.6rem;
}}

/* ---------- language picker, pinned beside Streamlit's menu ---------- */
.st-key-lang_selector {{
    position: fixed;
    top: 0.75rem;
    right: 3.4rem;
    /* Streamlit's header is opaque at z-index 999990 and would cover this. */
    z-index: 999991;
    width: auto !important;
}}
.st-key-lang_selector button {{
    border: 1px solid var(--line) !important;
    background: var(--surface) !important;
    color: var(--muted) !important;
    border-radius: 8px !important;
    padding: 0.3rem 0.6rem !important;
    min-height: 0 !important;
}}
.st-key-lang_selector button:hover {{
    border-color: var(--brand) !important;
    color: var(--brand) !important;
}}

/* ---------- Streamlit's own menu ---------- */
/* Screen recording has nothing to do with reading or writing an article, and
   the build stamp is for us, not for the reader. The theme switch and Print
   stay: this app's output is a long cited document people print. */
[data-testid="stMainMenuItem-recordScreencast"],
[data-testid="stMainMenuList"] + div {{
    display: none !important;
}}

/* ---------- print ---------- */
/* Printing is the article, not the application around it. */
@media print {{
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    .st-key-lang_selector,
    .st-key-nav_page,
    [data-testid="stDownloadButton"] {{
        display: none !important;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: none;
        padding: 0;
    }}
    .article-scroll [data-testid="stVerticalBlock"] {{
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
    }}
    a[href^="http"] {{ color: inherit; }}
}}

/* Hide the "Deploy"/status chrome the demo does not need. */
[data-testid="stStatusWidget"] {{ visibility: hidden; }}
</style>
"""

def apply():
    """Inject the global stylesheet. Safe to call on every rerun."""
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand():
    """Keeps the sidebar from looking abandoned on pages with no TOC."""
    st.sidebar.markdown(
        '<div class="side-brand"><div class="name">'
        '<span class="material-symbols-rounded">cyclone</span> STORM</div>'
        f'<div class="tag">{t("brand.tagline")}</div></div>',
        unsafe_allow_html=True,
    )


def top_bar(trail, name="", role=""):
    """The bar across the top of the main area: where you are, and who you are.

    `trail` is a list of labels, innermost last. Streamlit has no header of its
    own to hang this on, so it is the first thing the page draws.
    """
    crumbs = []
    for index, label in enumerate(trail):
        if index:
            crumbs.append('<span class="sep">/</span>')
        css = "here" if index == len(trail) - 1 else "crumb"
        crumbs.append(f'<span class="{css}">{label}</span>')

    identity = ""
    if name:
        role_part = f'<span class="role">{role}</span>' if role else ""
        identity = (
            f'<div class="topbar-user">'
            f'<span class="initial">{name.strip()[:1].upper()}</span>'
            f'<span class="name">{name}</span>{role_part}</div>'
        )

    st.markdown(
        f'<div class="topbar"><div class="crumbs">{"".join(crumbs)}</div>'
        f"{identity}</div>",
        unsafe_allow_html=True,
    )


def aside_title(text):
    """Heading for one of the panels in the right-hand column."""
    st.markdown(f'<div class="aside-title">{text}</div>', unsafe_allow_html=True)


def section_label(text, aside=""):
    """The hairline section marker the landing page is divided by."""
    right = f"<span>{aside}</span>" if aside else ""
    st.markdown(
        f'<div class="lp-label"><span>{text}</span>{right}</div>',
        unsafe_allow_html=True,
    )


def steps(items):
    """`items` is a sequence of (title, body); numbering is added here."""
    cells = "".join(
        f'<div class="lp-step"><span class="n">{index:02d}</span>'
        f'<div class="t">{title}</div><div class="b">{body}</div></div>'
        for index, (title, body) in enumerate(items, start=1)
    )
    st.markdown(f'<div class="lp-steps">{cells}</div>', unsafe_allow_html=True)


def page_header(title, subtitle=""):
    sub = f'<span class="sub">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="page-head"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True
    )


def hero(title, subtitle, eyebrow=""):
    brow = f'<span class="eyebrow">{eyebrow}</span>' if eyebrow else ""
    st.markdown(
        f'<div class="hero">{brow}<h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def empty_state(icon, title, body):
    """`icon` is a Material Symbols name, e.g. "library_books"."""
    st.markdown(
        f'<div class="empty">'
        f'<span class="material-symbols-rounded icon">{icon}</span>'
        f"<h3>{title}</h3><p>{body}</p></div>",
        unsafe_allow_html=True,
    )


def chips(items):
    """Pill-shaped badges — used on the article page header."""
    return "".join(f'<span class="chip">{item}</span>' for item in items)


def meta_line(items):
    """Single-line 'a · b · c' metadata, used on the article cards."""
    return '<span class="sep">·</span>'.join(items)


def humanize_date(timestamp):
    """Render a file mtime as 'today' / 'Mar 4' / 'Mar 4, 2025', translated."""
    when = datetime.fromtimestamp(timestamp)
    today = datetime.now()
    delta = (today.date() - when.date()).days
    if delta == 0:
        return t("date.today", time=f"{when:%H:%M}")
    if delta == 1:
        return t("date.yesterday")
    if delta < 7:
        return t("date.days_ago", n=delta)
    key = "date.this_year" if when.year == today.year else "date.other_year"
    return t(key, month=ui_language.month(when.month), day=when.day, year=when.year)


def measure_length(text):
    """How long an article is, as a (count, unit) pair.

    Thai, like Chinese and Japanese, does not put spaces between words, so
    splitting on whitespace would report a whole sentence as one word. For
    those scripts, count characters instead and say so.

    The pair is returned unformatted rather than as a label because the caller
    caches it, and the label depends on the interface language of the moment.
    """
    unspaced = sum(
        1
        for char in text
        if "฀" <= char <= "๿"  # Thai
        or "一" <= char <= "鿿"  # CJK
        or "぀" <= char <= "ヿ"  # kana
    )
    if unspaced > len(text) * 0.2:
        return unspaced, "chars"
    return len(text.split()), "words"


def length_label(length):
    """Turn a `measure_length` pair into '1,234 words' in the current language."""
    count, unit = length
    return t(f"length.{unit}", n=count)


@st.cache_data(show_spinner=False)
def summarize_article(article_path, url_info_path, mtime):
    """Length, source count and a short excerpt for the article cards.

    `mtime` is part of the cache key so edits on disk invalidate the entry.
    Nothing returned here is language-dependent, so the cache survives a
    switch of interface language.
    """
    length, sources, excerpt = (0, "words"), 0, ""
    if article_path and os.path.exists(article_path):
        import re

        text = open(article_path).read()
        body = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("#")
        )
        body = re.sub(r"\[\d+\]", "", body).strip()
        length = measure_length(body)
        # Strip markdown emphasis so the card preview reads as plain prose.
        plain = re.sub(r"[*_`]+", "", " ".join(body.split()))
        # Removing "[3]" leaves a space before the punctuation that followed it.
        plain = re.sub(r"\s+([.,;:])", r"\1", plain)
        excerpt = plain[:220].rsplit(" ", 1)[0] + "…"
    if url_info_path and os.path.exists(url_info_path):
        import json

        try:
            sources = len(json.load(open(url_info_path)).get("url_to_info", {}))
        except (ValueError, AttributeError):
            sources = 0
    return length, sources, excerpt
