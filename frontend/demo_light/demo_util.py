import base64
import datetime
import functools
import hashlib
import json
import os
import re
import threading
from typing import Optional

import markdown
import pytz
import streamlit as st
import article_store
import auth
import html_report
import model_settings
import run_options
import search_sources
import ui_language
import ui_theme
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from ui_language import t

# If you install the source code instead of the `knowledge-storm` package,
# Uncomment the following lines:
# import sys
# sys.path.append('../../')
from knowledge_storm import (
    STORMWikiRunnerArguments,
    STORMWikiRunner,
    STORMWikiLMConfigs,
)
from knowledge_storm.lm import GoogleModel, LitellmModel
from knowledge_storm.storm_wiki.modules.callback import BaseCallbackHandler
from knowledge_storm.utils import truncate_filename
from stoc import stoc


def _quiet_litellm():
    """Stop litellm narrating every call it makes into the terminal.

    Three separate noises, all from the same library and none of them a
    problem with the run:

    - a red "Provider List:" banner, printed whenever litellm is handed a
      model name with no provider prefix that it cannot place. The "-latest"
      aliases are exactly that, so it fires, prints, and then swallows its
      own exception;
    - an INFO line per call, logged twice over because litellm both attaches
      a handler and lets the record propagate to the root logger;
    - a pydantic serializer warning, raised when litellm writes a Gemini
      response — seven fields — through a model shaped for OpenAI's ten.

    Only the chatter goes. Anything litellm considers a warning or an error —
    a rate limit, a refused key, a failed call — still reaches the terminal.
    """
    import logging
    import warnings

    import litellm

    litellm.suppress_debug_info = True
    for name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
    warnings.filterwarnings(
        "ignore", message="Pydantic serializer warnings", category=UserWarning
    )


_quiet_litellm()


