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

import siblings
from pages_util import FramedSibling


def research_ui_page():
    FramedSibling.framed_page(
        siblings.RESEARCH_UI,
        note_key="research.frame_note",
        down_key="research.not_running",
        container_key="research_frame",
    )
