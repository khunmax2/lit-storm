"""Drawing a framed sibling, once, for both of them.

Deep Research and the agents researcher differ in what they do and in the
words around them; how they are framed is identical. Keeping that in one
place is why the health check is on both — the first version of this lived
inside the Deep Research tab and simply was not written for the second.

Before the frame goes in, the sibling is asked whether it is up. Without
that the iframe loads a browser error page — "this site can't be reached",
in the browser's language, inside our layout — and it reads as this app
being broken rather than a container being stopped.
"""

import siblings
import streamlit as st
import ui_theme
from ui_language import t


def framed_page(sibling, note_key, down_key, container_key):
    """One sibling's tab: a line, a way out, and the frame — if it is up."""
    url = siblings.frame_url(sibling)
    if not url:
        st.info(t(f"{sibling.name}.not_configured"))
        return

    up, detail = siblings.reachable(sibling)
    if not up:
        st.warning(t(down_key))
        # The probe's own words, for whoever is fixing it: "ConnectionError"
        # and "404" send you to different places.
        st.caption(t("sibling.probe_said", detail=detail, url=sibling.internal_url()))
        if st.button(t("sibling.retry"), key=f"retry_{sibling.name}"):
            siblings._probe.clear()
            st.rerun()
        return

    # A line above the frame, not a hero: the frame has its own heading and
    # two would be the second-application tell the embed flag exists to avoid.
    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        st.caption(t(note_key))
    with right:
        st.link_button(
            t("research.open_tab"), url, icon=":material/open_in_new:", width="stretch"
        )

    with st.container(key=container_key):
        st.iframe(url, height=siblings.FRAME_HEIGHT)
