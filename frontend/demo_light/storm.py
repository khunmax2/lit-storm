import os

script_dir = os.path.dirname(os.path.abspath(__file__))
wiki_root_dir = os.path.dirname(os.path.dirname(script_dir))

import demo_util
import streamlit as st
import ui_language
import ui_theme
from pages_util import MyArticles, CreateNewArticle
from ui_language import t

# The page names double as `nav_page` state, so they stay these fixed English
# ids and are translated only on the way to the screen.
ARTICLES_PAGE = "My Articles"
CREATE_PAGE = "Create New Article"
PAGE_ICONS = {
    ARTICLES_PAGE: ":material/collections_bookmark:",
    CREATE_PAGE: ":material/auto_awesome:",
}
PAGE_LABELS = {ARTICLES_PAGE: "nav.articles", CREATE_PAGE: "nav.home"}


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
    ui_theme.sidebar_brand()

    if "first_run" not in st.session_state:
        st.session_state["first_run"] = True

    # set api keys from secrets
    if st.session_state["first_run"]:
        for key, value in st.secrets.items():
            if type(value) == str:
                os.environ[key] = value

    # `nav_page` is the segmented control's own state, so other pages can
    # navigate simply by assigning to it before the widget is drawn.
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
    with st.sidebar:
        st.segmented_control(
            t("nav.label"),
            [CREATE_PAGE, ARTICLES_PAGE],
            format_func=lambda page: f"{PAGE_ICONS[page]} {t(PAGE_LABELS[page])}",
            key="nav_page",
            label_visibility="collapsed",
        )
        ui_language.selector()

    # A segmented control can be deselected by clicking the active option.
    selection = st.session_state["nav_page"] or CREATE_PAGE

    if selection == ARTICLES_PAGE:
        demo_util.clear_other_page_session_state(page_index=2)
        MyArticles.my_articles_page()
    else:
        demo_util.clear_other_page_session_state(page_index=3)
        CreateNewArticle.create_new_article_page()


if __name__ == "__main__":
    main()
