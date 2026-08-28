import os

import article_language
import auth
import demo_util
import streamlit as st
import ui_language
import ui_theme
from demo_util import DemoFileIOHelper, truncate_filename
from ui_language import t

EXAMPLE_TOPICS = {
    "English": [
        "The history of Thai silk",
        "Perovskite solar cells",
        "AI adoption among Thai SMEs",
    ],
    "ไทย": [
        "ประวัติศาสตร์ผ้าไหมไทย",
        "เซลล์แสงอาทิตย์เพอรอฟสไกต์",
        "แนวโน้มการใช้ AI ในธุรกิจไทย",
    ],
}


def _language():
    """The language the article will be written in.

    Someone reading a Thai interface almost always wants a Thai article, so the
    interface language seeds this; the picker below can still override it.
    """
    default = ui_language.current()
    if default not in article_language.LANGUAGES:
        default = article_language.DEFAULT
    return st.session_state.get("page3_language", default)


def _follow_interface_language():
    """Point the article picker at the interface language whenever that changes.

    Only on a change, so an explicit pick of a different article language
    survives the reruns that follow it.
    """
    interface = ui_language.current()
    if st.session_state.get("page3_language_followed") == interface:
        return
    st.session_state["page3_language_followed"] = interface
    if interface in article_language.LANGUAGES:
        st.session_state["page3_language"] = interface


def _start_research(topic):
    """Move the page into the research state for `topic`."""
    topic = topic.strip()
    if not topic:
        st.warning(t("create.needs_topic"), icon=":material/warning:")
        return
    # The limit is per person per month, not a role: creating reports is what
    # members are here for, and this is what stops one shared key paying for
    # all of it at once.
    if not auth.may_run():
        _, limit = auth.quota()
        st.warning(t("auth.quota_spent", limit=limit), icon=":material/warning:")
        return
    cleaned = topic.replace(" ", "_").replace("/", "_")
    st.session_state["page3_topic"] = topic
    st.session_state["page3_topic_name_cleaned"] = cleaned
    st.session_state["page3_topic_name_truncated"] = truncate_filename(cleaned)
    st.session_state["page3_write_article_state"] = "initiated"


def _recent_articles(limit=3):
    """The newest finished articles, as (name, path, mtime).

    Reads the directory directly rather than going through the library page,
    whose cache lives under a `page2_` key that is cleared while this page is
    the active one.
    """
    root = demo_util.working_dir()
    found = []
    for name in os.listdir(root):
        for filename in ("storm_gen_article_polished.txt", "storm_gen_article.txt"):
            path = os.path.join(root, name, filename)
            if os.path.exists(path):
                found.append((name, path, os.path.getmtime(path)))
                break
    return sorted(found, key=lambda row: row[2], reverse=True)[:limit]


def _open_in_library(article_name):
    st.session_state["nav_pending"] = "My Articles"
    st.session_state["page2_selected_my_article"] = article_name
    st.rerun()


def _how_it_works():
    ui_theme.section_label(t("home.how_label"))
    ui_theme.steps(
        [
            (t("home.step1_title"), t("home.step1_body")),
            (t("home.step2_title"), t("home.step2_body")),
            (t("home.step3_title"), t("home.step3_body")),
        ]
    )


def _recent_work():
    """Proof the thing works, drawn from what this instance has actually made."""
    recent = _recent_articles()
    if not recent:
        return

    ui_theme.section_label(t("home.recent_label"))
    columns = st.columns(3, gap="medium")
    for column, (name, path, mtime) in zip(columns, recent):
        length, sources, excerpt = ui_theme.summarize_article(
            path,
            os.path.join(os.path.dirname(path), "url_to_info.json"),
            mtime,
        )
        meta = [ui_theme.humanize_date(mtime), ui_theme.length_label(length)]
        if sources:
            meta.append(t("articles.sources", n=sources))
        with column:
            with st.container(border=True):
                st.markdown(
                    f'<div class="acard">'
                    f'<div class="title">{name.replace("_", " ")}</div>'
                    f'<div class="meta">{ui_theme.meta_line(meta)}</div>'
                    f'<div class="excerpt">{excerpt}</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    t("articles.read"), key=f"recent_{name}", use_container_width=True
                ):
                    _open_in_library(name)


def handle_not_started():
    if st.session_state["page3_write_article_state"] != "not started":
        return

    _follow_interface_language()

    ui_theme.hero(
        eyebrow=t("create.eyebrow"),
        title=t("create.title"),
        subtitle=t("create.subtitle"),
    )

    _, form_column, _ = st.columns([1, 3, 1])
    with form_column:
        with st.form(key="search_form"):
            topic = st.text_input(
                t("create.topic"),
                placeholder=t("create.topic_placeholder"),
                label_visibility="collapsed",
            )
            language_column, button_column = st.columns([1, 2])
            with language_column:
                st.selectbox(
                    t("create.article_language"),
                    list(article_language.LANGUAGES),
                    key="page3_language",
                    label_visibility="collapsed",
                )
            with button_column:
                submitted = st.form_submit_button(
                    t("create.submit"), type="primary", use_container_width=True
                )
            st.caption(t("create.caption"))
        if submitted:
            _start_research(topic)
            if st.session_state["page3_write_article_state"] == "initiated":
                st.rerun()

        st.markdown(
            '<div class="side-label" style="margin-top:1.4rem;text-align:center">'
            f'{t("create.try_example")}</div>',
            unsafe_allow_html=True,
        )
        examples = EXAMPLE_TOPICS.get(_language(), EXAMPLE_TOPICS["English"])
        example_columns = st.columns(len(examples))
        for column, example in zip(example_columns, examples):
            with column:
                if st.button(example, key=f"eg_{example}", use_container_width=True):
                    _start_research(example)
                    st.rerun()

        st.markdown(
            f'<div class="lp-note">{t("home.hero_note")}</div>',
            unsafe_allow_html=True,
        )

    _how_it_works()
    _recent_work()


