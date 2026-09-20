"""The third engine: deep-research-web-ui, framed.

Not a library and not ours — a Nuxt application in its own container, the
shape ADR-0005 in Upstream_Deeptutor settled on for OpenMAIC. This app is
coupled to it by one URL and three query parameters, and nothing else:
providers, keys, search and storage stay on its side (`deploy/research-ui`).

The parameters are the arrangement OpenMAIC's fork learned to honour and
this one's fork will: `lang` and `theme` so the frame matches the page
around it, `embed=1` so it hides its own language and theme controls, which
would otherwise sit under this app's and announce a second application.
Read once on mount, so a change to either reloads the frame — a research run
in progress at that moment is lost. Accepted: changing language or theme is a
deliberate, infrequent act.

Upstream ignores parameters it does not know, so this works against the
publisher's image today and improves when the fork's image replaces it.
"""

from urllib.parse import urlencode

import auth
import streamlit as st
import ui_language
from ui_language import t

# Where the container answers. Overridable the way every other address is.
DEFAULT_URL = "http://localhost:3100"

# The frame's language codes for this app's language names. Upstream has no
# Thai locale yet; until the fork adds one it falls back to English, which is
# what it would have shown anyway.
LANG_CODES = {"English": "en", "ไทย": "th"}

# A pixel height is what st.iframe actually honours: "stretch" fills the
# parent, and the parent here has no height of its own, so the frame came
# out at 180px with the page empty beneath it. The CSS in ui_theme raises
# this to the viewport's remaining height; this is the floor it falls back
# to, and what a browser without CSS variables would see.
FRAME_HEIGHT = 900


def frame_url():
    """The address the frame loads, or "" when the sibling is not configured."""
    base = (auth.setting("RESEARCH_UI_URL") or DEFAULT_URL).strip().rstrip("/")
    if not base:
        return ""
    theme = "light"
    try:
        theme = "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # noqa: BLE001 - no theme context outside a real session
        pass
    query = urlencode(
        {
            "embed": "1",
            "lang": LANG_CODES.get(ui_language.current(), "en"),
            "theme": theme,
        }
    )
    return f"{base}/?{query}"


def research_ui_page():
    url = frame_url()
    if not url:
        st.info(t("research.not_configured"))
        return

    # A line above the frame, not a hero: the frame has its own heading and
    # two would be the second-application tell the embed flag exists to avoid.
    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        st.caption(t("research.frame_note"))
    with right:
        st.link_button(
            t("research.open_tab"), url, icon=":material/open_in_new:", width="stretch"
        )

    with st.container(key="research_frame"):
        st.iframe(url, height=FRAME_HEIGHT)
