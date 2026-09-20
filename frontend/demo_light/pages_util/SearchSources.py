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
        if source["key"]:
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
                st.rerun()

        if is_set and typed == "":
            if st.button(
                t("search.forget_key"), key=f"forget_{name}", type="tertiary"
            ):
                search_sources.forget(source["key"])
                st.rerun()

        _show_test(name)


def search_sources_page():
    if not auth.is_admin():
        st.error(t("admin.not_admin"))
        return

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
