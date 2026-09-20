"""The round table: Co-STORM with a seat at it.

The article page runs STORM start to finish and hands back a document. This
page runs Co-STORM, which is the same research turned inside out — the experts
talk to each other in the open, one turn at a time, and a person can interrupt
at any point. Nothing advances unless somebody presses for it, so the page is a
transcript plus two ways to move: let the table speak, or speak yourself.

State lives under ``costorm_*`` rather than ``page6_*`` on purpose. A
discussion is expensive and has no file on disk until a report is written, so
walking over to the library and back should not throw it away —
``clear_other_page_session_state`` only sweeps keys that begin with "page".
"""

import re
import threading
from html import escape

import article_language
import article_store
import auth
import costorm
import demo_util
import search_sources
import streamlit as st
import ui_language
import ui_theme
from demo_util import DemoTextProcessingHelper
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from ui_language import t

from knowledge_storm.collaborative_storm.modules.callback import BaseCallbackHandler

# Every key this page owns, so "new discussion" can forget all of it without
# listing them again somewhere else.
STATE_KEYS = (
    "costorm_state",
    "costorm_runner",
    "costorm_status",
    "costorm_topic",
    "costorm_language",
    "costorm_run_id",
    "costorm_pending",
    "costorm_error",
    "costorm_folder",
    "costorm_intent",
    "costorm_suggestions",
)

# What the reader wants the discussion for. Fixed rather than written by a
# model: the question is the same whatever the topic, so paying for options
# would buy nothing. Each is (value, label, what it means, how it is said to
# the table); the first is the common case and the default, and the last is
# the way to decline — DeepTutor's card calls that a skipped question.
PURPOSES = (
    ("report", "table.purpose_report", "table.purpose_report_note"),
    ("decide", "table.purpose_decide", "table.purpose_decide_note"),
    ("learn", "table.purpose_learn", "table.purpose_learn_note"),
    ("teach", "table.purpose_teach", "table.purpose_teach_note"),
    ("none", "table.purpose_none", "table.purpose_none_note"),
)

# The warm start reports its progress as English prose with a step number in
# it. The number is the part worth keeping; the sentence is written again here
# in the reader's language.
_WARM_STEP = re.compile(r"Step (\d) / 4")


class RoundTableStatus(BaseCallbackHandler):
    """Co-STORM's progress, written into whichever status box is on screen.

    One discussion is seventy to a hundred model calls, so a person can sit in
    front of this for ten minutes. Every step therefore does two things: it
    appends a line to the log inside the box, and it rewrites the box's own
    label. The box is closed by default — the label alone is the answer to "is
    this thing still alive?", and it changes often enough to be one. Opening it
    is for the reader who wants to know which sources are being read.

    The runner keeps its handler for the life of the discussion, but the
    container to write into is a different widget on every rerun — and the
    worker threads that call these methods have no Streamlit context of their
    own. So both are re-attached before each turn rather than captured once.
    """

    def __init__(self):
        self.container = None
        self._script_run_ctx = None
        self.sources = 0

    def attach(self, container):
        self.container = container
        self._script_run_ctx = get_script_run_ctx()
        return self

    def _step(self, message):
        """Report a step: as the box's label, and as a line inside it."""
        if self.container is None:
            return
        if self._script_run_ctx is not None:
            add_script_run_ctx(threading.current_thread(), self._script_run_ctx)
        self.container.update(label=message)
        self.container.markdown(message)

    def _browsed(self, url):
        """A source that has been read. Counted in the label, listed inside.

        The URLs are the bulk of what this box says and the least of what it
        means, so only the running count reaches the label.
        """
        if self.container is None:
            return
        if self._script_run_ctx is not None:
            add_script_run_ctx(threading.current_thread(), self._script_run_ctx)
        self.sources += 1
        self.container.update(label=t("table.step_browsed", n=self.sources))
        self.container.markdown(t("status.browsed", link=f"[{url}]({url})"))

    # -- a turn ----------------------------------------------------------
    def on_turn_policy_planning_start(self, **kwargs):
        self._step(t("table.planning"))

    def on_expert_action_planning_start(self, **kwargs):
        self._step(t("table.deciding"))

    def on_expert_action_planning_end(self, **kwargs):
        self._step(t("table.decided"))

    def on_expert_information_collection_start(self, **kwargs):
        self._step(t("table.searching"))

    def on_expert_information_collection_end(self, info, **kwargs):
        for url in dict.fromkeys(item.url for item in info or []):
            self._browsed(url)

    def on_expert_utterance_generation_end(self, **kwargs):
        self._step(t("table.drafted"))

    def on_expert_utterance_polishing_start(self, **kwargs):
        self._step(t("table.polishing"))

    def on_expert_list_update_start(self, **kwargs):
        self._step(t("table.updating_experts"))

    def on_mindmap_insert_start(self, **kwargs):
        self._step(t("table.filing"))

    def on_mindmap_insert_end(self, **kwargs):
        self._step(t("table.filed"))

    def on_mindmap_reorg_start(self, **kwargs):
        self._step(t("table.reorganising"))

    def on_article_generation_start(self, **kwargs):
        self._step(t("table.writing_sections"))

    # -- the warm start --------------------------------------------------
    def on_warmstart_update(self, message, **kwargs):
        step = _WARM_STEP.search(message or "")
        if step:
            self._step(t(f"table.warm_step{step.group(1)}"))
            return
        for line in (message or "").splitlines():
            url = line.removeprefix("Finish browsing ").strip()
            if url.startswith("http"):
                self._browsed(url)


