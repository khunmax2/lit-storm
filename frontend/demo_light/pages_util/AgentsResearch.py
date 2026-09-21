"""The fourth engine: agents-deep-research, framed.

A third-party research library — qx-labs/agents-deep-research, Apache-2.0 —
which plans a report, researches each part in a loop until it stops finding
gaps, and writes it up. It answers the same request as the other three and
gets there a fourth way, which is the whole reason it is here.

Upstream is a library and a CLI with no web surface at all, so our copy adds
one in `web/`: a page, a progress feed and the report. That is the only
difference from the third engine's arrangement — the coupling is the same
URL and the same three parameters, and its models, search and history stay
on its side.
"""

import siblings
from pages_util import FramedSibling


def agents_research_page():
    FramedSibling.framed_page(
        siblings.AGENTS_RESEARCH,
        note_key="agents.frame_note",
        down_key="agents.not_running",
        container_key="agents_frame",
    )
