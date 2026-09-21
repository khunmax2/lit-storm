import os

script_dir = os.path.dirname(os.path.abspath(__file__))
wiki_root_dir = os.path.dirname(os.path.dirname(script_dir))

import auth
import demo_util
import streamlit as st
import ui_language
import ui_theme
from pages_util import (
    Account,
    Admin,
    Home,
    ModelSettings,
    MyArticles,
    SearchSources,
)
from ui_language import t

# The page names double as `nav_page` state, so they stay these fixed English
# ids and are translated only on the way to the screen.
ARTICLES_PAGE = "My Articles"
CREATE_PAGE = "Create New Article"
ADMIN_PAGE = "Members"
SOURCES_PAGE = "Search sources"
MODELS_PAGE = "Models"
PAGE_ICONS = {
    ARTICLES_PAGE: ":material/description:",
    CREATE_PAGE: ":material/home:",
    ADMIN_PAGE: ":material/group:",
    SOURCES_PAGE: ":material/travel_explore:",
    MODELS_PAGE: ":material/network_intelligence:",
}
PAGE_LABELS = {
    ARTICLES_PAGE: "nav.articles",
    CREATE_PAGE: "nav.home",
    ADMIN_PAGE: "nav.admin",
    SOURCES_PAGE: "nav.sources",
    MODELS_PAGE: "nav.models",
}


def _select_main_page():
    chosen = st.session_state.get("nav_main")
    if chosen:
        st.session_state["nav_page"] = chosen
        st.session_state["nav_manage"] = None


def _select_management_page():
    chosen = st.session_state.get("nav_manage")
    if chosen:
        st.session_state["nav_page"] = chosen
        st.session_state["nav_main"] = None


def main():
    st.set_page_config(
        page_title="STORM",
        page_icon="🌪️",
        layout="wide",
        # "auto" expands the sidebar on desktop but collapses it on phones,
        # where an expanded sidebar covers the whole landing page.
        initial_sidebar_state="auto",
    )
    ui_theme.apply()
    ui_language.selector()
    ui_theme.sidebar_brand()

    # Drawn before the gate, so it is on the screen whether or not the bypass
    # let anybody through.
    if auth.dev_enabled():
        ui_theme.dev_banner(auth.display_name())

    # A refresh should not cost a password. The browser still holds a crumb
    # from the last sign-in; this trades it for a session before the gate is
    # drawn, and `touch` ends a session that has been idle too long.
    auth.restore()
    auth.touch()

    # Nothing else is drawn until there is an account behind the request:
    # every run spends the deployment's API credit, and every article belongs
    # to somebody.
    if not Account.gate():
        return

    if "first_run" not in st.session_state:
        st.session_state["first_run"] = True

    # Publish secrets.toml into the environment, for the code that reads
    # os.environ directly rather than going through `auth.setting`.
    #
    # Guarded because a container has no secrets.toml — `auth.setting` says
    # so in as many words — and iterating one that is not there raises
    # instead of coming back empty. Nothing is lost when it does: what this
    # loop would have published is what such a deployment already passes in
    # as environment variables.
    if st.session_state["first_run"]:
        try:
            carried = list(st.secrets.items())
        except FileNotFoundError:
            carried = []
        for key, value in carried:
            if type(value) == str:
                os.environ[key] = value

    # nav_page is the canonical destination; the two sidebar groups mirror it.
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = CREATE_PAGE

    # Streamlit refuses assignment to a widget's key once that widget exists,
    # so a page that wants to navigate queues the destination here instead and
    # this consumes it on the next run, before the control is drawn.
    queued = st.session_state.pop("nav_pending", None)
    if queued:
        st.session_state["nav_page"] = queued

    # All navigation lives in the sidebar. The article page needs a sidebar
    # regardless — it is where the contents and references go — so a second
    # bar across the top would only duplicate a surface that has to exist.
    # The roster is only listed for an admin. A member who reaches the page
    # another way still gets refused — by the page, and by the policies.
    pages = [CREATE_PAGE, ARTICLES_PAGE]
    if auth.is_admin():
        pages.append(ADMIN_PAGE)
        pages.append(SOURCES_PAGE)
        pages.append(MODELS_PAGE)
    if st.session_state["nav_page"] not in pages:
        st.session_state["nav_page"] = CREATE_PAGE

    main_pages = [CREATE_PAGE, ARTICLES_PAGE]
    management_pages = [ADMIN_PAGE, SOURCES_PAGE, MODELS_PAGE] if auth.is_admin() else []
    selected_page = st.session_state["nav_page"]
    st.session_state["nav_main"] = selected_page if selected_page in main_pages else None
    st.session_state["nav_manage"] = (
        selected_page if selected_page in management_pages else None
    )
    with st.sidebar:
        st.markdown(f'<div class="side-label">{t("nav.main_group")}</div>',
                    unsafe_allow_html=True)
        st.segmented_control(
            t("nav.main_group"), main_pages,
            format_func=lambda page: f"{PAGE_ICONS[page]} {t(PAGE_LABELS[page])}",
            key="nav_main", label_visibility="collapsed", on_change=_select_main_page,
        )
        if management_pages:
            st.markdown(f'<div class="side-label side-group-management">{t("nav.manage_group")}</div>',
                        unsafe_allow_html=True)
            st.segmented_control(
                t("nav.manage_group"), management_pages,
                format_func=lambda page: f"{PAGE_ICONS[page]} {t(PAGE_LABELS[page])}",
                key="nav_manage", label_visibility="collapsed",
                on_change=_select_management_page,
            )

    # A segmented control can be deselected by clicking the active option.
    selection = st.session_state["nav_page"] or CREATE_PAGE

    # After the navigation, and pinned to the foot of the rail by CSS.
    Account.sidebar_account()

    # Breadcrumb. The article name is already in state by the time this draws,
    # because it is set on the run before the article page appears.
    trail = [t(PAGE_LABELS[selection])]
    if selection == ARTICLES_PAGE and "page2_selected_my_article" in st.session_state:
        trail.append(st.session_state["page2_selected_my_article"].replace("_", " "))
    clicked = ui_theme.top_bar(
        trail,
        name=auth.display_name(),
        role=t("auth.role_admin") if auth.is_admin() else t("auth.role_member"),
    )
    # The only crumb above the current page today is the library, so clicking
    # it means: stop reading this article. The trail is the way back, which is
    # why there is no longer a separate button for it.
    if clicked is not None:
        st.session_state.pop("page2_selected_my_article", None)
        st.rerun()

    if selection == MODELS_PAGE:
        demo_util.clear_other_page_session_state(page_index=6)
        ModelSettings.model_settings_page()
    elif selection == SOURCES_PAGE:
        demo_util.clear_other_page_session_state(page_index=5)
        SearchSources.search_sources_page()
    elif selection == ADMIN_PAGE:
        demo_util.clear_other_page_session_state(page_index=4)
        Admin.admin_page()
    elif selection == ARTICLES_PAGE:
        demo_util.clear_other_page_session_state(page_index=2)
        MyArticles.my_articles_page()
    else:
        # Both engines live behind this one page; it picks between them.
        Home.home_page()


if __name__ == "__main__":
    main()