class DemoFileIOHelper:
    @staticmethod
    def read_structure_to_dict(articles_root_path):
        """
        Reads the directory structure of articles stored in the given root path and
        returns a nested dictionary. The outer dictionary has article names as keys,
        and each value is another dictionary mapping file names to their absolute paths.

        Args:
            articles_root_path (str): The root directory path containing article subdirectories.

        Returns:
            dict: A dictionary where each key is an article name, and each value is a dictionary
                of file names and their absolute paths within that article's directory.
        """
        return article_store.list_articles(articles_root_path)

    @staticmethod
    def read_txt_file(file_path):
        """
        Reads the contents of a text file and returns it as a string.

        Args:
            file_path (str): The path to the text file to be read.

        Returns:
            str: The content of the file as a single string.
        """
        with open(file_path) as f:
            return f.read()

    @staticmethod
    def read_json_file(file_path):
        """
        Reads a JSON file and returns its content as a Python dictionary or list,
        depending on the JSON structure.

        Args:
            file_path (str): The path to the JSON file to be read.

        Returns:
            dict or list: The content of the JSON file. The type depends on the
                        structure of the JSON file (object or array at the root).
        """
        with open(file_path) as f:
            return json.load(f)

    @staticmethod
    def read_image_as_base64(image_path):
        """
        Reads an image file and returns its content encoded as a base64 string,
        suitable for embedding in HTML or transferring over networks where binary
        data cannot be easily sent.

        Args:
            image_path (str): The path to the image file to be encoded.

        Returns:
            str: The base64 encoded string of the image, prefixed with the necessary
                data URI scheme for images.
        """
        with open(image_path, "rb") as f:
            data = f.read()
            encoded = base64.b64encode(data)
        data = "data:image/png;base64," + encoded.decode("utf-8")
        return data

    @staticmethod
    def set_file_modification_time(file_path, modification_time_string):
        """
        Sets the modification time of a file based on a given time string in the California time zone.

        Args:
            file_path (str): The path to the file.
            modification_time_string (str): The desired modification time in 'YYYY-MM-DD HH:MM:SS' format.
        """
        california_tz = pytz.timezone("America/Los_Angeles")
        modification_time = datetime.datetime.strptime(
            modification_time_string, "%Y-%m-%d %H:%M:%S"
        )
        modification_time = california_tz.localize(modification_time)
        modification_time_utc = modification_time.astimezone(datetime.timezone.utc)
        modification_timestamp = modification_time_utc.timestamp()
        os.utime(file_path, (modification_timestamp, modification_timestamp))

    @staticmethod
    def get_latest_modification_time(path):
        """
        Returns the latest modification time of all files in a directory in the California time zone as a string.

        Args:
            directory_path (str): The path to the directory.

        Returns:
            str: The latest file's modification time in 'YYYY-MM-DD HH:MM:SS' format.
        """
        california_tz = pytz.timezone("America/Los_Angeles")
        latest_mod_time = None

        file_paths = []
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_paths.append(os.path.join(root, file))
        else:
            file_paths = [path]

        for file_path in file_paths:
            modification_timestamp = os.path.getmtime(file_path)
            modification_time_utc = datetime.datetime.utcfromtimestamp(
                modification_timestamp
            )
            modification_time_utc = modification_time_utc.replace(
                tzinfo=datetime.timezone.utc
            )
            modification_time_california = modification_time_utc.astimezone(
                california_tz
            )

            if (
                latest_mod_time is None
                or modification_time_california > latest_mod_time
            ):
                latest_mod_time = modification_time_california

        if latest_mod_time is not None:
            return latest_mod_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def assemble_article_data(article_file_path_dict):
        """
        Constructs a dictionary containing the content and metadata of an article
        based on the available files in the article's directory. This includes the
        main article text, citations from a JSON file, and a conversation log if
        available. The function prioritizes a polished version of the article if
        both a raw and polished version exist.

        Args:
            article_file_paths (dict): A dictionary where keys are file names relevant
                                    to the article (e.g., the article text, citations
                                    in JSON format, conversation logs) and values
                                    are their corresponding file paths.

        Returns:
            dict or None: A dictionary containing the parsed content of the article,
                        citations, and conversation log if available. Returns None
                        if neither the raw nor polished article text exists in the
                        provided file paths.
        """
        if (
            "storm_gen_article.txt" in article_file_path_dict
            or "storm_gen_article_polished.txt" in article_file_path_dict
        ):
            full_article_name = (
                "storm_gen_article_polished.txt"
                if "storm_gen_article_polished.txt" in article_file_path_dict
                else "storm_gen_article.txt"
            )
            article_data = {
                "article": DemoTextProcessingHelper.parse(
                    DemoFileIOHelper.read_txt_file(
                        article_file_path_dict[full_article_name]
                    )
                )
            }
            if "url_to_info.json" in article_file_path_dict:
                article_data["citations"] = _construct_citation_dict_from_search_result(
                    DemoFileIOHelper.read_json_file(
                        article_file_path_dict["url_to_info.json"]
                    )
                )
            if "conversation_log.json" in article_file_path_dict:
                article_data["conversation_log"] = DemoFileIOHelper.read_json_file(
                    article_file_path_dict["conversation_log.json"]
                )
            return article_data
        return None


