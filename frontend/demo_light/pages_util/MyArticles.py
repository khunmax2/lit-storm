import os
import html

import article_import
import article_store
import demo_util
import streamlit as st
import ui_theme
from demo_util import DemoFileIOHelper
from ui_language import t



def _load_articles():
    # A directory scan is cheap and prevents stale entries after deletion,
    # new runs, or an account change in the same browser session.
    return DemoFileIOHelper.read_structure_to_dict(demo_util.working_dir())


def _delete_article(article_name):
    try:
        article_store.trash_article(demo_util.working_dir(), article_name)
    except (OSError, ValueError):
        st.error(t("articles.action_failed"))
        return
    st.session_state["page2_library_notice"] = ("articles.deleted", article_name)
    if st.session_state.get("page2_selected_my_article") == article_name:
        st.session_state.pop("page2_selected_my_article", None)
    st.rerun()


def _deleted_articles():
    root = demo_util.working_dir()
    entries = article_store.list_trash(root)
    if not entries:
        return
    with st.expander(t("articles.trash", n=len(entries))):
        st.caption(t("articles.trash_note"))
        for entry_id, name in entries.items():
            with st.container(horizontal=True, vertical_alignment="center"):
                st.write(name.replace("_", " "))
                if st.button(
                    t("articles.restore"),
                    icon=":material/restore_from_trash:",
                    key=f"restore_{entry_id}",
                ):
                    try:
                        article_store.restore_article(root, entry_id)
                    except FileExistsError:
                        st.error(t("articles.restore_conflict"))
                    except (OSError, ValueError):
                        st.error(t("articles.action_failed"))
                    else:
                        st.session_state["page2_library_notice"] = (
                            "articles.restored", name
                        )
                        st.rerun()


def _import_panel(width="content"):
    """Take in a report that was written by one of the framed engines.

    Deep Research and the agents researcher both hand a finished report over
    as Markdown and then have nowhere to put it. This is the far end of that:
    the file goes in, an article comes out, and the library stops being only
    half of what a member has made.

    The title is read from the report's own first heading rather than asked
    for, because the report already knows what it is called. It stays
    editable — a heading is a headline, and a directory name is a name.
    """
    with st.popover(
        t("articles.import"),
        icon=":material/upload_file:",
        key="import_article",
        width=width,
    ):
        st.caption(t("articles.import_note"))
        upload = st.file_uploader(
            t("articles.import_file"),
            type=["md", "markdown", "txt"],
            key="import_file",
        )

        text = ""
        suggested = ""
        if upload is not None:
            try:
                text = upload.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                st.error(t("articles.import_not_text"), icon=":material/error:")
            else:
                suggested = article_import.suggested_title(text, upload.name)
                found = len(article_import.parse_sources(text))
                # Said before saving, not after: whether the references came
                # across is the one thing about an import that is worth
                # knowing while the decision is still being made.
                st.caption(
                    t("articles.import_sources", n=found)
                    if found
                    else t("articles.import_no_sources")
                )

        title = st.text_input(
            t("articles.import_title"),
            placeholder=suggested or t("articles.import_title"),
            key="import_title",
        )
        if st.button(
            t("articles.import_save"),
            type="primary",
            width="stretch",
            disabled=not text.strip(),
            key="import_save",
        ):
            chosen = (title or "").strip() or suggested
            try:
                name = article_import.save(
                    demo_util.working_dir(),
                    chosen,
                    text,
                    origin=upload.name if upload else "",
                )
            except ValueError:
                st.error(t("articles.import_bad_title"), icon=":material/error:")
            except FileExistsError:
                st.error(t("articles.import_exists"), icon=":material/error:")
            except OSError:
                st.error(t("articles.action_failed"), icon=":material/error:")
            else:
                st.session_state["page2_library_notice"] = ("articles.imported", name)
                st.rerun()


def _card_menu(article_name, article_path, file_path_dict):
    """Every report, including an interrupted one, can be deleted."""
    with st.popover(
        t("articles.actions"), icon=":material/more_vert:",
        key=f"card_menu_{article_name}"
    ):
        if article_path:
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
                width="stretch",
            )
        if st.button(
            t("articles.delete"), icon=":material/delete:",
            key=f"delete_{article_name}", width="stretch",
        ):
            _delete_article(article_name)
        st.caption(t("articles.delete_note"))


