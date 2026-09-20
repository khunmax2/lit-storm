"""What one person may choose for one run, and where that choice is kept.

Three choices: how deep to go, which sources to search, and which model to
write with. None of them is new — every one is a knob the app already turned,
just with the value fixed by the admin. What is new is that the admin now
decides what is *on offer* (`search_sources.set_offered`,
`model_settings.set_presets`) and the person starting a run picks from that.

A run started without opening the picker gets the admin's settings unchanged,
so nothing about the app's behaviour moves for anyone who never looks.

The choice lives in session state under keys without the "page" prefix, so
it survives a walk to the library and back the way the engine switch does.
"""

import streamlit as st

import model_settings
import search_sources

# The knobs behind each level, for both engines. "standard" is exactly what
# the app has always used; the others are the same knobs moved.
#
# Time estimates are for Gemini Flash on DuckDuckGo. Deep is not three times
# standard because the interviews are the cost and they scale with
# perspectives times turns — five by four is over twice three by three.
DEPTHS = {
    "fast": {
        "max_conv_turn": 2,
        "max_perspective": 2,
        "search_top_k": 3,
        "retrieve_top_k": 3,
        "warmstart_max_num_experts": 2,
        "max_search_queries_per_turn": 2,
    },
    "standard": {
        "max_conv_turn": 3,
        "max_perspective": 3,
        "search_top_k": 3,
        "retrieve_top_k": 5,
        "warmstart_max_num_experts": 3,
        "max_search_queries_per_turn": 3,
    },
    "deep": {
        "max_conv_turn": 4,
        "max_perspective": 5,
        "search_top_k": 5,
        "retrieve_top_k": 8,
        "warmstart_max_num_experts": 4,
        "max_search_queries_per_turn": 4,
    },
}
DEFAULT_DEPTH = "standard"

DEPTH_KEY = "run_depth"
SOURCES_KEY = "run_sources"
MODEL_KEY = "run_model"


def depth():
    """The chosen level, always one of `DEPTHS`."""
    chosen = st.session_state.get(DEPTH_KEY)
    return chosen if chosen in DEPTHS else DEFAULT_DEPTH


def knobs():
    return DEPTHS[depth()]


def offered_sources():
    """Sources the admin has put on offer *and* that can be built right now.

    A source ticked as offered but missing its key would fail at run time
    with a message about the key, in front of someone who cannot fix it. So
    it is not shown.
    """
    return [n for n in search_sources.load()["offered"] if search_sources.ready(n)]


def sources():
    """The ticked sources, limited to what is on offer.

    Empty means "whatever the admin set", and `search_sources.build_many`
    treats it that way, so an untouched picker is not a different run.
    """
    # Returned in the admin's order, not the order they were ticked: that is
    # the order `build_many` searches them in, and keeping the two the same
    # means re-ticking the same set in a different order is not a new run.
    ticked = set(st.session_state.get(SOURCES_KEY, []))
    return [n for n in offered_sources() if n in ticked]


def model():
    """The chosen model preset id, or None for the admin's default."""
    chosen = st.session_state.get(MODEL_KEY)
    ids = {p["id"] for p in model_settings.presets()}
    return chosen if chosen in ids else None


def fingerprint():
    """What of the choice a runner was built from; part of its cache key."""
    return f"{depth()}|{','.join(sources())}|{model() or ''}"


def is_customised():
    """Whether anything differs from the admin's settings — for the badge."""
    return depth() != DEFAULT_DEPTH or bool(sources()) or model() is not None