class DemoTextProcessingHelper:
    @staticmethod
    def remove_citations(sent):
        return (
            re.sub(r"\[\d+", "", re.sub(r" \[\d+", "", sent))
            .replace(" |", "")
            .replace("]", "")
        )

    @staticmethod
    def parse_conversation_history(json_data):
        """
        Given conversation log data, return list of parsed data of following format
        (persona_name, persona_description, list of dialogue turn)
        """
        parsed_data = []
        for persona_conversation_data in json_data:
            if ": " in persona_conversation_data["perspective"]:
                name, description = persona_conversation_data["perspective"].split(
                    ": ", 1
                )
            elif "- " in persona_conversation_data["perspective"]:
                name, description = persona_conversation_data["perspective"].split(
                    "- ", 1
                )
            else:
                name, description = "", persona_conversation_data["perspective"]
            cur_conversation = []
            for dialogue_turn in persona_conversation_data["dlg_turns"]:
                cur_conversation.append(
                    {"role": "user", "content": dialogue_turn["user_utterance"]}
                )
                cur_conversation.append(
                    {
                        "role": "assistant",
                        "content": DemoTextProcessingHelper.remove_citations(
                            dialogue_turn["agent_utterance"]
                        ),
                    }
                )
            parsed_data.append((name, description, cur_conversation))
        return parsed_data

    @staticmethod
    def parse(text):
        regex = re.compile(r']:\s+"(.*?)"\s+http')
        text = regex.sub("]: http", text)
        return text

    @staticmethod
    def add_markdown_indentation(input_string):
        lines = input_string.split("\n")
        processed_lines = [""]
        for line in lines:
            num_hashes = 0
            for char in line:
                if char == "#":
                    num_hashes += 1
                else:
                    break
            num_hashes -= 1
            num_spaces = 4 * num_hashes
            new_line = " " * num_spaces + line
            processed_lines.append(new_line)
        return "\n".join(processed_lines)

    @staticmethod
    def get_current_time_string():
        """
        Returns the current time in the California time zone as a string.

        Returns:
            str: The current California time in 'YYYY-MM-DD HH:MM:SS' format.
        """
        california_tz = pytz.timezone("America/Los_Angeles")
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        california_now = utc_now.astimezone(california_tz)
        return california_now.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def compare_time_strings(
        time_string1, time_string2, time_format="%Y-%m-%d %H:%M:%S"
    ):
        """
        Compares two time strings to determine if they represent the same point in time.

        Args:
            time_string1 (str): The first time string to compare.
            time_string2 (str): The second time string to compare.
            time_format (str): The format of the time strings, defaults to '%Y-%m-%d %H:%M:%S'.

        Returns:
            bool: True if the time strings represent the same time, False otherwise.
        """
        # Parse the time strings into datetime objects
        time1 = datetime.datetime.strptime(time_string1, time_format)
        time2 = datetime.datetime.strptime(time_string2, time_format)

        # Compare the datetime objects
        return time1 == time2

    @staticmethod
    def add_inline_citation_link(article_text, citation_dict):
        # Regular expression to find citations like [i]
        pattern = r"\[(\d+)\]"

        # Function to replace each citation with its Markdown link
        def replace_with_link(match):
            i = match.group(1)
            url = citation_dict.get(int(i), {}).get("url", "#")
            return f"[[{i}]]({url})"

        # Replace all citations in the text with Markdown links
        return re.sub(pattern, replace_with_link, article_text)

    @staticmethod
    def generate_html_toc(md_text):
        toc = []
        for line in md_text.splitlines():
            if line.startswith("#"):
                level = line.count("#")
                title = line.strip("# ").strip()
                anchor = title.lower().replace(" ", "-").replace(".", "")
                toc.append(
                    f"<li style='margin-left: {20 * (level - 1)}px;'><a href='#{anchor}'>{title}</a></li>"
                )
        return "<ul>" + "".join(toc) + "</ul>"

    @staticmethod
    def construct_bibliography_from_url_to_info(url_to_info):
        bibliography_list = []
        sorted_url_to_unified_index = dict(
            sorted(
                url_to_info["url_to_unified_index"].items(), key=lambda item: item[1]
            )
        )
        for url, index in sorted_url_to_unified_index.items():
            title = url_to_info["url_to_info"][url]["title"]
            bibliography_list.append(f"[{index}]: [{title}]({url})")
        bibliography_string = "\n\n".join(bibliography_list)
        return f"# References\n\n{bibliography_string}"


class DemoUIHelper:
    @staticmethod
    def article_markdown_to_html(article_title, article_content):
        return f"""
        <html>
            <head>
                <meta charset="utf-8">
                <title>{article_title}</title>
                <style>
                    .title {{
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="title">
                    <h1>{article_title.replace('_', ' ')}</h1>
                </div>
                <h2>Table of Contents</h2>
                {DemoTextProcessingHelper.generate_html_toc(article_content)}
                {markdown.markdown(article_content)}
            </body>
        </html>
        """


def _construct_citation_dict_from_search_result(search_results):
    if search_results is None:
        return None
    citation_dict = {}
    for url, index in search_results["url_to_unified_index"].items():
        citation_dict[index] = {
            "url": url,
            "title": search_results["url_to_info"][url]["title"],
            "snippets": search_results["url_to_info"][url]["snippets"],
        }
    return citation_dict