def _language():
    """The language the table talks in, seeded by the interface language.

    Seeded once, when the picker is first drawn, rather than followed: a
    discussion already under way should not change language because somebody
    switched the interface while reading it.
    """
    if "costorm_language" not in st.session_state:
        default = ui_language.current()
        st.session_state["costorm_language"] = (
            default
            if default in article_language.LANGUAGES
            else article_language.DEFAULT
        )
    return st.session_state["costorm_language"]


def _reset():
    for key in STATE_KEYS:
        st.session_state.pop(key, None)


def busy():
    """Whether a discussion is open and should keep the page to itself.

    Unlike a STORM run this survives navigation: the keys are not `page_`
    ones, so a discussion is still there after a trip to the library.
    """
    return st.session_state.get("costorm_state", "idle") != "idle"


# --------------------------------------------------------------- opening


def _opening():
    """The topic form, and what the page is for."""
    _language()  # seeds the picker below before it is drawn
    # No eyebrow: the switch above the hero already says which engine this is.
    ui_theme.hero(
        title=t("table.title"),
        subtitle=t("table.subtitle"),
    )

    _, form_column, _ = st.columns([1, 3, 1])
    with form_column:
        with st.form(key="round_table_form"):
            topic = st.text_input(
                t("create.topic"),
                placeholder=t("table.topic_placeholder"),
            )
            st.selectbox(
                t("create.article_language"),
                list(article_language.LANGUAGES),
                key="costorm_language",
            )

            # The purpose sits between the topic and the button, so it reads
            # as part of asking rather than as a setting to go back for.
            labels = dict((value, label) for value, label, _ in PURPOSES)
            purpose = st.radio(
                t("table.purpose_label"),
                [value for value, _, _ in PURPOSES],
                captions=[t(note) for _, _, note in PURPOSES],
                format_func=lambda value: t(labels[value]),
            )
            typed_purpose = st.text_input(
                t("table.purpose_own"),
                placeholder=t("table.purpose_own_placeholder"),
            )

            submitted = st.form_submit_button(
                t("table.submit"), type="primary", width="stretch"
            )
            st.caption(t("table.caption"))

        if submitted:
            _open_discussion(topic, purpose, typed_purpose)

    ui_theme.section_label(t("home.how_label"))
    ui_theme.steps(
        [
            (t("table.step1_title"), t("table.step1_body")),
            (t("table.step2_title"), t("table.step2_body")),
            (t("table.step3_title"), t("table.step3_body")),
        ]
    )


def _open_discussion(topic, purpose, typed_purpose):
    """Check what a discussion costs before starting one."""
    topic = topic.strip()
    if not topic:
        st.warning(t("create.needs_topic"), icon=":material/warning:")
        return
    try:
        article_store.validate_name(costorm.truncate(topic))
    except ValueError:
        st.warning(t("create.invalid_topic"), icon=":material/warning:")
        return
    if not auth.may_run():
        _, limit = auth.quota()
        st.warning(t("auth.quota_spent", limit=limit), icon=":material/warning:")
        return
    # The reader's own words win over the preset, and "none" says nothing at
    # all rather than saying "no particular purpose" to the table.
    typed_purpose = (typed_purpose or "").strip()
    if typed_purpose:
        st.session_state["costorm_intent"] = typed_purpose
    elif purpose and purpose != "none":
        st.session_state["costorm_intent"] = t(
            "table.purpose_said",
            purpose=t(dict((v, label) for v, label, _ in PURPOSES)[purpose]).lower(),
        )
    # A new discussion is a new row in the ledger. `_reset` clears this on the
    # way out of the last one, but clearing it on the way in is what makes the
    # rule above safe to read: an id in session state always belongs to the
    # discussion on screen.
    st.session_state.pop("costorm_run_id", None)
    st.session_state["costorm_topic"] = topic
    st.session_state["costorm_state"] = "warming"
    st.rerun()


# ------------------------------------------------------------ warm start


