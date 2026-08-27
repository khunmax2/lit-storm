import os

import demo_util
import streamlit as st
import ui_theme
from demo_util import DemoFileIOHelper
from ui_language import t

CARDS_PER_ROW = 3


def _load_articles():
    if "page2_user_articles_file_path_dict" not in st.session_state:
        local_dir = os.path.join(demo_util.get_demo_dir(), "DEMO_WORKING_DIR")
        os.makedirs(local_dir, exist_ok=True)
        st.session_state["page2_user_articles_file_path_dict"] = (
            DemoFileIOHelper.read_structure_to_dict(local_dir)
        )
    return st.session_state["page2_user_articles_file_path_dict"]


def _article_card(column, article_name, file_path_dict):
    """One card in the grid. Returns True when the user opens the article."""
    title = article_name.replace("_", " ")
    article_path = file_path_dict.get(
        "storm_gen_article_polished.txt"
    ) or file_path_dict.get("storm_gen_article.txt")
    url_info_path = file_path_dict.get("url_to_info.json")

    if article_path and os.path.exists(article_path):
        mtime = os.path.getmtime(article_path)
        length, sources, excerpt = ui_theme.summarize_article(
            article_path, url_info_path, mtime
        )
        meta = [ui_theme.humanize_date(mtime), ui_theme.length_label(length)]
        if sources:
            meta.append(t("articles.sources", n=sources))
        ready = True
    else:
        # A run that was interrupted before the article was written.
        meta = [t("articles.incomplete")]
        excerpt = t("articles.incomplete_body")
        ready = False

    with column:
        with st.container(border=True):
            st.markdown(
                f'<div class="acard">'
                f'<div class="title">{title}</div>'
                f'<div class="meta">{ui_theme.meta_line(meta)}</div>'
                f'<div class="excerpt">{excerpt}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            return st.button(
                t("articles.read") if ready else t("articles.inspect"),
                key=f"open_{article_name}",
                use_container_width=True,
                disabled=not ready,
            )


def _grid(article_names, articles):
    # One st.columns() per row, so cards in a row share the same height.
    for row_start in range(0, len(article_names), CARDS_PER_ROW):
        row = article_names[row_start : row_start + CARDS_PER_ROW]
        columns = st.columns(CARDS_PER_ROW, gap="medium")
        for column, article_name in zip(columns, row):
            clicked = _article_card(
                column=column,
                article_name=article_name,
                file_path_dict=articles[article_name],
            )
            if clicked:
                st.session_state["page2_selected_my_article"] = article_name
                st.rerun()


def my_articles_page():
    articles = _load_articles()

    # ---- reading a single article -------------------------------------
    if "page2_selected_my_article" in st.session_state:
        with st.sidebar:
            if st.button(t("articles.back"), use_container_width=True):
                del st.session_state["page2_selected_my_article"]
                st.rerun()

        selected = st.session_state["page2_selected_my_article"]
        demo_util.display_article_page(
            selected_article_name=selected,
            selected_article_file_path_dict=articles[selected],
            show_title=True,
            show_main_article=True,
        )
        return

    # ---- the library ---------------------------------------------------
    if not articles:
        ui_theme.page_header(t("nav.articles"))
        ui_theme.empty_state(
            "library_books",
            t("articles.empty_title"),
            t("articles.empty_body", create=t("nav.home")),
        )
        _, button_col, _ = st.columns([3, 2, 3])
        with button_col:
            if st.button(
                t("articles.start_first"),
                type="primary",
                use_container_width=True,
            ):
                st.session_state["nav_pending"] = "Create New Article"
                st.rerun()
        return

    article_names = sorted(articles.keys(), key=lambda n: n.lower())
    ui_theme.page_header(
        t("nav.articles"),
        t(
            "articles.count",
            n=len(article_names),
            s="s" if len(article_names) > 1 else "",
        ),
    )

    search_col, _ = st.columns([2, 3])
    with search_col:
        query = st.text_input(
            t("articles.search"),
            placeholder=t("articles.search_placeholder"),
            label_visibility="collapsed",
        )
    if query:
        needle = query.lower().replace(" ", "_")
        article_names = [n for n in article_names if needle in n.lower()]
        if not article_names:
            ui_theme.empty_state(
                "search_off", t("articles.no_match_title"), t("articles.no_match_body", query=query)
            )
            return

    # Pagination only matters once the library gets big.
    page_size = 24
    total_pages = max(1, -(-len(article_names) // page_size))
    if total_pages > 1:
        nav_col, _ = st.columns([1, 4])
        with nav_col:
            current_page = st.number_input(
                t("articles.page", total=total_pages),
                min_value=1,
                max_value=total_pages,
                step=1,
            )
        start = (current_page - 1) * page_size
        article_names = article_names[start : start + page_size]

    _grid(article_names, articles)
