import base64
import datetime
import functools
import json
import os
import re
import threading
from typing import Optional

import markdown
import pytz
import streamlit as st
import auth
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
from knowledge_storm.lm import LitellmModel
from knowledge_storm.rm import DuckDuckGoSearchRM
from knowledge_storm.storm_wiki.modules.callback import BaseCallbackHandler
from knowledge_storm.utils import truncate_filename
from stoc import stoc


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
        articles_dict = {}
        for topic_name in os.listdir(articles_root_path):
            topic_path = os.path.join(articles_root_path, topic_name)
            if os.path.isdir(topic_path):
                # Initialize or update the dictionary for the topic
                articles_dict[topic_name] = {}
                # Iterate over all files within a topic directory
                for file_name in os.listdir(topic_path):
                    file_path = os.path.join(topic_path, file_name)
                    articles_dict[topic_name][file_name] = os.path.abspath(file_path)
        return articles_dict

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


def _display_references(citation_dict):
    if not citation_dict:
        st.caption(t("article.no_references"))
        return

    reference_list = [f"[{i}]" for i in range(1, len(citation_dict) + 1)]
    selected_key = st.selectbox(t("article.jump_reference"), reference_list)
    citation_val = citation_dict[reference_list.index(selected_key) + 1]
    title = citation_val["title"].replace("$", "\\$")
    st.markdown(
        f'<div class="ref-card"><div class="ref-title">{title}</div>'
        f'<div class="ref-url"><a href="{citation_val["url"]}" target="_blank">'
        f'{citation_val["url"]}</a></div></div>',
        unsafe_allow_html=True,
    )
    snippets = "\n\n".join(citation_val["snippets"]).replace("$", "\\$")
    st.caption(t("article.highlights"))
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
    selected_article_file_path_dict, show_reference=True, show_conversation=True
):
    article_data = DemoFileIOHelper.assemble_article_data(
        selected_article_file_path_dict
    )

    # Contents and references sit in a right-hand column beside the article
    # rather than in the sidebar, which the navigation now owns.
    # 173px of aside was too narrow for a wrapped Thai heading.
    body_column, aside_column = st.columns([2.5, 1], gap="large")

    with aside_column:
        toc_panel = st.container()
        references_panel = st.container()

    with toc_panel, st.container(border=True):
        ui_theme.aside_title(t("article.toc"))
        toc_target = st.container()

    with body_column:
        st.markdown('<div class="article-scroll">', unsafe_allow_html=True)
        with st.container(height=900, border=False):
            _display_main_article_text(
                article_text=article_data.get("article", ""),
                citation_dict=article_data.get("citations", {}),
                table_content_sidebar=toc_target,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # display reference panel
    if show_reference and "citations" in article_data:
        with references_panel, st.container(border=True):
            ui_theme.aside_title(t("article.references"))
            with st.container(height=420, border=False):
                _display_references(citation_dict=article_data.get("citations", {}))

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
    owner = auth.user_id()
    path = os.path.join(root, owner) if owner else root
    os.makedirs(path, exist_ok=True)
    return path


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


def set_storm_runner():
    current_working_dir = working_dir()

    # configure STORM runner with Google Gemini + DuckDuckGo
    llm_configs = STORMWikiLMConfigs()
    gemini_kwargs = {
        "api_key": st.secrets["GOOGLE_API_KEY"],
        "temperature": 1.0,
        "top_p": 0.9,
        # Ride out the occasional 429 rather than failing the whole run.
        "num_retries": 6,
    }
    # Use the "-latest" aliases: pinned 2.x ids are 404/quota-blocked for new API keys.
    fast_lm = LitellmModel(
        model="gemini/gemini-flash-lite-latest", max_tokens=500, **gemini_kwargs
    )
    strong_lm = LitellmModel(
        model="gemini/gemini-flash-latest", max_tokens=3000, **gemini_kwargs
    )

    llm_configs.set_conv_simulator_lm(fast_lm)
    llm_configs.set_question_asker_lm(fast_lm)
    llm_configs.set_outline_gen_lm(strong_lm)
    llm_configs.set_article_gen_lm(strong_lm)
    llm_configs.set_article_polish_lm(strong_lm)

    engine_args = STORMWikiRunnerArguments(
        output_dir=current_working_dir,
        max_conv_turn=3,
        max_perspective=3,
        search_top_k=3,
        retrieve_top_k=5,
    )

    rm = DuckDuckGoSearchRM(k=engine_args.search_top_k, safe_search="On", region="us-en")

    runner = STORMWikiRunner(engine_args, llm_configs, rm)
    st.session_state["runner"] = runner


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
                ui_theme.humanize_date(os.path.getmtime(article_path)),
                ui_theme.length_label(length),
            ]
            if sources:
                meta.append(t("articles.sources", n=sources))
        st.markdown(
            f'<div class="article-head">'
            f"<h1>{selected_article_name.replace('_', ' ')}</h1>"
            f'<div class="meta">{ui_theme.chips(meta)}</div></div>',
            unsafe_allow_html=True,
        )
        if article_path and os.path.exists(article_path):
            st.download_button(
                t("article.download"),
                data=open(article_path).read(),
                file_name=f"{selected_article_name}.md",
                mime="text/markdown",
            )

    if show_main_article:
        _display_main_article(selected_article_file_path_dict)


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