def _header():
    chips = [t("table.in_progress")]
    runner = st.session_state.get("costorm_runner")
    if runner is not None:
        chips = [
            t("table.turns", n=len(runner.conversation_history)),
            t("articles.sources", n=len(runner.knowledge_base.info_uuid_to_info_dict)),
        ]
    st.markdown(
        f'<div class="article-head"><h1>{escape(st.session_state["costorm_topic"])}</h1>'
        f'<div class="meta">{ui_theme.chips(chips)}</div></div>',
        unsafe_allow_html=True,
    )


def _warm_start():
    """Build the runner and let the experts brief each other."""
    _header()
    # Closed: the label says what is happening, and it is the label that
    # gets rewritten on every step. The log behind it is for whoever wants
    # to see which sources were read.
    status = st.status(t("table.warm_label"), expanded=False)
    handler = RoundTableStatus().attach(status)

    article_language.apply(_language())
    try:
        runner = costorm.build_runner(
            st.session_state["costorm_topic"], callback_handler=handler
        )
    except search_sources.SearchConfigError as error:
        _abandon(status, t("search.failed_config"), error)
        return
    except demo_util.LMConfigError as error:
        _abandon(status, t("table.failed_embedding"), error)
        return
    except Exception as error:  # noqa: BLE001 - nothing started, so say so
        _abandon(status, t("create.failed_generic"), error)
        return

    # Recorded once per discussion rather than once per attempt. "warming" is
    # the state for the whole ten-minute warm start, so any rerun inside that
    # window — a saved file, a reconnected browser, a stray click — re-enters
    # here from the top. Opening a new row each time it did so cost one reader
    # seventeen runs of quota for a single topic, and left sixteen rows stuck
    # at "running" that nothing would ever close.
    if "costorm_run_id" not in st.session_state:
        st.session_state["costorm_run_id"] = auth.record_run_start(
            st.session_state["costorm_topic"], _language()
        )
    try:
        runner.warm_start()
    except Exception as error:  # noqa: BLE001 - any failure ends the warm start
        auth.record_run_end(
            st.session_state.get("costorm_run_id"), "failed", error=str(error)
        )
        _abandon(status, _failure_message(error), error)
        return

    # The research is paid for and kept whether or not a report is ever asked
    # for, so the ledger is closed here rather than at the end of the chat.
    # Said now rather than before: the warm start builds the panel's shared
    # background and takes no user turn, so this is the first moment there is
    # a conversation to say it into. Costs nothing — recording an utterance
    # is not a model call — and the next turn is the one that answers it.
    intent = st.session_state.get("costorm_intent")
    if intent:
        runner.step(user_utterance=intent)

    auth.record_run_end(st.session_state.get("costorm_run_id"), "done")
    status.update(label=t("table.warm_done"), state="complete")
    st.session_state["costorm_runner"] = runner
    st.session_state["costorm_status"] = handler
    st.session_state["costorm_state"] = "open"
    st.rerun()


def _failure_message(error):
    quota = ("ratelimit", "rate limit", "quota", "credits", "429")
    text = str(error).lower()
    return (
        t("create.failed_quota")
        if any(hint in text for hint in quota)
        else t("create.failed_generic")
    )


def _abandon(status, message, error):
    """Report a failure that leaves no discussion behind, and go back."""
    status.update(label=t("create.failed_label"), state="error")
    st.error(message)
    with st.expander(t("create.failed_detail")):
        st.code(f"{type(error).__name__}: {error}", language=None)
    _reset()
    if st.button(t("create.retry"), type="primary"):
        st.rerun()


# ------------------------------------------------------------ round table


def _speaker(turn):
    """(is the user, name, description, avatar) for whoever is talking.

    Co-STORM calls the person at the table "Guest"; everyone else introduces
    themselves as "role: what they will focus on", which `ConversationTurn`
    has already split apart.
    """
    role = (turn.role or "").strip()
    if role.lower() in ("guest", "you"):
        return True, t("table.you"), "", None
    if "moderator" in role.lower():
        return False, role, turn.role_description, ":material/gavel:"
    # A nameless speaker is not a thing the panel produces, but an empty name
    # is refused by `st.chat_message` outright, which would take the whole
    # transcript down with it.
    return False, role or "assistant", turn.role_description, None


def _transcript(runner):
    citations = costorm.citation_dict(runner)
    for turn in runner.conversation_history:
        guest, name, description, avatar = _speaker(turn)
        with st.chat_message("user" if guest else name, avatar=avatar):
            if not guest:
                st.markdown(f"**{name}**")
                if description:
                    st.caption(description.strip())
            # "$" would otherwise open a LaTeX block halfway through a
            # sentence about money.
            text = costorm.clean_utterance(
                ui_language.localize_engine_reply(turn.utterance)
            ).replace("$", "\\$")
            st.markdown(
                DemoTextProcessingHelper.add_inline_citation_link(text, citations)
            )


