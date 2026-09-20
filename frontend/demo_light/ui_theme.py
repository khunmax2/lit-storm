"""Shared look-and-feel for the STORM demo UI.

Everything visual that is not tied to a single page lives here: the global
stylesheet, the colour tokens the pages reference, and a couple of small
building blocks (page headers, article cards) that keep the two pages
consistent.
"""

import os
from datetime import datetime
from html import escape

import streamlit as st
import ui_language
from ui_language import t

# Colour tokens, one set per theme. Keep these in sync with the
# [theme.light] / [theme.dark] sections of .streamlit/config.toml.
LIGHT = {
    # Blue, on a slate-grey page. The rail is dark navy in this theme too —
    # in the reference the frame stays dark while the page is light, which is
    # what keeps the two reading as different surfaces.
    "brand": "#1D4ED8",
    "brand-hover": "#1E40AF",
    "brand-soft": "#E8EEFC",
    "on-brand": "#FFFFFF",
    "ink": "#0F172A",
    "muted": "#64748B",
    "line": "#E2E8F0",
    "line-strong": "#CBD5E1",
    "canvas": "#F1F5F9",
    "surface": "#FFFFFF",
    "nav-hover": "#EEF2F8",
    "shadow": "rgba(15, 23, 42, 0.16)",
    "shadow-soft": "rgba(15, 23, 42, 0.22)",
    # The rail. Same values in both themes: it is the product's frame, and
    # the reference draws it dark against a light page.
    "rail-bg": "#0D1A2D",
    "rail-bg-foot": "#102341",
    "rail-line": "#1B2C45",
    "rail-line-soft": "#1B2C45",
    "rail-ink": "#F1F5F9",
    "rail-text": "#CBD5E1",
    "rail-muted": "#94A3B8",
    "rail-nav": "#A8B5CA",
    "rail-hover": "#16283F",
    "rail-active": "#1D4ED8",
    "rail-active-ink": "#FFFFFF",
    "rail-border": "#25384F",
}


DARK = {
    # The same blue family, lightened to carry on a dark page, and the page
    # itself moved off neutral black onto the navy the rail is cut from.
    "brand": "#60A5FA",
    "brand-hover": "#93C5FD",
    "brand-soft": "rgba(96, 165, 250, 0.16)",
    # The dark-mode brand is a light blue, so it needs dark text on top.
    "on-brand": "#0B1220",
    "ink": "#E2E8F0",
    "muted": "#94A3B8",
    "line": "#1E293B",
    "line-strong": "#334155",
    "canvas": "#111A2B",
    "surface": "#131E31",
    "nav-hover": "#1A2740",
    "shadow": "rgba(0, 0, 0, 0.55)",
    "shadow-soft": "rgba(0, 0, 0, 0.6)",
    "rail-bg": "#0D1A2D",
    "rail-bg-foot": "#102341",
    "rail-line": "#1B2C45",
    "rail-line-soft": "#1B2C45",
    "rail-ink": "#F1F5F9",
    "rail-text": "#CBD5E1",
    "rail-muted": "#94A3B8",
    "rail-nav": "#A8B5CA",
    "rail-hover": "#16283F",
    "rail-active": "#1D4ED8",
    "rail-active-ink": "#FFFFFF",
    "rail-border": "#25384F",
}


# Trirong (serif) and IBM Plex Sans Thai both ship Thai *and* Latin glyphs.
# A Latin-only pairing would leave Thai text to a system fallback, so the same
# page would render in two unrelated typefaces depending on the language.
FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap');"
)

FONT_STACK = (
    '"IBM Plex Sans Thai", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    '"Helvetica Neue", Arial, sans-serif'
)

# Headings are the body face at a heavier weight and tighter tracking rather
# than a second family: the reference sets the whole interface in one sans,
# and a serif heading over a sans page read as a different product.
DISPLAY_STACK = FONT_STACK


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

    /* Layout constants the top bar is aligned against. Streamlit sets the
       rail's width inline, so it is pinned below to the same number rather
       than trusted to stay there. */
    --rail-width: 300px;
    --content-max: 1600px;
    /* Where the content column starts, measured from the rail: the block's
       own 5rem of padding, plus half of whatever slack is left once the
       block reaches its max width and centres itself. This is what puts the
       breadcrumb over the title below it. */
    --page-pad: 3.5rem;
    --gutter: max(
        var(--page-pad),
        calc(
            (100vw - var(--rail-width) - var(--content-max)) / 2
                + var(--page-pad)
        )
    );
}}
/* Collapsed rail: the same sums with no rail in them. */
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) {{
    --rail-width: 0px;
}}
/* A desktop gutter on a phone is most of the screen: 3.5rem either side of a
   375px window leaves 263px of page, which is narrower than a card. */