def _incomplete_details(article_name, files):
    """Show saved research without needing a finished article or an LLM call."""
    ui_theme.page_header(article_name.replace("_", " "))
    st.warning(t("articles.incomplete_body"))
    st.caption(t("articles.saved_details_note"))
    found = False
    for filename, label in (
        ("storm_gen_outline.txt", "articles.saved_outline"),
        ("direct_gen_outline.txt", "articles.initial_outline"),
    ):
        path = files.get(filename)
        if path:
            found = True
            with st.expander(t(label)):
                try:
                    with open(path, encoding="utf-8") as handle:
                        text = handle.read()
                    if text.strip():
                        st.markdown(text)
                    else:
                        st.warning(t("articles.saved_details_unreadable"))
                except (OSError, UnicodeError):
                    st.warning(t("articles.saved_details_unreadable"))

    for filename, label in (
        ("conversation_log.json", "articles.saved_interviews"),
        ("raw_search_results.json", "articles.saved_sources"),
    ):
        path = files.get(filename)
        if not path:
            continue
        found = True
        with st.expander(t(label)):
            try:
                data = DemoFileIOHelper.read_json_file(path)
                if filename == "conversation_log.json":
                    if data:
                        demo_util._display_persona_conversations(data)
                    else:
                        st.info(t("articles.no_saved_details"))
                else:
                    # Only research content, never run_config or API settings.
                    for source in data.values():
                        st.write(source.get("title") or source.get("url", ""))
                        for snippet in source.get("snippets", []):
                            st.write(snippet)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                st.warning(t("articles.saved_details_unreadable"))
    if not found:
        st.info(t("articles.no_saved_details"))


def _article_card(article_name, file_path_dict):
    """One card in the grid. Returns True when the user opens the article."""
    title = article_name.replace("_", " ")
    article_path = article_store.completed_article(file_path_dict)
    if article_path and article_path != file_path_dict.get("storm_gen_article_polished.txt"):
        file_path_dict = dict(file_path_dict)
        file_path_dict.pop("storm_gen_article_polished.txt", None)
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
        body = f'<div class="acard"><div class="title">{html.escape(title)}</div>'
        if state:
            body += f'<div class="state">{state}</div>'
        if meta:
            body += f'<div class="meta">{ui_theme.meta_line(meta)}</div>'
        body += f'<div class="excerpt">{html.escape(excerpt)}</div></div>'
        st.markdown(body, unsafe_allow_html=True)
        # Drawn after the body and lifted into the corner by CSS, so it needs
        # no row of its own to sit in.
        _card_menu(article_name, article_path, file_path_dict)
        return st.button(
            t("articles.read") if ready else t("articles.inspect"),
            icon=":material/description:" if ready else ":material/search:",
            key=f"open_{article_name}",
            width="stretch",
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
    notice = st.session_state.pop("page2_library_notice", None)
    if notice:
        key, name = notice
        st.success(t(key, name=name.replace("_", " ")))

    # ---- reading a single article -------------------------------------
    # The way back to the library is drawn by the shell, with the rest of the
    # navigation — see storm.py.
    if "page2_selected_my_article" in st.session_state:
        selected = st.session_state["page2_selected_my_article"]
        files = articles.get(selected)
        if files is None:
            st.session_state.pop("page2_selected_my_article", None)
            st.rerun()
        with st.container(horizontal=True):
            if st.button(t("articles.back"), icon=":material/arrow_back:"):
                st.session_state.pop("page2_selected_my_article", None)
                st.rerun()
            if st.button(
                t("articles.delete"), icon=":material/delete:",
                key=f"delete_selected_{selected}",
            ):
                _delete_article(selected)
        article_path = article_store.completed_article(files)
        if article_path:
            # Use the nonempty draft if a failed polish left an empty file.
            files = dict(files)
            if article_path != files.get("storm_gen_article_polished.txt"):
                files.pop("storm_gen_article_polished.txt", None)
            demo_util.display_article_page(
                selected_article_name=selected,
                selected_article_file_path_dict=files,
                show_title=True,
                show_main_article=True,
            )
        else:
            _incomplete_details(selected, files)
        return

    # ---- the library ---------------------------------------------------
    if not articles:
        ui_theme.page_header(t("nav.articles"))
        _deleted_articles()
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
                width="stretch",
            ):
                st.session_state["nav_pending"] = "Create New Article"
                st.rerun()
            # Here too, and not only on a library that already has something
            # in it: a member whose first report came from Deep Research
            # arrives at this page with nothing, and importing is exactly
            # what they are here to do.
            _import_panel(width="stretch")
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
    _deleted_articles()

    search_col, import_col, _ = st.columns([2, 1, 2], vertical_alignment="center")
    with search_col:
        query = st.text_input(
            t("articles.search"),
            placeholder=t("articles.search_placeholder"),
            icon=":material/search:",
            label_visibility="collapsed",
        )
    with import_col:
        _import_panel(width="stretch")
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
