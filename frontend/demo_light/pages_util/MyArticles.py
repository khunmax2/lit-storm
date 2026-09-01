import os

import demo_util
import streamlit as st
import ui_theme
from demo_util import DemoFileIOHelper
from ui_language import t



def _load_articles():
    if "page2_user_articles_file_path_dict" not in st.session_state:
        local_dir = demo_util.working_dir()
        st.session_state["page2_user_articles_file_path_dict"] = (
            DemoFileIOHelper.read_structure_to_dict(local_dir)
        )
    return st.session_state["page2_user_articles_file_path_dict"]


def _card_menu(article_name, article_path, file_path_dict):
    """The quiet menu in a card's top corner.

    Only what there is actually a file for: the article itself. A menu whose
    items do nothing is worse than no menu, so a card with no finished
    article does not get one.
    """
    if not (article_path and os.path.exists(article_path)):
        return
    with st.popover("", icon=":material/more_vert:"):
        demo_util.download_report_button(
            article_name,
            file_path_dict,
            article_path,
            key=f"card_report_{article_name}",
        )
        st.download_button(
            t("article.download"),
            data=ui_theme.read_text(article_path, os.path.getmtime(article_path)),
            file_name=f"{article_name}.md",
            mime="text/markdown",
            icon=":material/download:",
            key=f"card_download_{article_name}",
            use_container_width=True,
        )


def _article_card(article_name, file_path_dict):
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
        state = ""
        ready = True
    else:
        # A run that was interrupted before the article was written. That is a
        # state rather than a measurement, so it is not listed beside the date
        # and the counts.
        meta = []
        state = ui_theme.badge(t("articles.incomplete"), tone="info")
        excerpt = t("articles.incomplete_body")
        ready = False

    with st.container(border=True):
        body = f'<div class="acard"><div class="title">{title}</div>'
        if state:
            body += f'<div class="state">{state}</div>'
        if meta:
            body += f'<div class="meta">{ui_theme.meta_line(meta)}</div>'
        body += f'<div class="excerpt">{excerpt}</div></div>'
        st.markdown(body, unsafe_allow_html=True)
        # Drawn after the body and lifted into the corner by CSS, so it needs
        # no row of its own to sit in.
        _card_menu(article_name, article_path, file_path_dict)
        return st.button(
            t("articles.read") if ready else t("articles.inspect"),
            icon=":material/description:" if ready else ":material/search:",
            key=f"open_{article_name}",
            use_container_width=True,
            disabled=not ready,
        )


def _grid(article_names, articles):
    """Every card in one container, laid out by CSS.

    st.columns() fixes the number of columns when the page renders, so a
    three-up row stayed three-up on a tablet and overflowed on a phone. A
    grid over one flat list reflows to 3, 2 or 1 on its own.
    """
    with st.container(key="article_grid"):
        for article_name in article_names:
            if _article_card(article_name, articles[article_name]):
                st.session_state["page2_selected_my_article"] = article_name
                st.rerun()


def my_articles_page():
    articles = _load_articles()

    # ---- reading a single article -------------------------------------
    # The way back to the library is drawn by the shell, with the rest of the
    # navigation — see storm.py.
    if "page2_selected_my_article" in st.session_state:
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
            icon=":material/search:",
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