def _display_main_article_text(article_text, citation_dict, table_content_sidebar):
    # Post-process the generated article for better display.
    if "Write the lead section:" in article_text:
        article_text = article_text[
            article_text.find("Write the lead section:")
            + len("Write the lead section:") :
        ]
    if article_text[0] == "#":
        article_text = "\n".join(article_text.split("\n")[1:])
    article_text = DemoTextProcessingHelper.add_inline_citation_link(
        article_text, citation_dict
    )
    # '$' needs to be changed to '\$' to avoid being interpreted as LaTeX in st.markdown()
    article_text = article_text.replace("$", "\\$")
    stoc.from_markdown(article_text, table_content_sidebar)


def _reference_card(number, citation):
    title = citation["title"].replace("$", "\\$")
    st.markdown(
        f'<div class="ref-card"><div class="ref-title">[{number}] {title}</div>'
        f'<div class="ref-url"><a href="{citation["url"]}" target="_blank">'
        f'{citation["url"]}</a></div></div>',
        unsafe_allow_html=True,
    )


@st.dialog(" ", width="large")
def _references_dialog(citation_dict):
    """Every source behind the article, in one place.

    The panel beside the article used to hold a picker that showed one source
    at a time, which meant the list could not be read as a list. The reference
    puts a single button there instead.
    """
    st.markdown(
        f'<div class="dialog-head">{t("article.references")}</div>',
        unsafe_allow_html=True,
    )
    for number in sorted(citation_dict):
        citation = citation_dict[number]
        _reference_card(number, citation)
        snippets = "\n\n".join(citation.get("snippets", [])).replace("$", "\\$")
        if snippets:
            with st.expander(t("article.highlights")):
                st.markdown(snippets)


def _display_persona_conversations(conversation_log):
    """
    Display persona conversation in dialogue UI
    """
    # get personas list as (persona_name, persona_description, dialogue turns list) tuple
    parsed_conversation_history = DemoTextProcessingHelper.parse_conversation_history(
        conversation_log
    )
    # construct tabs for each persona conversation
    persona_tabs = st.tabs([name for (name, _, _) in parsed_conversation_history])
    for idx, persona_tab in enumerate(persona_tabs):
        with persona_tab:
            # show persona description
            st.info(parsed_conversation_history[idx][1])
            # show user / agent utterance in dialogue UI
            for message in parsed_conversation_history[idx][2]:
                message["content"] = ui_language.localize_engine_reply(
                    message["content"]
                ).replace("$", "\\$")
                with st.chat_message(message["role"]):
                    if message["role"] == "user":
                        st.markdown(f"**{message['content']}**")
                    else:
                        st.markdown(message["content"])


def _display_main_article(
    selected_article_file_path_dict,
    show_reference=True,
    show_conversation=True,
    head=None,
):
    article_data = DemoFileIOHelper.assemble_article_data(
        selected_article_file_path_dict
    )

    # Contents and references sit in a right-hand column beside the article
    # rather than in the sidebar, which the navigation now owns.
    # 173px of aside was too narrow for a wrapped Thai heading.
    # The card is the measure now: at the widths this is used at, the text
    # fills it the way the reference's does, and the cap below only bites on
    # a very wide screen.
    body_column, aside_column = st.columns([1.5, 1], gap="medium")

    with aside_column:
        toc_panel = st.container()
        references_panel = st.container()

    with toc_panel, st.container(key="toc_card"):
        ui_theme.aside_title(t("article.toc"), icon="format_list_bulleted")
        toc_target = st.container()

    # Title, badges and the download sit inside the article's own card rather
    # than on the page above it, so the article reads as one sheet.
    with body_column, st.container(key="article_card"):
        if head is not None:
            head()
        # A keyed container, not a pair of marker divs: an open tag in one
        # st.markdown and its close in another do not wrap what is between
        # them — Streamlit closes each one where it stands, and the class was
        # landing on an empty div while the article sat outside it.
        with st.container(key="article_text"):
            with st.container(height=900, border=False):
                _display_main_article_text(
                    article_text=article_data.get("article", ""),
                    citation_dict=article_data.get("citations", {}),
                    table_content_sidebar=toc_target,
                )

    # display reference panel
    if show_reference and "citations" in article_data:
        citations = article_data.get("citations", {})
        with references_panel, st.container(key="refs_card"):
            ui_theme.aside_title(t("article.references"), icon="menu_book")
            if not citations:
                st.caption(t("article.no_references"))
            elif st.button(
                t("article.view_all_references"),
                icon=":material/open_in_new:",
                width="stretch",
                key="refs_open",
            ):
                _references_dialog(citations)

    # display conversation history
    if show_conversation and "conversation_log" in article_data:
        # No icon: Streamlit renders the expander's icon slot as the raw
        # ligature name rather than a glyph, and the chevron already marks it.
        with st.expander(t("article.conversation")):
            _display_persona_conversations(
                conversation_log=article_data.get("conversation_log", {})
            )


