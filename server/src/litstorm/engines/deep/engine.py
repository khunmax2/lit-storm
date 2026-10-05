"""Deep Research (khunmax2/lit_deep-research-web) as an Engine.

The fork's research runs in Node. Its CLI (cli/litstorm.ts, bundled into
one file in the Worker image) is started as a subprocess of this Run's own
process (docs/adr/0004): the config goes in as one JSON line on stdin, the
keys in its environment only, and what it does comes back as JSON lines.

Stopping is killing it: this process checks for a stop while it waits, and
if this process is killed, the CLI sees its stdin close and exits too.

Breadth and depth come from the depth level; research stops at 80% of the
level's target and the report is written from what was learned by then.
Each learning keeps the passage it came from, which becomes the report's
Evidence.
"""

import json
import os
import queue
import subprocess
import threading
import time

from litstorm import instructions, outcomes
from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs
from litstorm.engines import sources
from litstorm.engines.base import Cancelled, EngineFailure

from litstorm.engines.agent import normalize

CLI = os.environ.get("LITSTORM_DEEP_CLI", "/opt/deep-research/litstorm-deep.mjs")
NODE = os.environ.get("LITSTORM_NODE", "node")
GATHER_SHARE = 0.8
DEFAULTS = {"breadth": 3, "depth": 2}

# Our providers in the fork's terms.
AI = {
    "openrouter": ("openrouter", None),
    "openai": ("openai", "https://api.openai.com/v1"),
    "gemini": ("openai-compatible", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "groq": ("openai-compatible", "https://api.groq.com/openai/v1"),
    "openai-compatible": ("openai-compatible", None),
}
SEARCH = {"searxng": "searxng", "tavily": "tavily"}


def cli_input(config, secrets, bridge=None):
    """The CLI's config line, and its environment. With a SearchBridge the
    CLI searches the Run's sources through it, as if it were a SearXNG."""
    llm = config.llm
    provider, base = AI.get(llm.get("provider"), (None, None))
    if provider is None:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, f"Deep Research cannot use {llm.get('provider')!r}")
    base = llm.get("api_base") if llm.get("provider") == "openai-compatible" else base
    extra = dict(reasoning_kwargs(llm.get("reasoning"), llm["provider"]))
    extra.update(routing_kwargs(llm["provider"], extra).get("extra_body", {}))

    if bridge is not None:
        search, endpoint, engines, search_key = "searxng", bridge.url, None, ""
    else:
        search = SEARCH.get(config.search.get("provider"))
        if search is None:
            raise EngineFailure(outcomes.BAD_CONFIGURATION, f"Deep Research cannot search with {config.search.get('provider')!r}")
        endpoint, engines, search_key = config.search.get("endpoint"), config.search.get("engines"), secrets.search_api_key
    params = {**DEFAULTS, **(config.params or {})}
    query = config.topic
    focus = instructions.focus(config)
    if focus:
        query += f"\n\nFocus: {focus}"
    if instructions.style(config):
        query += f"\n\nWriting style: {instructions.style(config)}"
    line = {
        "query": query,
        "language": config.language,
        "breadth": int(params["breadth"]),
        "depth": int(params["depth"]),
        "gatherMs": int((config.target_seconds or 300) * GATHER_SHARE * 1000),
        "ai": {"provider": provider, "model": llm["model"], "apiBase": base, "extraBody": extra or None},
        "search": {"provider": search, "apiBase": endpoint, "engines": engines},
    }
    # Its own small environment: never the Worker's, which holds its secrets.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LITSTORM_AI_API_KEY": secrets.llm_api_key,
        "LITSTORM_SEARCH_API_KEY": search_key,
    }
    # Windows (where the tests run) opens no socket without it, the search
    # bridge's included; on Linux it is not set.
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return line, env


