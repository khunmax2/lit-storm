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
import model_settings
import run_options
import search_sources
import streamlit as st
from pages_util import CreateNewArticle, RoundTable
from ui_language import t

# Not prefixed with "page", so the choice survives a walk to the library and
# back — `clear_other_page_session_state` only sweeps keys that begin with it.
ENGINE_KEY = "home_engine"

STORM = "storm"
COSTORM = "costorm"

# icon, label, and the line under the switch that says what you are choosing.
ENGINES = {
    STORM: (":material/auto_stories:", "home.engine_storm", "home.engine_storm_note"),
    COSTORM: (":material/forum:", "home.engine_costorm", "home.engine_costorm_note"),
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


def _options():
    """How this run should go: depth, sources, model. A popover under the switch.

    The admin decides what is on offer; this is the pick from it. Every
    section that has nothing to offer is left out rather than shown empty,
    and the button says on its face whether anything has been changed, so
    a run started with the defaults looks like one.
    """
    offered_sources = run_options.offered_sources()
    presets = model_settings.presets()
    customised = run_options.is_customised()

    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        label = t("run.options_changed") if customised else t("run.options")
        with st.popover(label, icon=":material/tune:", width="stretch"):
            # Widgets read their value from session state when given a key;
            # handing them a default as well makes Streamlit warn and pick
            # one. So the state is seeded first and the widgets carry no
            # defaults of their own.
            st.session_state.setdefault(run_options.DEPTH_KEY, run_options.depth())
            st.markdown(f"**{t('run.depth')}**")
            st.radio(
                t("run.depth"),
                list(run_options.DEPTHS),
                key=run_options.DEPTH_KEY,
                format_func=lambda d: t(f"run.depth_{d}"),
                captions=[t(f"run.depth_{d}_note") for d in run_options.DEPTHS],
                label_visibility="collapsed",
            )

            # One preset is already a choice: it or the default.
            if presets:
                st.markdown(f"**{t('run.model')}**")
                ids = [None] + [p["id"] for p in presets]
                labels = {None: t("run.model_default")}
                labels.update({p["id"]: p["label"] for p in presets})
                st.session_state.setdefault(run_options.MODEL_KEY, run_options.model())
                if st.session_state[run_options.MODEL_KEY] not in ids:
                    st.session_state[run_options.MODEL_KEY] = None
                st.radio(
                    t("run.model"),
                    ids,
                    key=run_options.MODEL_KEY,
                    format_func=labels.__getitem__,
                    label_visibility="collapsed",
                )

            if len(offered_sources) > 1:
                st.markdown(f"**{t('run.sources')}**")
                st.caption(t("run.sources_note"))
                chosen = set(run_options.sources())
                picked = []
                for name in offered_sources:
                    source = search_sources.SOURCES[name]
                    note_key = source.get("note")
                    st.session_state.setdefault(f"run_source_{name}", name in chosen)
                    if st.checkbox(
                        source["label"],
                        key=f"run_source_{name}",
                        help=t(note_key) if note_key else None,
                    ):
                        picked.append(name)
                st.session_state[run_options.SOURCES_KEY] = picked

            if customised and st.button(t("run.reset"), type="tertiary", key="run_reset"):
                for key in (run_options.DEPTH_KEY, run_options.MODEL_KEY, run_options.SOURCES_KEY):
                    st.session_state.pop(key, None)
                for name in offered_sources:
                    st.session_state.pop(f"run_source_{name}", None)
                st.rerun()


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
    _options()
    if _engine() == COSTORM:
        RoundTable.round_table_page()
    else:
        CreateNewArticle.create_new_article_page()