def _suggestions():
    """Questions to put to the table, offered as buttons.

    Drawn only when they have been asked for. The alternative — generating
    three every turn — spends a model call on every reader who was going to
    type their own question anyway, and there is no way to know which reader
    that is until they have already been charged for it.

    The free-text box below stays either way: a suggestion is a shortcut past
    a blank page, never the only way to speak.
    """
    ready = st.session_state.get("costorm_suggestions")
    if not ready:
        return None

    with st.container(border=True):
        st.caption(t("table.suggestions_label"))
        for index, question in enumerate(ready):
            if st.button(
                question,
                key=f"suggested_{index}",
                icon=":material/help:",
                width="stretch",
            ):
                return question
    return None


def _mind_map(runner):
    outline = costorm.mind_map(runner)
    with st.expander(t("table.mind_map")):
        st.code(outline or t("table.mind_map_empty"), language=None)


def _controls(working):
    """The two ways to move the discussion, and the way out of it."""
    with st.container(horizontal=True):
        if st.button(
            t("table.next_turn"),
            icon=":material/play_arrow:",
            type="primary",
            disabled=working,
        ):
            _queue("turn")
        if st.button(
            t("table.write_report"),
            icon=":material/draft:",
            disabled=working,
        ):
            _queue("report")
        if st.button(
            t("table.suggest"),
            icon=":material/lightbulb:",
            disabled=working,
        ):
            _queue("suggest")
        with st.popover(t("table.new"), icon=":material/refresh:", disabled=working):
            st.write(t("table.new_confirm"))
            if st.button(t("table.new"), type="primary", key="confirm_new"):
                _reset()
                st.rerun()


def _queue(work):
    st.session_state.pop("costorm_error", None)
    st.session_state["costorm_pending"] = work
    st.rerun()


def _round_table():
    runner = st.session_state["costorm_runner"]
    _header()

    pending = st.session_state.pop("costorm_pending", None)
    _controls(working=pending is not None)
    _mind_map(runner)

    if st.session_state.get("costorm_error"):
        st.error(st.session_state["costorm_error"])

    if st.session_state.get("costorm_folder"):
        _report_ready()

    _transcript(runner)
    picked = _suggestions()

    # Drawn even while the table is thinking — it is pinned to the foot of the
    # page, and a box that vanishes for a minute reads as a page that broke.
    said = st.chat_input(t("table.say_placeholder"), disabled=pending is not None)

    if pending:
        _work(runner, pending)
        return

    said = said or picked
    if said:
        # Recording what the user said costs nothing — it is the reply that
        # takes a minute — so it is done now and drawn on the way in.
        st.session_state.pop("costorm_suggestions", None)
        runner.step(user_utterance=said)
        _queue("turn")


def _work(runner, pending):
    """Run the turn (or the report) the last click asked for, then redraw."""
    labels = {
        "turn": t("table.thinking"),
        "report": t("table.writing_label"),
        "suggest": t("table.suggesting"),
    }
    label = labels[pending]
    status = st.status(label, expanded=False)
    st.session_state["costorm_status"].attach(status)

    article_language.apply(_language())
    try:
        if pending == "turn":
            runner.step()
        elif pending == "suggest":
            st.session_state["costorm_suggestions"] = costorm.suggest_questions(
                runner,
                st.session_state.get("costorm_intent"),
                _language(),
            )
        else:
            runner.knowledge_base.reorganize()
            st.session_state["costorm_folder"] = costorm.save_report(
                runner,
                runner.generate_report(),
                st.session_state["costorm_topic"],
            )
            auth.record_run_end(
                st.session_state.get("costorm_run_id"),
                "done",
                folder=st.session_state["costorm_folder"],
            )
    except costorm.EmptyReport:
        status.update(label=t("create.failed_label"), state="error")
        st.session_state["costorm_error"] = t("table.failed_empty_report")
    except Exception as error:  # noqa: BLE001 - a failed turn is not a failed run
        status.update(label=t("create.failed_label"), state="error")
        st.session_state["costorm_error"] = f"{t('table.failed_turn')}\n\n`{error}`"
    else:
        status.update(
            label={
                "turn": t("table.thinking_done"),
                "report": t("table.writing_done"),
                "suggest": t("table.suggested"),
            }[pending],
            state="complete",
        )
    st.rerun()


def _report_ready():
    with st.container(border=True):
        st.success(t("table.report_ready"), icon=":material/task_alt:")
        if st.button(t("create.read_article"), type="primary"):
            st.session_state["nav_pending"] = "My Articles"
            st.session_state["page2_selected_my_article"] = st.session_state[
                "costorm_folder"
            ]
            st.rerun()


def round_table_page():
    demo_util.clear_other_page_session_state(page_index=6)

    state = st.session_state.get("costorm_state", "idle")
    if state == "warming":
        _warm_start()
    elif state == "open":
        _round_table()
    else:
        _opening()