def working_dir():
    """Where this user's articles live.

    Everything used to land in one shared folder, so every account would have
    seen every other account's work. Scoping by user id keeps them apart on
    disk as well as in the database.
    """
    root = os.path.join(get_demo_dir(), "DEMO_WORKING_DIR")
    return article_store.workspace(root, auth.user_id())


def get_demo_dir():
    return os.path.dirname(os.path.abspath(__file__))


def clear_other_page_session_state(page_index: Optional[int]):
    if page_index is None:
        keys_to_delete = [key for key in st.session_state if key.startswith("page")]
    else:
        keys_to_delete = [
            key
            for key in st.session_state
            if key.startswith("page") and f"page{page_index}" not in key
        ]
    for key in set(keys_to_delete):
        del st.session_state[key]


class LMConfigError(RuntimeError):
    """The language model settings do not describe a model we can call."""


# What each provider needs and what its ids look like. Gemini uses Google's
# SDK; the remaining providers use LiteLLM. The entries here are the
# ones with a key name of their own. Anything else that speaks the OpenAI API
# — z.ai, Together, a model served on your own machine — goes through
# "openai-compatible" with its own base URL.
PROVIDERS = {
    "gemini": {
        "key": "GOOGLE_API_KEY",
        "prefix": "gemini/",
        # The "-latest" aliases, not a pinned 2.x id: Google returns 404 for
        # those on keys created recently, even though list_models() lists them.
        "fast": "gemini-flash-lite-latest",
        "strong": "gemini-flash-latest",
    },
    "openrouter": {"key": "OPENROUTER_API_KEY", "prefix": "openrouter/"},
    "groq": {"key": "GROQ_API_KEY", "prefix": "groq/"},
    "openai": {"key": "OPENAI_API_KEY", "prefix": "openai/"},
    "openai-compatible": {
        "key": "LLM_API_KEY",
        "prefix": "openai/",
        "base": "LLM_API_BASE",
    },
}

# Two models, named for the work they do rather than for their size.
ROLES = ("FAST", "STRONG")

# What each role is allowed to spend on one reply. The fast role runs
# hundreds of times in a run and answers in a sentence; the strong role
# writes sections. The settings page probes a role with the same budget,
# so a model that cannot answer inside it fails the test rather than the
# run — a reasoning model can spend the whole of 500 on thinking and
# return an empty string, which is a working call that said nothing.
ROLE_TOKENS = {"FAST": 500, "STRONG": 3000}

# Set on a role to stop its model thinking before it answers. Thinking is
# spent from the same budget as the answer, so on the fast role's 500 tokens
# a model can use the lot and return nothing — billed, and silent.
#
# "off" rather than a boolean because the opposite is not "on": it is not
# sending the parameter at all, which is what a model with no thinking to
# turn off needs. OpenRouter's spelling; it is the only provider here whose
# models offer the choice.
NO_REASONING = {"reasoning": {"enabled": False}}