class DeepEngine:
    name = "deep"

    def run(self, config, secrets, workspace, progress, cancel):
        with sources.bridge_for(config, secrets, SEARCH) as bridge:
            return self._run(config, secrets, workspace, progress, cancel, bridge)

    def _run(self, config, secrets, workspace, progress, cancel, bridge):
        line, env = cli_input(config, secrets, bridge)
        model_name = LLM_PROVIDERS[config.llm["provider"]]["prefix"] + config.llm["model"]
        search_name = "SearXNG" if line["search"]["provider"] == "searxng" else "Tavily"
        stderr = open(os.path.join(workspace, "deep-research.log"), "wb")
        proc = subprocess.Popen(
            [NODE, CLI], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, env=env,
        )
        proc.stdin.write((json.dumps(line, ensure_ascii=False) + "\n").encode())
        proc.stdin.flush()  # left open: its closing tells the CLI we are gone

        lines = queue.Queue()

        def read():
            for raw in proc.stdout:
                lines.put(raw)
            lines.put(None)

        threading.Thread(target=read, daemon=True).start()

        tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        searches = 0
        stage = None
        result = None
        failure = None

        def flush(name):
            nonlocal tokens, searches
            if name:
                # Through the bridge, its count by source; else the CLI's own.
                search = bridge.usage() if bridge is not None else {search_name: searches}
                progress.usage(name, llm={model_name: tokens}, search=search)
            tokens, searches = {"prompt_tokens": 0, "completion_tokens": 0}, 0

        try:
            while True:
                try:
                    raw = lines.get(timeout=1)
                except queue.Empty:
                    if cancel.requested():
                        proc.kill()
                        raise Cancelled()
                    continue
                if raw is None:
                    break
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                kind = event.get("type")
                if kind == "stage":
                    cancel.check()
                    flush(stage)
                    stage = event["stage"]
                    progress.stage(stage)
                elif kind == "usage":
                    tokens["prompt_tokens"] += int(event.get("promptTokens") or 0)
                    tokens["completion_tokens"] += int(event.get("completionTokens") or 0)
                elif kind == "searched":
                    searches += 1
                    if event.get("urls"):
                        progress.note("browsed", urls=sorted(set(event["urls"])))
                elif kind == "node":
                    # One node of the research tree: kept with the Run, so the
                    # canvas can draw it while it grows and after (web: ResearchCanvas).
                    progress.note(
                        "tree",
                        **{k: event[k] for k in ("id", "parent", "status", "query", "goal", "sources", "learnings", "message")
                           if event.get(k) is not None},
                    )
                elif kind == "cut_short":
                    progress.note("research_cut_short", learnings=event.get("learnings"))
                elif kind == "report":
                    result = event
                elif kind == "error":
                    failure = event.get("message", "the research failed")
        finally:
            flush(stage)
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            stderr.close()

        if result is None:
            if failure and "nothing it could use" in failure:
                raise EngineFailure(outcomes.EMPTY_REPORT, failure)
            raise EngineFailure(outcomes.ENGINE_ERROR, failure or f"the research process exited with {proc.returncode}")

        with open(os.path.join(workspace, "report.md"), "w", encoding="utf-8") as f:
            f.write(result["markdown"])
        progress.stage("normalize")
        learnings = result.get("learnings") or []
        refs = {i + 1: item["url"] for i, item in enumerate(learnings) if item.get("url")}
        found = {item["url"]: {"title": item.get("title", "")} for item in learnings if item.get("url")}
        evidence = {}
        for item in learnings:
            passage = (item.get("excerpt") or item.get("learning") or "").strip()
            if item.get("url") and passage and passage not in evidence.setdefault(item["url"], []):
                evidence[item["url"]].append(passage)
        report = normalize.normalize(
            result["markdown"], config.topic, config.language, found, refs=refs, evidence=evidence, engine="deep"
        )
        if not report["sources"]:
            raise EngineFailure(outcomes.EMPTY_REPORT, "the report cites none of what the research learned")
        return report