def handle_initiated():
    if st.session_state["page3_write_article_state"] == "initiated":
        current_working_dir = demo_util.working_dir()

        # Called on every run, not only the first: it is what notices that the
        # provider in secrets.toml has changed.
        try:
            demo_util.set_storm_runner()
        except demo_util.LMConfigError as error:
            st.error(t("create.failed_model"))
            st.code(str(error), language=None)
            st.session_state["page3_write_article_state"] = "not started"
            return
        # Rewrites STORM's writing prompts in place, so it has to happen before
        # the run rather than when the (cached) runner was built.
        article_language.apply(_language())
        st.session_state["page3_run_id"] = auth.record_run_start(
            st.session_state["page3_topic"], _language()
        )
        st.session_state["page3_current_working_dir"] = current_working_dir
        st.session_state["page3_write_article_state"] = "pre_writing"


def _running_header():
    st.markdown(
        f'<div class="article-head"><h1>{st.session_state["page3_topic"]}</h1>'
        f'<div class="meta">{ui_theme.chips([t("create.in_progress")])}</div></div>',
        unsafe_allow_html=True,
    )


def _report_failure(status, error):
    """Show a failed run as a message rather than a traceback.

    Streamlit's default is to render the exception and its stack into the
    page, which tells a researcher nothing and looks like the app broke.
    """
    auth.record_run_end(
        st.session_state.get("page3_run_id"), "failed", error=str(error)
    )
    status.update(label=t("create.failed_label"), state="error")
    quota = ("ratelimit", "rate limit", "quota", "credits", "429")
    text = str(error).lower()
    st.error(
        t("create.failed_quota")
        if any(hint in text for hint in quota)
        else t("create.failed_generic")
    )
    with st.expander(t("create.failed_detail")):
        st.code(f"{type(error).__name__}: {error}", language=None)
    st.session_state["page3_write_article_state"] = "not started"
    if st.button(t("create.retry"), type="primary"):
        st.rerun()


def handle_pre_writing():
    if st.session_state["page3_write_article_state"] != "pre_writing":
        return

    _running_header()
    status = st.status(t("create.step1"), expanded=True)
    st_callback_handler = demo_util.StreamlitCallbackHandler(status)
    failure = None
    with status:
        try:
            st.session_state["runner"].run(
                topic=st.session_state["page3_topic"],
                do_research=True,
                do_generate_outline=True,
                do_generate_article=False,
                do_polish_article=False,
                callback_handler=st_callback_handler,
            )
        except Exception as error:  # noqa: BLE001 - any failure ends the run
            failure = error
    # Reported outside the status: an errored status collapses, and the
    # explanation has to stay on screen.
    if failure is not None:
        _report_failure(status, failure)
        return
    with status:
        conversation_log_path = os.path.join(
            st.session_state["page3_current_working_dir"],
            st.session_state["page3_topic_name_truncated"],
            "conversation_log.json",
        )
        demo_util._display_persona_conversations(
            DemoFileIOHelper.read_json_file(conversation_log_path)
        )
        st.session_state["page3_write_article_state"] = "final_writing"
        status.update(label=t("create.step1_done"), state="complete")


def handle_final_writing():
    if st.session_state["page3_write_article_state"] != "final_writing":
        return

    with st.status(t("create.step2"), expanded=True) as status:
        st.write(t("create.step2_writing"))
        try:
            st.session_state["runner"].run(
                topic=st.session_state["page3_topic"],
                do_research=False,
                do_generate_outline=False,
                do_generate_article=True,
                do_polish_article=True,
                remove_duplicate=False,
            )
            st.session_state["runner"].post_run()
        except Exception as error:  # noqa: BLE001 - any failure ends the run
            failure = error
        else:
            failure = None
            auth.record_run_end(
                st.session_state.get("page3_run_id"),
                "done",
                folder=st.session_state["page3_topic_name_truncated"],
            )
            st.session_state["page3_write_article_state"] = "prepare_to_show_result"
            status.update(label=t("create.step2_done"), state="complete")

    if failure is not None:
        _report_failure(status, failure)


def handle_prepare_to_show_result():
    if st.session_state["page3_write_article_state"] == "prepare_to_show_result":
        _, button_column, _ = st.columns([3, 2, 3])
        with button_column:
            if st.button(
                t("create.read_article"), type="primary", use_container_width=True
            ):
                st.session_state["page3_write_article_state"] = "completed"
                st.rerun()


def handle_completed():
    if st.session_state["page3_write_article_state"] == "completed":
        current_working_dir_paths = DemoFileIOHelper.read_structure_to_dict(
            st.session_state["page3_current_working_dir"]
        )
        current_article_file_path_dict = current_working_dir_paths[
            st.session_state["page3_topic_name_truncated"]
        ]
        demo_util.display_article_page(
            selected_article_name=st.session_state["page3_topic_name_cleaned"],
            selected_article_file_path_dict=current_article_file_path_dict,
            show_title=True,
            show_main_article=True,
        )


def create_new_article_page():
    demo_util.clear_other_page_session_state(page_index=3)

    if "page3_write_article_state" not in st.session_state:
        st.session_state["page3_write_article_state"] = "not started"

    handle_not_started()

    handle_initiated()

    handle_pre_writing()

    handle_final_writing()

    handle_prepare_to_show_result()

    handle_completed()
