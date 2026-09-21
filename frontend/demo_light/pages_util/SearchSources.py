"""Which engine STORM researches with — an admin's page.

STORM takes one retriever, so this is a choice between sources rather than a
row of switches. A key can be tested before it is saved, and no key is ever
sent back to the browser: a saved one is shown as its last four characters.
"""

from urllib.parse import urlparse

import auth
import search_sources
import streamlit as st
import ui_theme
from ui_language import t

TEST_RESULT = "page5_search_test"


# What was just saved, carried across the rerun that a save triggers.
SAVED = "page5_saved"


def _saved_and_rerun(message):
    """Record what happened, then rerun.

    The toast cannot be raised here: a save ends in a rerun, and the rerun
    discards the render the toast would have appeared in. It is left in
    session state and shown by the next run — the same run that draws the
    saved value, so the two agree.
    """
    st.session_state[SAVED] = message
    st.rerun()


def _show_saved():
    """Announce the last save, once."""
    message = st.session_state.pop(SAVED, None)
    if message:
        st.toast(message, icon=":material/check_circle:")


def _test(name, typed):
    ok, message, urls = search_sources.check(name, secret=typed or None)
    st.session_state[TEST_RESULT] = (name, ok, message, urls)


def _show_test(name):
    result = st.session_state.get(TEST_RESULT)
    if not result or result[0] != name:
        return
    _, ok, message, urls = result
    if ok:
        hosts = ", ".join(dict.fromkeys(urlparse(u).netloc.replace("www.", "") for u in urls))
        st.success(t("search.test_ok", n=len(urls), hosts=hosts))
    elif message in ("no_results", "needs_endpoint", "needs_collection"):
        st.warning(t(f"search.{message}"))
    else:
        st.error(t("search.test_failed"))
        st.code(message, language=None)


def _source_card(name, chosen):
    source = search_sources.SOURCES[name]
    is_set, last4 = search_sources.hint(name)
    unavailable = "unavailable" in source

    with st.container(border=True, key=f"src_{name}_{'chosen' if name == chosen else 'other'}"):
        badge = ui_theme.badge(
            t("search.free") if source["free"] else t("search.paid"),
            tone="positive" if source["free"] else "info",
        )
        state = ""
        if unavailable:
            state = ui_theme.badge(t("search.unavailable"), tone="warning")
        elif name == chosen:
            state = ui_theme.badge(t("search.in_use"), tone="positive")
        st.markdown(
            f'<div class="src-head"><span class="name">{source["label"]}</span>'
            f'<span class="tags">{badge}{state}</span></div>',
            unsafe_allow_html=True,
        )

        if unavailable:
            st.caption(t(f"search.{source['unavailable']}"))
            return

        typed = ""
        if source.get("shares"):
            # Rides another source's address — the same instance, asked
            # differently. Nothing to type here; set it on the other card.
            shared = search_sources.SOURCES[source["shares"]]["label"]
            st.caption(t(source["note"]))
            st.caption(t("search.shares_address", name=shared))
        elif source.get("kind") == "url":
            # An address, not a secret: shown in full, edited in the open.
            # A blank box still means "keep what is saved", as with keys.
            saved_url = search_sources.secret_for(name) or ""
            typed = st.text_input(
                t("search.url_saved") if is_set else t("search.url_needed"),
                key=f"key_{name}",
                placeholder=saved_url or "https://searx.example.org",
            )
            st.caption(t(source["note"]))
            if source["signup"]:
                st.caption(f"[{t('search.host_one')}]({source['signup']})")
        elif source["key"]:
            label = (
                t("search.key_saved", last4=last4) if is_set else t("search.key_needed")
            )
            typed = st.text_input(
                label,
                type="password",
                key=f"key_{name}",
                placeholder="•" * 12 if is_set else "",
            )
            if source["signup"]:
                st.caption(f"[{t('search.get_key')}]({source['signup']})")
        else:
            st.caption(t(source.get("note", "search.no_key_needed")))

        left, right = st.columns(2)
        with left:
            if st.button(
                t("search.test"),
                key=f"test_{name}",
                icon=":material/wifi_tethering:",
                width="stretch",
            ):
                with st.spinner(t("search.testing")):
                    _test(name, typed)
        with right:
            can_use = bool(typed) or is_set or not source["key"]
            if st.button(
                t("search.use"),
                key=f"use_{name}",
                type="primary" if name != chosen else "secondary",
                disabled=not can_use or name == chosen,
                width="stretch",
            ):
                search_sources.save(name, {source["key"]: typed} if source["key"] else {})
                _saved_and_rerun(t("search.saved_in_use", name=source["label"]))

        # A shared address is forgotten from the card that owns it, not here —
        # this button would drop it for both.
        if is_set and typed == "" and not source.get("shares"):
            forget_label = (
                t("search.forget_url") if source.get("kind") == "url" else t("search.forget_key")
            )
            if st.button(forget_label, key=f"forget_{name}", type="tertiary"):
                search_sources.forget(source["key"])
                _saved_and_rerun(t("search.saved_forgotten", name=source["key"]))

        _show_test(name)


def search_sources_page():
    if not auth.is_admin():
        st.error(t("admin.not_admin"))
        return

    # Before anything is drawn, so a save's confirmation arrives with the
    # values it saved.
    _show_saved()

    settings = search_sources.load()
    chosen = settings["source"]
    ui_theme.page_header(
        t("search.title"), t("search.using", name=search_sources.SOURCES[chosen]["label"])
    )
    st.caption(t("search.one_at_a_time"))

    grid = list(search_sources.SOURCES)
    for row_start in range(0, len(grid), 2):
        columns = st.columns(2, gap="medium")
        for column, name in zip(columns, grid[row_start : row_start + 2]):
            with column:
                _source_card(name, chosen)

    _offer_section(settings)


def _offer_section(settings):
    """Which of the configured sources a member may tick for their own run.

    Only sources that can be built right now are listed — one without its
    key would fail in front of the person least able to fix it. The source
    in use is always offered; it is what a run gets when nothing is ticked.
    """
    ready = [n for n in search_sources.OFFERED if search_sources.ready(n)]
    with st.container(border=True, key="src_offer"):
        st.markdown(f"**{t('search.offer_title')}**")
        st.caption(t("search.offer_note"))
        chosen = st.multiselect(
            t("search.offer_title"),
            ready,
            default=[n for n in settings["offered"] if n in ready],
            format_func=lambda n: search_sources.SOURCES[n]["label"],
            key="src_offer_pick",
            label_visibility="collapsed",
        )
        if st.button(t("search.offer_save"), key="src_offer_save", type="primary"):
            search_sources.set_offered(chosen)
            # `set_offered` puts the source in use back in whatever was
            # chosen, because it is what a run with nothing ticked gets and
            # a list without it would leave the default pointing outside the
            # list. Saying so matters most when the choice was empty: the
            # page then looks like it refused the save rather than like it
            # completed one.
            saved = search_sources.load()["offered"]
            added = [n for n in saved if n not in chosen]
            labels = ", ".join(search_sources.SOURCES[n]["label"] for n in saved)
            if added:
                message = t(
                    "search.saved_offered_with_default",
                    list=labels,
                    name=search_sources.SOURCES[added[0]]["label"],
                )
            else:
                message = t("search.saved_offered", list=labels)
            _saved_and_rerun(message)
