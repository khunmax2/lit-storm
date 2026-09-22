"""The third engine: deep-research-web-ui, framed.

Not a library and not ours — a Nuxt application in its own container, the
shape ADR-0005 in Upstream_Deeptutor settled on for OpenMAIC. This app is
coupled to it by one URL and three query parameters, and nothing else:
providers, keys, search and storage stay on its side.

The framing itself, the three parameters and the check that the container is
actually up all live in `FramedSibling` and `siblings`, shared with the
fourth engine. What is left here is which sibling this tab shows and what to
say about it.
"""

import research_sync
import siblings
import streamlit as st
from pages_util import FramedSibling
from ui_language import t


def research_ui_page():
    # Before the frame, not after: the watcher is zero height and draws
    # nothing, and putting it first means a report filed on this run is
    # announced above the frame rather than a screen below it.
    filed = research_sync.watch()
    if filed:
        st.success(t("research.synced", name=filed.replace("_", " ")))
    elif st.session_state.pop("research_sync_error", None):
        # Said once, and quietly. The report is still in the research UI and
        # can be exported and imported by hand, which is what this says.
        st.warning(t("research.sync_failed"))

    FramedSibling.framed_page(
        siblings.RESEARCH_UI,
        note_key="research.frame_note",
        down_key="research.not_running",
        container_key="research_frame",
    )