def resolve_role(role, default_provider, lookup=None):
    """(model id, call arguments) for one of the two roles.

    The provider's prefix is always applied. It is tempting to leave a name
    that already contains a slash alone, but OpenRouter's own ids look like
    "anthropic/claude-sonnet-4" — under that rule the call would go straight
    to Anthropic, with an OpenRouter key. A role that belongs somewhere else
    says so in LLM_<ROLE>_PROVIDER instead.

    `lookup` is where settings come from. It defaults to the saved settings,
    falling back to secrets and the environment; the settings page passes one
    of its own so a key can be tried before it is saved.
    """
    if lookup is None:
        lookup = model_settings.setting
    name = (lookup(f"LLM_{role}_PROVIDER") or default_provider).strip().lower()
    if name not in PROVIDERS:
        raise LMConfigError(
            f"{name!r} is not a provider this app knows. Choose one of: "
            + ", ".join(sorted(PROVIDERS))
        )
    provider = PROVIDERS[name]

    api_key = lookup(provider["key"])
    if not api_key:
        raise LMConfigError(
            f"{provider['key']} is missing, and the {role.lower()} model is "
            f"set to {name!r}, which reads its key from there."
        )

    model = lookup(f"LLM_{role}_MODEL") or provider.get(role.lower())
    if not model:
        raise LMConfigError(
            f"{name!r} ships no default models, so LLM_{role}_MODEL has to "
            "name one. Guessing an id here would fail in the middle of a run "
            "rather than before it starts."
        )

    kwargs = {
        "api_key": api_key,
        "temperature": 1.0,
        "top_p": 0.9,
        # Ride out the occasional 429 rather than failing the whole run.
        "num_retries": 6,
    }
    if (lookup(f"LLM_{role}_REASONING") or "").strip().lower() == "off":
        kwargs.update(NO_REASONING)
    if "base" in provider:
        base = lookup(provider["base"])
        if not base:
            raise LMConfigError(
                f"{provider['base']} is missing. {name!r} is any endpoint that "
                "speaks the OpenAI API, so it has to be told which one."
            )
        kwargs["api_base"] = base

    return provider["prefix"] + model, kwargs


def lm_settings(preset_id=None):
    """The two models to call, from secrets or the environment.

    Only LLM_PROVIDER has to be set, and only if it is not Gemini. Each role
    can override the provider as well as the model, so the questions can be
    asked somewhere cheap while the writing happens somewhere strong.

    `preset_id` names a model the admin put on offer and this run picked;
    it moves the strong role only. An id that no longer exists is ignored
    rather than failed on, so a preset withdrawn after someone chose it does
    not stop their next run.
    """
    lookup = model_settings.preset_lookup(preset_id) if preset_id else None
    default = model_settings.default_provider()
    return tuple(resolve_role(role, default, lookup=lookup) for role in ROLES)


def _settings_fingerprint(*calls):
    """A short digest of what the runner was built from.

    Keys are hashed rather than kept, so what sits in session state cannot be
    read back out of it.
    """
    parts = []
    for model, kwargs in calls:
        secret = f"{kwargs.get('api_key', '')}|{kwargs.get('api_base', '')}"
        thinking = "" if "reasoning" in kwargs else "+think"
        parts.append(
            f"{model}{thinking}:{hashlib.sha256(secret.encode()).hexdigest()[:12]}"
        )
    return "|".join(parts)


def build_lm(model, max_tokens, kwargs):
    """Use Google's current SDK for Gemini; keep LiteLLM for other providers."""
    if model.startswith("gemini/"):
        return GoogleModel(model=model.removeprefix("gemini/"), max_tokens=max_tokens, **kwargs)
    return LitellmModel(model=model, max_tokens=max_tokens, **kwargs)


