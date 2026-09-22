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
    # Not in a middle column. `st.columns([1, 2, 1])` handed the switch a
    # fixed half of the page, and four labels with their icons want 536px:
    # at a 1400px window the row was given 478 and "Agent Research" was cut
    # to "Agent R" — inside a scroller with nothing to say it scrolled, so
    # the fourth engine simply looked like it had a short name. A fraction
    # of the page cannot know what is being put into it. The stylesheet
    # centres the row instead and lets it be its own width, and wrap when
    # the window cannot hold it on one line.
    st.segmented_control(
        t("home.engine_label"),
        list(ENGINES),
        format_func=lambda name: f"{ENGINES[name][0]} {t(ENGINES[name][1])}",
        key=ENGINE_KEY,
        label_visibility="collapsed",
    )
    st.markdown(
        f'<div class="lp-note" style="margin-top:.35rem">'
        f"{t(ENGINES[_engine()][2])}</div>",
        unsafe_allow_html=True,
    )
    # A discussion the reader has walked away from is still running up a
    # knowledge base and still costing what it cost. Now that leaving is
    # allowed, say that it is there — otherwise it is state nothing on
    # screen accounts for, and the way back is a guess.
    if RoundTable.busy() and _engine() != COSTORM:
        _, middle, _ = st.columns([1, 3, 1])
        with middle:
            if st.button(
                t("home.discussion_open"),
                icon=":material/forum:",
                width="stretch",
                type="tertiary",
            ):
                st.session_state[ENGINE_KEY] = COSTORM
                st.rerun()


def home_page():
    demo_util.clear_other_page_session_state(page_index=3)

    # A STORM run owns the page for as long as it lasts. Its state is a
    # `page3_` key, so walking away is already how you abandon one, and
    # there is no discussion to come back to.
    if CreateNewArticle.busy():
        CreateNewArticle.create_new_article_page()
        return

    # A discussion is not the same thing, and treating it as one took the
    # page away. Co-STORM state is deliberately not a `page_` key so that a
    # discussion survives a walk to the library — but this asked
    # `RoundTable.busy()`, which is true for as long as a discussion exists,
    # and so the switch was never drawn again. The reader was left in a room
    # with one door marked "start a new discussion", which discards the one
    # they were in. That is a strange thing to insist on for state a browser
    # refresh loses anyway.
    #
    # Now only work actually in flight holds the page, and the switch stays.
    # `round_table_page` resumes from `costorm_state`, so leaving Co-STORM
    # and coming back finds the discussion where it was.
    if RoundTable.working():
        RoundTable.round_table_page()
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