@media (max-width: 760px) {{
    .stApp {{
        --page-pad: 1.15rem;
    }}
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

/* The page fills the width it is given, up to a wide cap. Capped at 1180 it
   left a third of a large screen empty on either side, which the reference
   does not: there the grid grows and the gutters stay put. Long prose is
   held to its own measure by the article column instead, so widening here
   does not widen the reading line. */
[data-testid="stMainBlockContainer"] {{
    /* Clear of the 60px header the top bar is drawn into, plus a gap —
       not another header's worth of it. */
    padding-top: 5.25rem;
    padding-left: var(--page-pad);
    padding-right: var(--page-pad);
    padding-bottom: 4rem;
    max-width: var(--content-max);
}}

/* Two things in the main column draw nothing where they sit: the stylesheet
   above, and the top bar, which is fixed into Streamlit's header. Streamlit
   still lays each one out as a row and puts its 16px gap after it, so every
   page opened 32px lower than it was asked to. Taking them out of the flex
   flow costs the gap; `position: fixed` inside still resolves to the
   viewport, because absolute ancestors do not contain it. */
[data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(
    [data-testid="stMarkdownContainer"] > style:only-child
),
[data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(
    .topbar
) {{
    position: absolute;
}}

/* ---------- page header ---------- */
.page-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin: 0.4rem 0 1.9rem 0;
    padding-bottom: 1.1rem;
    border-bottom: 1px solid var(--line);
}}
.page-head h1 {{
    font-size: 1.9rem;
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
    padding: 0;
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
/* The card is the vertical block that holds the markup, matched through its
   own first child: `st.container(border=True)` puts the border on that block
   itself in this version, and there is no wrapper around it to hang this on.
   Matching `:has(.acard)` without the child path would also match every
   block the cards sit inside, the grid included. */
/* Three across, two on a tablet, one on a phone. st.columns() decides the
   count in Python, when the page renders, so it cannot answer a window that
   changes afterwards; the cards go into one flat list and this lays them
   out. */
.st-key-article_grid {{
    display: grid !important;
    /* Below the desktop breakpoint the card's own minimum decides how many
       fit — the rail can be open or shut, so the window's width does not
       actually say how much room the grid has. Two columns forced onto a
       tablet with the rail open gave 190px cards with clipped titles. */
    grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
    gap: 1.35rem;
}}
/* Streamlit wraps each card in a layout div, and that div is the grid item —
   so it is the one that has to stretch before the card's own height: 100%
   has a row height to fill. Without this a card with less in it sits 6px
   short of its neighbours and its button misses their line. */
.st-key-article_grid > [data-testid="stLayoutWrapper"] {{
    height: 100%;
}}

/* Three across on a desktop, and never four however wide the window gets. */
@media (min-width: 1181px) {{
    .st-key-article_grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
}}

[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
) {{
    position: relative;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1.25rem 1.3rem 1.15rem 1.3rem;
    height: 100%;
    /* Flat by default. A card that lifts off the page on hover reads as a
       toy; the border and a hairline of shadow are enough to say it is live. */
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
):hover {{
    border-color: var(--brand);
    box-shadow: 0 1px 3px var(--shadow-soft);
}}
/* The card is a column, and its action is the last thing in it whatever the
   title and the excerpt did with the space above. */
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
) > div,
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
) > div > [data-testid="stVerticalBlock"] {{
    height: 100%;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    [data-testid="stElementContainer"]:has(.stButton) {{
    margin-top: auto;
    /* A block container leaves a few pixels of leading under an inline-block
       button, and the amount depends on the label — so two cards in a row
       ended up with their buttons on different lines. A flex box is the
       height of what is in it. */
    display: flex;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    [data-testid="stElementContainer"]:has(.stButton) .stButton {{
    width: 100%;
    /* The button is inline-flex inside a block, so the line box around it
       reserves room for a descender under it — a few pixels that vary with
       the label, which is what knocked one card's button off its row's line. */
    display: flex;
}}
/* Keep the title fully readable; the secondary menu gets its own short row. */
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    :is(
        [data-testid="stElementContainer"], [data-testid="stLayoutWrapper"]
    ):has([data-testid="stPopover"]) {{
    position: static;
    width: fit-content;
    margin-left: auto;
    z-index: 2;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    [data-testid="stPopover"] button {{
    border: 1px solid var(--line) !important;
    background: var(--surface) !important;
    color: var(--muted) !important;
    padding: .35rem .55rem !important;
    min-height: 2.75rem !important;
    opacity: 1;
    font-size: .78rem !important;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    [data-testid="stPopover"] button:hover {{
    opacity: 1;
    color: var(--ink) !important;
    background: var(--nav-hover) !important;
}}
/* Streamlit adds a chevron after a popover's label; on a menu that is only
   its icon, the chevron is a second glyph saying the same thing. */
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
)
    [data-testid="stPopover"] button [data-testid="stIconMaterial"]:last-of-type {{
    display: none;
}}
/* The card's own action: outlined, not filled. It opens something, it does
   not commit anything. */
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
) .stButton > button {{
    min-height: 2.5rem;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--brand) !important;
}}
[data-testid="stVerticalBlock"]:has(
    > [data-testid="stElementContainer"] > [data-testid="stMarkdown"] .acard
) .stButton > button:hover:not(:disabled) {{
    background: var(--brand-soft) !important;
    border-color: var(--brand) !important;
}}
.acard .title {{
    font-size: 1.05rem;
    font-weight: 600;
    line-height: 1.35;
    color: var(--ink);
    margin-bottom: 0.5rem;
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
/* A run that never finished is a state, not a measurement, so it is set
   apart from the date and the counts rather than listed beside them. */
.acard .state {{
    display: block;
    margin-bottom: 0.6rem;
}}
.badge {{
    display: inline-block;
    font-size: 0.73rem;
    font-weight: 500;
    border-radius: 999px;
    padding: 0.2rem 0.6rem;
    line-height: 1.4;
}}
.badge.is-info {{
    color: var(--brand);
    background: var(--brand-soft);
}}
.badge.is-positive {{
    color: light-dark(#047857, #34D399);
    background: light-dark(#ECFDF5, rgba(52, 211, 153, 0.14));
}}
.badge.is-warning {{
    color: light-dark(#B45309, #FBBF24);
    background: light-dark(#FFFBEB, rgba(251, 191, 36, 0.14));
}}
.badge.is-critical {{
    color: light-dark(#B91C1C, #F87171);
    background: light-dark(#FEF2F2, rgba(248, 113, 113, 0.14));
}}
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

/* ---------- a search source's card ---------- */
[class*="st-key-src_"][class*="_chosen"] {{
    border-color: var(--brand) !important;
    box-shadow: 0 0 0 2px var(--brand-soft);
}}
.src-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.7rem;
}}
.src-head .name {{
    font-size: 1rem;
    font-weight: 600;
    color: var(--ink);
}}
/* A button that cannot be pressed has to look it. Streamlit leaves a
   disabled primary button in full brand colour, which reads as the thing to
   press next — on this page that is the button waiting for a key. */
[class*="st-key-src_"] button:disabled {{
    opacity: 0.4 !important;
    cursor: not-allowed !important;
}}
.src-head .tags {{
    display: flex;
    gap: 0.35rem;
    flex-shrink: 0;
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
    border-radius: 8px;
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
[data-testid="stBaseButton-primary"]:hover:not(:disabled),
[data-testid="stBaseButton-primaryFormSubmit"]:hover:not(:disabled) {{
    background: var(--brand-hover) !important;
    border-color: var(--brand-hover) !important;
    color: var(--on-brand) !important;
}}
[data-testid="stBaseButton-primary"]:disabled,
[data-testid="stBaseButton-primaryFormSubmit"]:disabled {{
    background: var(--brand-soft) !important;
    border-color: var(--line) !important;
    color: var(--muted) !important;
    cursor: not-allowed;
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
/* Keyboard focus must remain visible on every action, including compact
   menus and controls inside dialogs. */
.stApp button:focus-visible,
.stApp a:focus-visible,
.stApp [role="tab"]:focus-visible,
.stApp [role="radio"]:focus-visible {{
    outline: 3px solid var(--brand) !important;
    outline-offset: 2px;
}}
.stApp button:not(:disabled) {{ cursor: pointer; }}
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
/* The collapse button uses the right-hand end of a strip Streamlit reserves
   across the whole rail, so the brand was pushed below an otherwise empty
   row. The two belong on one line: the strip keeps its height for the
   button, and the content below is pulled back up over it. Raising the
   strip keeps the button clickable through the brand, which is not. */
[data-testid="stSidebarHeader"] {{
    height: 2.25rem;
    padding-top: 0.25rem;
    padding-bottom: 0;
    margin-bottom: 0 !important;
    position: relative;
    z-index: 2;
}}
[data-testid="stSidebarUserContent"] {{
    padding-top: 0.25rem;
    margin-top: -2rem;
    /* Streamlit reserves 6rem under the rail's content for a scroll that a
       column pinned to the viewport never has, which left the account
       block floating short of the foot. */
    padding-bottom: 1rem;
}}

/* The rail is a column: navigation at the top, the account at the foot.
   Streamlit wraps a keyed container in a stLayoutWrapper, so the margin has
   to go on that wrapper — it is the flex child, not the container itself. */
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(
    > [data-testid="stLayoutWrapper"] > .st-key-side_account
) {{
    min-height: calc(100vh - 1.5rem);
}}
[data-testid="stLayoutWrapper"]:has(> .st-key-side_account) {{
    margin-top: auto !important;
}}
/* The container is only the anchor that holds the foot of the rail; the
   panel is drawn around the identity inside it, so that Sign out can sit
   below the panel and line up with the menu, as it does in the reference. */
.st-key-side_account {{
    padding: 0;
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

/* ---------- the article as a sheet ---------- */
/* The reference sets the article on a white card rather than straight onto
   the page, with the contents and the references as two more cards beside
   it. Three panels, one shape. */
.st-key-article_card,
.st-key-toc_card,
.st-key-refs_card {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: 0 1px 2px var(--shadow-soft);
}}
.st-key-article_card {{
    padding: 2rem 2.4rem 1.4rem 2.4rem;
}}
.st-key-toc_card,
.st-key-refs_card {{
    padding: 1.3rem 1.4rem;
}}
.st-key-refs_card {{
    margin-top: 1rem;
}}
/* The rule under the title block, spanning the card's own measure. */
.article-rule {{
    height: 1px;
    background: var(--line);
    margin: 1.4rem 0 0.4rem 0;
}}

/* The badges under the title: icon then figure, as in the reference. */
.article-head .meta .chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--canvas);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.34rem 0.75rem;
    font-size: 0.79rem;
}}
.article-head .meta .chip .material-symbols-rounded {{
    font-size: 1rem !important;
    color: var(--muted);
}}

/* ---------- article body ---------- */
.article-head {{
    margin: 0.5rem 0 1.4rem 0;
}}
.article-head h1 {{
    padding: 0;
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

/* The article's card sets the measure, as the reference's does: at the sizes
   this is read at the text fills the card. The cap is a backstop for a very
   wide screen — measured rather than guessed, an average character is 7.15px
   at this face and size, so 40rem is about 89 of them. It is a cap and not
   the measure because the reference runs longer lines than a cap of 75 would
   allow, and a card with text down one side of it looks broken. */
.st-key-article_text [data-testid="stMarkdownContainer"] {{
    max-width: 40rem;
}}

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
/* Mark and wordmark on one line, the role beneath the name — the reference
   sets them as a lockup rather than as a heading with a sentence under it. */
.side-brand {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.1rem 0 1.1rem 0;
    margin-bottom: 1.1rem;
    border-bottom: 1px solid var(--rail-line-soft);
}}
.side-brand .mark {{
    font-size: 2.6rem !important;
    line-height: 1;
    color: var(--rail-ink);
    flex-shrink: 0;
}}
.side-brand .words {{
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    min-width: 0;
}}
.side-brand .name {{
    font-size: 1.12rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--rail-ink);
}}
.side-brand .tag {{
    font-size: 0.76rem;
    color: var(--rail-muted);
    margin-top: 0.1rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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

/* ---------- grouped sidebar navigation ---------- */
.st-key-nav_main, .st-key-nav_manage {{
    width: 100% !important;
    margin: 0 0 1.1rem;
}}
.st-key-nav_main [data-testid="stButtonGroup"],
.st-key-nav_manage [data-testid="stButtonGroup"] {{
    display: flex;
    width: 100%;
}}
.st-key-nav_main [data-testid="stButtonGroup"] > div,
.st-key-nav_manage [data-testid="stButtonGroup"] > div {{
    display: flex;
    flex-direction: column;
    max-width: none;
    flex: 1 1 auto;
    align-items: stretch;
    gap: 0.45rem;
    background: transparent;
    border: none;
    padding: 0;
}}
.st-key-nav_main button[data-variant="segmented_control"],
.st-key-nav_manage button[data-variant="segmented_control"] {{
    border: 0 !important;
    border-radius: 10px !important;
    background: transparent !important;
    color: var(--rail-nav) !important;
    min-height: 3.2rem !important;
    height: auto !important;
    padding: 0.72rem 1rem !important;
    width: 100% !important;
    font-size: 0.98rem !important;
    font-weight: 550 !important;
    justify-content: flex-start !important;
}}
.st-key-nav_main button[data-variant="segmented_control"] > div,
.st-key-nav_manage button[data-variant="segmented_control"] > div {{
    justify-content: flex-start !important;
    width: 100%;
    gap: 0.9rem !important;
}}
.st-key-nav_main button[data-variant="segmented_control"] [data-testid*="Icon"],
.st-key-nav_manage button[data-variant="segmented_control"] [data-testid*="Icon"] {{
    font-size: 1.35rem !important;
    width: 1.35rem;
}}
.st-key-nav_main button[data-variant="segmented_control"]:hover,
.st-key-nav_manage button[data-variant="segmented_control"]:hover {{
    background: var(--rail-hover) !important;
    color: var(--rail-ink) !important;
}}
.st-key-nav_main button[data-variant="segmented_control"][data-selected="true"],
.st-key-nav_manage button[data-variant="segmented_control"][data-selected="true"] {{
    background: #f8fbff !important;
    color: #1651d6 !important;
    font-weight: 700 !important;
    box-shadow: inset 4px 0 #2461e9, 0 4px 16px rgba(0,0,0,.1);
}}
.st-key-nav_main button[data-variant="segmented_control"][data-selected="true"] [data-testid*="Icon"],
.st-key-nav_manage button[data-variant="segmented_control"][data-selected="true"] [data-testid*="Icon"] {{
    color: #1651d6 !important;
}}
[data-testid="stSidebar"] .side-label {{
    color: var(--rail-muted);
    font-size: 0.8rem;
    font-weight: 650;
    letter-spacing: .03em;
    padding: .35rem .8rem .45rem;
}}
[data-testid="stSidebar"] .side-group-management {{
    border-top: 1px solid var(--rail-line-soft);
    margin-top: .3rem;
    padding-top: 1.3rem;
}}

/* ---------- top bar ---------- */
/* Streamlit's header is the only band that already spans the main area and
   follows the rail when it collapses, so the bar is that band: the header
   gets the edge, and the breadcrumb is placed into it. Drawn in the page
   instead, as it was, it sat in the content's own column and read as the
   first line of the article rather than as the frame around it.

   It is laid over the header rather than inside it — Streamlit gives no way
   in — so it takes no clicks, and keeps clear of the buttons at the far
   right. */
[data-testid="stHeader"] {{
    border-bottom: 1px solid var(--line);
}}
@media (min-width: 769px) {{
    [data-testid="stSidebar"] {{
        width: var(--rail-width) !important;
        min-width: var(--rail-width) !important;
        max-width: var(--rail-width) !important;
    }}
}}
/* Who you are, against the right-hand end of the band and clear of the
   language and menu buttons that live there. Text only, so it takes no
   clicks away from them. */
.topbar {{
    position: fixed;
    top: 0;
    right: 9.5rem;
    /* The header's own height. Taller and the bar draws past its edge. */
    height: 60px;
    z-index: 999992;
    pointer-events: none;
    display: flex;
    align-items: center;
    font-size: 0.85rem;
    color: var(--muted);
}}
/* The trail, against the left-hand end. Fixed, so Streamlit's column never
   lays it out or spends a gap on it. */
.st-key-crumbs {{
    position: fixed !important;
    top: 0;
    left: calc(var(--rail-width) + var(--gutter));
    height: 60px;
    z-index: 999992;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 0.35rem !important;
    max-width: calc(100vw - var(--rail-width) - var(--gutter) - 16rem);
    overflow: hidden !important;
}}
/* Every crumb but the first is preceded by a separator drawn here rather
   than written into the row, so it belongs to no button and takes no click. */
.st-key-crumbs
    > [data-testid="stElementContainer"]
    + [data-testid="stElementContainer"]::before {{
    content: "/";
    align-self: center;
    padding: 0 0.45rem;
    color: var(--muted);
    opacity: 0.45;
    font-size: 0.85rem;
}}
/* Crumbs keep their own width — allowed to shrink, Streamlit's button box
   comes up a hair short of its label and clips the last letter. The strip
   clips instead, at its own edge, if a title is long enough to run into the
   identity. */
.st-key-crumbs > [data-testid="stElementContainer"] {{
    display: flex !important;
    align-items: center !important;
    flex: 0 0 auto !important;
}}
/* A crumb is a link that happens to be a button: it should read as the text
   around it until you go near it. */
.st-key-crumbs .stButton > button {{
    border: none !important;
    background: transparent !important;
    color: var(--muted) !important;
    font-size: 0.85rem !important;
    font-weight: 400 !important;
    min-height: 0 !important;
    padding: 0.2rem 0.35rem !important;
    margin: 0 -0.35rem !important;
    border-radius: 6px !important;
    white-space: nowrap !important;
}}
.st-key-crumbs .stButton > button:hover:not(:disabled) {{
    color: var(--ink) !important;
    background: var(--nav-hover) !important;
}}
/* The page you are on: still a crumb, but the end of the trail. */
.st-key-crumbs .stButton > button:disabled {{
    color: var(--ink) !important;
    font-weight: 600 !important;
    opacity: 1 !important;
    cursor: default !important;
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
    gap: 0.6rem;
    flex-shrink: 0;
}}
.topbar-user .initial {{
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    background: var(--brand);
    color: var(--on-brand);
    font-size: 0.82rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    justify-content: center;
}}
/* Name over role rather than side by side, as in the reference: two short
   words on one line read as one long one. */
.topbar-user .who {{
    display: flex;
    flex-direction: column;
    line-height: 1.25;
}}
.topbar-user .name {{
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--ink);
}}
.topbar-user .role {{
    font-size: 0.72rem;
    color: var(--muted);
}}
.topbar .here {{
    color: var(--ink);
    font-weight: 600;
    min-width: 0;
}}
/* On a phone the rail is an overlay rather than a column, so the trail has
   no rail to sit beside — and it has to clear the button that opens it. Who
   you are is in the rail already; at this width the trail is worth more. */
@media (max-width: 768px) {{
    .st-key-crumbs {{
        left: 3.5rem !important;
        max-width: calc(100vw - 10.5rem) !important;
    }}
    .topbar {{ display: none !important; }}
    /* The trail is laid over Streamlit's header, which puts it above the
       rail as well; here the rail is an overlay and should cover it. */
    .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-crumbs {{
        display: none !important;
    }}
}}

/* ---------- dev-mode strip ---------- */
/* Deliberately ugly. It marks a build whose sign-in is switched off, and it
   should never be mistaken for part of the product. */
.dev-strip {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.6rem 0 0 0;
    padding: 0.4rem 0.7rem;
    border: 1px solid #B45309;
    border-left: 4px solid #B45309;
    border-radius: 6px;
    background: light-dark(#FEF3C7, #3B2A08);
    color: light-dark(#7C2D12, #FCD34D);
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.01em;
}}
.dev-strip .who {{
    font-weight: 500;
    opacity: 0.85;
}}

/* ---------- sidebar as a brand rail ---------- */
/* A surface of its own, on its own ramp, in whichever theme is running: the
   rail should read as the product's frame rather than as part of the page,
   and it was pinned dark to get that. Pinned, it stayed black behind a light
   page. The `--rail-*` tokens say the same thing in both themes instead. */
[data-testid="stSidebar"] {{
    /* Not flat: the reference lifts very slightly towards the foot, which
       keeps a tall rail from reading as a cut-out. */
    background: linear-gradient(
        180deg, var(--rail-bg) 0%, var(--rail-bg-foot) 100%
    ) !important;
    border-right: 1px solid var(--rail-line) !important;
}}
[data-testid="stSidebar"] .side-brand {{
    border-bottom-color: var(--rail-line-soft);
}}
[data-testid="stSidebar"] .side-brand .name {{ color: var(--rail-ink); }}
[data-testid="stSidebar"] .side-brand .tag {{ color: var(--rail-muted); }}
[data-testid="stSidebar"] .side-label {{ color: var(--rail-muted); }}
/* Everything the article page puts in the rail has to be legible on it. */
[data-testid="stSidebar"] [data-testid="stExpander"] details {{
    background: transparent;
    border-color: var(--rail-line-soft);
}}
[data-testid="stSidebar"] summary,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {{
    color: var(--rail-text);
}}
[data-testid="stSidebar"] a.toc {{ color: var(--rail-nav) !important; }}
[data-testid="stSidebar"] a.toc:hover {{ color: var(--rail-ink) !important; }}
[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    border-color: var(--rail-border) !important;
    color: var(--rail-text) !important;
}}
/* Below the panel and lined up with the menu, not inside the panel: it is
   an action on the rail, not a field of the account. */
.st-key-side_account .stButton > button {{
    border: none !important;
    background: transparent !important;
    color: var(--rail-muted) !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    border-radius: 10px !important;
    padding: 0.72rem 1.05rem !important;
    justify-content: flex-start !important;
}}
.st-key-side_account .stButton > button > div {{
    justify-content: flex-start !important;
    gap: 0.9rem !important;
    width: 100%;
}}
.st-key-side_account .stButton > button [data-testid*="Icon"] {{
    font-size: 1.35rem !important;
    width: 1.35rem;
}}
.st-key-side_account .stButton > button:hover {{
    color: var(--rail-ink) !important;
    background: var(--rail-hover) !important;
}}

/* ---------- who is signed in ---------- */
.side-account {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1.5rem 0.9rem;
    background: var(--rail-hover);
    border: 1px solid var(--rail-border);
    border-radius: 12px;
    margin-bottom: 0.35rem;
}}
.side-account .avatar {{
    width: 2.1rem;
    height: 2.1rem;
    border-radius: 999px;
    background: var(--brand);
    color: var(--on-brand);
    font-size: 0.85rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.side-account .who {{
    display: flex;
    flex-direction: column;
    line-height: 1.25;
    min-width: 0;
}}
.side-account .name {{
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--rail-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.side-account .meta {{
    font-size: 0.73rem;
    color: var(--rail-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.side-account .sep {{ opacity: 0.5; }}

/* ---------- the aside column: contents and references ---------- */
/* The article is a tall scroll; the panels beside it stay put. */
[data-testid="stColumn"]:last-child:has(.aside-title) {{
    position: sticky;
    top: 4.5rem;
    align-self: flex-start;
}}

/* The panel headings carry a mark, and the contents are bulleted the way
   the reference bullets them: a filled dot for a section, a ring for what
   sits under one. */
.aside-title .material-symbols-rounded {{
    font-size: 1.15rem !important;
    color: var(--brand);
    margin-right: 0.5rem;
    vertical-align: -0.2rem;
}}
.st-key-toc_card ul {{
    list-style: none;
    padding-left: 0;
    margin: 0.2rem 0 0 0;
}}
.st-key-toc_card li {{
    position: relative;
    padding-left: 1.15rem;
    margin: 0.5rem 0;
}}
.st-key-toc_card li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--brand);
}}
.st-key-toc_card ul ul {{
    padding-left: 1.1rem;
    margin: 0.35rem 0;
}}
.st-key-toc_card ul ul li::before {{
    background: transparent;
    border: 1.5px solid var(--line-strong);
}}
/* The one button in the references panel, and the way the reference draws
   it: quiet, filled with the brand at its lightest. */
.st-key-refs_open button {{
    background: var(--brand-soft) !important;
    border-color: transparent !important;
    color: var(--brand) !important;
    font-weight: 550 !important;
}}
.st-key-refs_open button:hover {{
    border-color: var(--brand) !important;
}}
.dialog-head {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 0.9rem;
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

/* ---------- member management dashboard ---------- */
.st-key-admin_dashboard {{
    padding: 1.35rem 1.45rem 1.7rem;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: var(--surface);
    box-shadow: 0 10px 36px -30px var(--shadow-soft);
}}
.st-key-admin_dashboard h1 {{
    font-size: 2rem;
    letter-spacing: -.025em;
    margin: 0;
    color: var(--ink);
}}
.st-key-admin_dashboard [data-testid="stCaptionContainer"] {{
    color: var(--muted);
}}
.st-key-admin_stat_total,
.st-key-admin_stat_active,
.st-key-admin_stat_suspended {{
    border: 1px solid var(--line);
    border-radius: 13px;
    padding: 1.1rem 1.2rem;
    min-height: 9.4rem;
}}
.st-key-admin_stat_total {{ background: light-dark(#f7faff, #182843); border-color: light-dark(#dbe8ff, #294267); }}
.st-key-admin_stat_active {{ background: light-dark(#f4fdfb, #12352f); border-color: light-dark(#ccefe7, #286052); }}
.st-key-admin_stat_suspended {{ background: light-dark(#fff8f9, #35212b); border-color: light-dark(#ffdde2, #75414d); }}
.admin-stat-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.7rem;
    height: 2.7rem;
    border-radius: 10px;
    font-size: 1.45rem !important;
    background: light-dark(#e7efff, #234171);
    color: light-dark(#1651d6, #8fbaff);
}}
.st-key-admin_stat_active .admin-stat-icon {{ background: light-dark(#dcf8ef, #174d3d); color: light-dark(#07936a, #56dab0); }}
.st-key-admin_stat_suspended .admin-stat-icon {{ background: light-dark(#ffe6e9, #5e303e); color: light-dark(#e2273a, #ff8998); }}
.admin-stat-number {{
    display: block;
    font-size: 1.9rem;
    line-height: 1.1;
    color: var(--ink);
    margin: .18rem 0;
}}
.st-key-admin_dashboard [data-testid="stTabs"] {{ margin-top: 1rem; }}
.st-key-admin_dashboard [data-testid="stTab"] {{ font-weight: 600; }}
.st-key-admin_roster_table {{
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
}}
.st-key-admin_roster_header {{
    background: light-dark(#f8fbff, #1a2940);
    border-bottom: 1px solid var(--line);
    padding: .35rem .85rem;
}}
.st-key-admin_roster_header [data-testid="stCaptionContainer"] {{
    color: var(--muted);
    font-weight: 700;
}}
.mobile-cell-label {{ display: none; }}
[class*="st-key-admin_roster_row_"] {{
    border-bottom: 1px solid var(--line);
    padding: .72rem .85rem;
}}
[class*="st-key-admin_roster_row_"]:last-child {{ border-bottom: 0; }}
[class*="st-key-admin_roster_row_"] [data-testid="stProgress"] {{ margin-top: -.35rem; }}
[class*="st-key-admin_roster_row_"] [data-testid="stProgress"] > div {{ height: .42rem; }}
.member-identity {{
    display: flex;
    align-items: center;
    gap: .7rem;
    min-width: 0;
}}
.member-identity > span:last-child {{ min-width: 0; }}
.member-identity strong {{
    display: block;
    color: var(--ink);
    font-size: .94rem;
    line-height: 1.25;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.member-identity small {{
    display: block;
    color: var(--muted);
    font-size: .77rem;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.member-avatar {{
    display: grid;
    place-items: center;
    flex: 0 0 2.4rem;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 50%;
    background: #1d4ed8;
    color: white;
    font-weight: 700;
}}
[class*="st-key-admin_roster_row_"] [data-testid="stPopover"] button {{
    min-height: 2.75rem;
    padding: .35rem .5rem;
    font-size: .82rem;
}}
@media (max-width: 1450px) {{
    .st-key-admin_dashboard {{ padding: 1rem; }}
    .st-key-admin_roster_header {{ display: none; }}
    [class*="st-key-admin_roster_row_"] {{ position: relative; padding: 1.05rem; }}
    [class*="st-key-admin_roster_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .85rem 1.15rem;
        align-items: start;
    }}
    [class*="st-key-admin_roster_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
        width: auto !important;
        min-width: 0 !important;
        flex: none !important;
    }}
    [class*="st-key-admin_roster_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child,
    [class*="st-key-admin_roster_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) {{
        grid-column: 1 / -1;
    }}
    [class*="st-key-admin_roster_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
        position: absolute;
        right: 0;
        top: 0;
    }}
    .member-identity {{ padding-right: 6rem; }}
    .mobile-cell-label {{ display: block; color: var(--muted); font-size: .78rem; font-weight: 600; margin-bottom: .2rem; }}
    [class*="st-key-admin_roster_row_"] [data-testid="stProgress"] {{ margin-top: 0; }}
}}
@media (max-width: 760px) {{
    .st-key-admin_dashboard {{ padding: .85rem; }}
    .st-key-admin_stat_total,
    .st-key-admin_stat_active,
    .st-key-admin_stat_suspended {{
        min-height: 0;
        padding: .75rem;
        display: grid;
        grid-template-columns: 2.7rem minmax(0, 1fr) auto;
        grid-template-rows: auto auto;
        column-gap: .7rem;
        row-gap: .1rem;
        align-items: center;
    }}
    [class*="st-key-admin_stat_"] > [data-testid="stElementContainer"]:first-child {{ grid-column: 1; grid-row: 1 / 3; }}
    [class*="st-key-admin_stat_"] > [data-testid="stElementContainer"]:nth-child(2) {{ grid-column: 2; grid-row: 1; }}
    [class*="st-key-admin_stat_"] > [data-testid="stElementContainer"]:nth-child(3) {{ grid-column: 3; grid-row: 1 / 3; }}
    [class*="st-key-admin_stat_"] > [data-testid="stElementContainer"]:nth-child(4) {{ grid-column: 2; grid-row: 2; }}
    .admin-stat-number {{ font-size: 1.45rem; }}
}}

/* ---------- print ---------- */
/* Printing is the article, not the application around it. */
@media print {{
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    .st-key-lang_selector,
    .st-key-nav_main,
    .st-key-nav_manage,
    [data-testid="stDownloadButton"] {{
        display: none !important;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: none;
        padding: 0;
    }}
    .st-key-article_text [data-testid="stVerticalBlock"] {{
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
        '<div class="side-brand">'
        '<span class="mark material-symbols-rounded">cyclone</span>'
        '<span class="words"><span class="name">STORM</span>'
        f'<span class="tag">{t("brand.role")}</span></span></div>',
        unsafe_allow_html=True,
    )


def top_bar(trail, name="", role=""):
    """The bar across the top of the main area: where you are, and who you are.

    `trail` is a list of labels, innermost last. Every label but the last is a
    button, because that is what a breadcrumb is: the trail is the way back,
    and one that cannot be walked is decoration. Returns the index of the
    crumb that was clicked, or None.

    The two halves are placed separately — the trail against the content
    column on the left, the identity against the buttons on the right — so
    neither has to know the other's width.
    """
    clicked = None
    last = len(trail) - 1
    with st.container(
        key="crumbs", horizontal=True, vertical_alignment="center", gap=None
    ):
        # Every crumb is a button, the current page's one disabled. A row of
        # one kind of element lines itself up; mixing text in left it sitting
        # low, because Streamlit gives text in a horizontal container a fixed
        # height of its own. The separators are drawn by CSS, so they stay out
        # of the buttons' hit areas.
        for index, label in enumerate(trail):
            if st.button(
                label,
                key=f"crumb_{index}",
                type="tertiary",
                disabled=index == last,
            ):
                clicked = index

    if name:
        role_part = f'<span class="role">{escape(role)}</span>' if role else ""
        safe_name = escape(name)
        st.markdown(
            f'<div class="topbar"><div class="topbar-user">'
            f'<span class="initial">{escape(name.strip()[:1].upper())}</span>'
            f'<span class="who"><span class="name">{safe_name}</span>'
            f"{role_part}</span></div></div>",
            unsafe_allow_html=True,
        )
    return clicked


def dev_banner(who=""):
    """Say, on every page, that this build is not asking anyone to sign in."""
    detail = f'<span class="who">signed in as {escape(who)}</span>' if who else ""
    st.markdown(
        f'<div class="dev-strip"><span>DEV MODE — sign-in bypassed</span>'
        f"{detail}</div>",
        unsafe_allow_html=True,
    )


def aside_title(text, icon=""):
    """Heading for one of the panels in the right-hand column."""
    mark = (
        f'<span class="material-symbols-rounded">{escape(icon)}</span>' if icon else ""
    )
    st.markdown(
        f'<div class="aside-title">{mark}{escape(text)}</div>', unsafe_allow_html=True
    )


def section_label(text, aside=""):
    """The hairline section marker the landing page is divided by."""
    right = f"<span>{escape(aside)}</span>" if aside else ""
    st.markdown(
        f'<div class="lp-label"><span>{escape(text)}</span>{right}</div>',
        unsafe_allow_html=True,
    )


def steps(items):
    """`items` is a sequence of (title, body); numbering is added here."""
    cells = "".join(
        f'<div class="lp-step"><span class="n">{index:02d}</span>'
        f'<div class="t">{escape(title)}</div><div class="b">{escape(body)}</div></div>'
        for index, (title, body) in enumerate(items, start=1)
    )
    st.markdown(f'<div class="lp-steps">{cells}</div>', unsafe_allow_html=True)


def page_header(title, subtitle=""):
    sub = f'<span class="sub">{escape(subtitle)}</span>' if subtitle else ""
    st.markdown(
        f'<div class="page-head"><h1>{escape(title)}</h1>{sub}</div>', unsafe_allow_html=True
    )


def hero(title, subtitle, eyebrow=""):
    brow = f'<span class="eyebrow">{escape(eyebrow)}</span>' if eyebrow else ""
    st.markdown(
        f'<div class="hero">{brow}<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def empty_state(icon, title, body):
    """`icon` is a Material Symbols name, e.g. "library_books"."""
    st.markdown(
        f'<div class="empty">'
        f'<span class="material-symbols-rounded icon">{escape(icon)}</span>'
        f"<h3>{escape(title)}</h3><p>{escape(body)}</p></div>",
        unsafe_allow_html=True,
    )


def chips(items):
    """Pill-shaped badges — used on the article page header.

    An item is either a label or an (icon, label) pair; the icon is a
    Material Symbols ligature name.
    """
    out = []
    for item in items:
        if isinstance(item, tuple):
            icon, label = item
            out.append(
                f'<span class="chip">'
                f'<span class="material-symbols-rounded">{escape(icon)}</span>{escape(label)}</span>'
            )
        else:
            out.append(f'<span class="chip">{escape(item)}</span>')
    return "".join(out)


BADGE_TONES = ("info", "positive", "warning", "critical")


def badge(text, tone="info"):
    """A small pill for a card's state.

    The library has one state to show today — a run that stopped before it
    wrote anything — but the tone is a parameter so the next one is a word
    rather than another rule.
    """
    if tone not in BADGE_TONES:
        raise ValueError(f"unknown badge tone: {tone}")
    return f'<span class="badge is-{tone}">{escape(text)}</span>'


@st.cache_data(show_spinner=False)
def read_text(path, mtime):
    """File contents, cached on the path and its modification time.

    The cards offer the article as a download, and re-reading every one of
    them on every rerun of the library is the kind of cost that only shows up
    once somebody has a hundred articles.
    """
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def meta_line(items):
    """Single-line 'a · b · c' metadata, used on the article cards."""
    return '<span class="sep">·</span>'.join(escape(item) for item in items)


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