def set_storm_runner():
    """Put a runner in session state, built from the current settings.

    Rebuilds when those settings change. The runner used to be built once and
    kept for the life of the browser session, so switching provider in
    secrets.toml changed nothing until the session was thrown away — the app
    went on calling the provider it was started with, and said so in that
    provider's own error message.
    """
    llm_configs = STORMWikiLMConfigs()
    (fast_model, fast_kwargs), (strong_model, strong_kwargs) = lm_settings(
        run_options.model()
    )

    # The run's own choices are part of what the runner was built from, so a
    # change of depth or sources between two runs rebuilds it the way a
    # change of provider does.
    fingerprint = (
        _settings_fingerprint((fast_model, fast_kwargs), (strong_model, strong_kwargs))
        + "|"
        + run_options.fingerprint()
    )
    current_working_dir = working_dir()
    if (
        "runner" in st.session_state
        and st.session_state.get("runner_settings") == fingerprint
        and st.session_state.get("runner_workspace") == current_working_dir
    ):
        return

    fast_lm = build_lm(fast_model, ROLE_TOKENS["FAST"], fast_kwargs)
    strong_lm = build_lm(strong_model, ROLE_TOKENS["STRONG"], strong_kwargs)

    llm_configs.set_conv_simulator_lm(fast_lm)
    llm_configs.set_question_asker_lm(fast_lm)
    llm_configs.set_outline_gen_lm(strong_lm)
    llm_configs.set_article_gen_lm(strong_lm)
    llm_configs.set_article_polish_lm(strong_lm)

    knobs = run_options.knobs()
    engine_args = STORMWikiRunnerArguments(
        output_dir=current_working_dir,
        max_conv_turn=knobs["max_conv_turn"],
        max_perspective=knobs["max_perspective"],
        search_top_k=knobs["search_top_k"],
        retrieve_top_k=knobs["retrieve_top_k"],
    )

    rm = search_sources.build_many(run_options.sources(), k=engine_args.search_top_k)

    st.session_state["runner"] = STORMWikiRunner(engine_args, llm_configs, rm)
    st.session_state["runner_settings"] = fingerprint
    st.session_state["runner_workspace"] = current_working_dir


@st.cache_data(show_spinner=False)
def _report_bytes(article_name, file_path_dict, mtime, lang):
    """The interactive report, cached on the run's own modification time.

    Streamlit needs a download button's payload on every rerun, so building
    the file inline would recompile the whole article on every click anywhere
    on the page. `mtime` is in the key so a re-run of the topic invalidates it.
    """
    return html_report.build_report(article_name, file_path_dict, lang).encode("utf-8")


def download_report_button(article_name, file_path_dict, article_path, key, short=False):
    """Hand over the whole run as one file that opens anywhere.

    The Markdown download beside it is the article's text alone; this is the
    article with the evidence and the interviews still attached, which is what
    makes it worth reading away from the app.
    """
    try:
        data = _report_bytes(
            article_name,
            file_path_dict,
            os.path.getmtime(article_path),
            ui_language.current(),
        )
    except (ValueError, OSError):
        # A run that stopped before the article was written has nothing to
        # compile. The Markdown button is already hidden in that case.
        return
    st.download_button(
        t("article.download_report_short" if short else "article.download_report"),
        data=data,
        file_name=html_report.report_filename(article_name),
        mime="text/html",
        icon=":material/find_in_page:",
        help=t("article.report_help"),
        key=key,
        width="stretch",
    )


def display_article_page(
    selected_article_name,
    selected_article_file_path_dict,
    show_title=True,
    show_main_article=True,
):
    if show_title:
        article_path = selected_article_file_path_dict.get(
            "storm_gen_article_polished.txt"
        ) or selected_article_file_path_dict.get("storm_gen_article.txt")
        meta = []
        if article_path and os.path.exists(article_path):
            length, sources, _ = ui_theme.summarize_article(
                article_path,
                selected_article_file_path_dict.get("url_to_info.json"),
                os.path.getmtime(article_path),
            )
            meta = [
                ("calendar_today", ui_theme.humanize_date(os.path.getmtime(article_path))),
                ("description", ui_theme.length_label(length)),
            ]
            if sources:
                meta.append(("layers", t("articles.sources", n=sources)))
        def head():
            st.markdown(
                f'<div class="article-head">'
                f"<h1>{selected_article_name.replace('_', ' ')}</h1>"
                f'<div class="meta">{ui_theme.chips(meta)}</div></div>',
                unsafe_allow_html=True,
            )
            if article_path and os.path.exists(article_path):
                # Two ways out of the app, on one row: the text, and the whole
                # run. The report goes first because it is the one worth
                # sending to someone else.
                report_col, markdown_col = st.columns(2, gap="small")
                with report_col:
                    download_report_button(
                        selected_article_name,
                        selected_article_file_path_dict,
                        article_path,
                        key="head_report",
                        short=True,
                    )
                with markdown_col:
                    st.download_button(
                        t("article.download_short"),
                        data=open(article_path).read(),
                        file_name=f"{selected_article_name}.md",
                        mime="text/markdown",
                        icon=":material/download:",
                        width="stretch",
                    )
            st.markdown('<div class="article-rule"></div>', unsafe_allow_html=True)

    else:
        head = None

    if not show_main_article:
        return

    # Two ways to read the same run. "Article" is the page the app has always
    # drawn — sidebar contents, references, the interviews underneath. "Report"
    # is the file the download button hands over, shown here rather than only
    # after a round trip through the reader's Downloads folder.
    view = st.segmented_control(
        t("article.view_label"),
        ["article", "report"],
        format_func=lambda name: t(f"article.view_{name}"),
        default="article",
        key=f"view_{selected_article_name}",
        label_visibility="collapsed",
    )
    if view == "report":
        _display_report_view(selected_article_name, selected_article_file_path_dict)
    else:
        _display_main_article(selected_article_file_path_dict, head=head)


