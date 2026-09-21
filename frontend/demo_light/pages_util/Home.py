"""The front door: pick how the research should happen, then get out of the way.

STORM and Co-STORM answer the same request — "tell me about X" — in two
different ways, and which one somebody wants is a property of the afternoon
rather than of the app. So they share this page and a switch, instead of being
two entries in the navigation where the difference would have to be guessed
from the words "Round table".

Work already under way owns the page and the switch is not drawn. It is not a
way to change your mind at that point; it is a way to lose a discussion that
cost ten minutes and a good deal of API credit.
"""

import demo_util
import streamlit as st
from pages_util import AgentsResearch, CreateNewArticle, ResearchUI, RoundTable
from ui_language import t

# Not prefixed with "page", so the choice survives a walk to the library and
# back — `clear_other_page_session_state` only sweeps keys that begin with it.
ENGINE_KEY = "home_engine"

STORM = "storm"
COSTORM = "costorm"
RESEARCH = "research"
AGENTS = "agents"

# icon, label, and the line under the switch that says what you are choosing.
ENGINES = {
    STORM: (":material/auto_stories:", "home.engine_storm", "home.engine_storm_note"),
    COSTORM: (":material/forum:", "home.engine_costorm", "home.engine_costorm_note"),
    # Sibling applications framed in, not engines of this app's: each has
    # its own models, its own search and its own history. See ResearchUI and
    # AgentsResearch.
    RESEARCH: (":material/travel_explore:", "home.engine_research", "home.engine_research_note"),
    AGENTS: (":material/account_tree:", "home.engine_agents", "home.engine_agents_note"),
}


def _engine():
    """Which engine the page is showing. Always one of `ENGINES`."""
    # A segmented control can be deselected by clicking the live option, which
    # leaves None behind; the article writer is the answer to "neither".
    chosen = st.session_state.get(ENGINE_KEY)
    return chosen if chosen in ENGINES else STORM


def _switch():
    """The choice, drawn where the hero's eyebrow used to be."""
    st.session_state.setdefault(ENGINE_KEY, STORM)
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.segmented_control(
            t("home.engine_label"),
            list(ENGINES),
            format_func=lambda name: f"{ENGINES[name][0]} {t(ENGINES[name][1])}",
            key=ENGINE_KEY,
            label_visibility="collapsed",
            width="stretch",
        )
        st.markdown(
            f'<div class="lp-note" style="margin-top:.35rem">'
            f"{t(ENGINES[_engine()][2])}</div>",
            unsafe_allow_html=True,
        )


def home_page():
    demo_util.clear_other_page_session_state(page_index=3)

    # Whichever one is mid-flight keeps the page, whatever the switch says.
    # Co-STORM is asked first: its state outlives navigation, so a discussion
    # left open is the thing most likely to be come back to.
    if RoundTable.busy():
        RoundTable.round_table_page()
        return
    if CreateNewArticle.busy():
        CreateNewArticle.create_new_article_page()
        return

    _switch()
    engine = _engine()
    if engine == COSTORM:
        RoundTable.round_table_page()
    elif engine == RESEARCH:
        ResearchUI.research_ui_page()
    elif engine == AGENTS:
        AgentsResearch.agents_research_page()
    else:
        CreateNewArticle.create_new_article_page()