def _display_report_view(article_name, file_path_dict):
    """The interactive report, embedded rather than downloaded.

    Through an iframe rather than `st.html`: the report is a small application
    — tabbed views, a source filter, citations that open what they cite — and
    none of that survives having its scripts stripped. The HTML is this app's
    own output, not anything a reader supplied.
    """
    try:
        html = _report_bytes(
            article_name,
            file_path_dict,
            os.path.getmtime(
                file_path_dict.get("storm_gen_article_polished.txt")
                or file_path_dict["storm_gen_article.txt"]
            ),
            ui_language.current(),
        ).decode("utf-8")
    except (ValueError, OSError, KeyError) as error:
        st.warning(t("article.view_failed"), icon=":material/warning:")
        st.code(str(error), language=None)
        return
    st.iframe(html, height=900)


def _in_script_run_ctx(method):
    """STORM fires callbacks from its worker threads, which have no Streamlit
    context; writing to a container from there raises RuntimeError. Re-attach
    the script run context captured when the handler was built."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._script_run_ctx is not None:
            add_script_run_ctx(threading.current_thread(), self._script_run_ctx)
        return method(self, *args, **kwargs)

    return wrapper


class StreamlitCallbackHandler(BaseCallbackHandler):
    def __init__(self, status_container):
        self.status_container = status_container
        self._script_run_ctx = get_script_run_ctx()

    @_in_script_run_ctx
    def on_identify_perspective_start(self, **kwargs):
        self.status_container.info(t("status.perspectives_start"))

    @_in_script_run_ctx
    def on_identify_perspective_end(self, perspectives: list[str], **kwargs):
        self.status_container.success(
            t("status.perspectives_end", perspectives="\n- ".join(perspectives))
        )

    @_in_script_run_ctx
    def on_information_gathering_start(self, **kwargs):
        self.status_container.info(t("status.browsing_start"))

    @_in_script_run_ctx
    def on_dialogue_turn_end(self, dlg_turn, **kwargs):
        urls = list(set([r.url for r in dlg_turn.search_results]))
        for url in urls:
            link = f'<a href="{url}" class="small-font" target="_blank">{url}</a>'
            self.status_container.markdown(
                f"""
                    <style>
                    .small-font {{
                        font-size: 14px;
                        margin: 0px;
                        padding: 0px;
                    }}
                    </style>
                    <div class="small-font">{t("status.browsed", link=link)}</div>
                    """,
                unsafe_allow_html=True,
            )

    @_in_script_run_ctx
    def on_information_gathering_end(self, **kwargs):
        self.status_container.success(t("status.browsing_end"))

    @_in_script_run_ctx
    def on_information_organization_start(self, **kwargs):
        self.status_container.info(t("status.organizing_start"))

    @_in_script_run_ctx
    def on_direct_outline_generation_end(self, outline: str, **kwargs):
        self.status_container.success(t("status.outline_internal"))

    @_in_script_run_ctx
    def on_outline_refinement_end(self, outline: str, **kwargs):
        self.status_container.success(t("status.outline_collected"))
