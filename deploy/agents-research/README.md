# Agent Research — the fourth engine

[qx-labs/agents-deep-research](https://github.com/qx-labs/agents-deep-research),
Apache-2.0. It plans a report, researches each part in a loop until it stops
finding gaps, then writes it up — a fourth way to answer the same request the
other three answer, which is the whole reason it is here.

A sibling application, the shape ADR-0005 settled on: its own container,
coupled to the main app by a URL and nothing else. Its models, its search and
its reports stay on its side.

```
docker compose up -d agents-research     # from deploy/
```

It answers at `/agents/` through the stack's edge proxy, and the app
frames it in the **Agent Research** tab. It publishes no port of its own.

## Upstream is a library; the web surface is ours

There is no web UI upstream at all — a package and a CLI. Our copy
([khunmax2/lit_agents-deep-research](https://github.com/khunmax2/lit_agents-deep-research),
pinned in `agents-research-pin.json`) adds `web/`: a page, a live progress
feed and the report. It is kept outside `deep_researcher/` so a merge from
upstream cannot collide with it.

**The repository is private**, so there is no GHCR image yet and the stack
builds from the checkout at `../../agents-deep-research`. Make it public and
this can pin a digest like the other sibling.

## Two changes to upstream, and why

**`openrouter.ai` added to `structured_output_providers`.** Without it every
OpenRouter model took the text fallback — the JSON schema goes into the
prompt and the parser takes the first JSON object it finds in the reply.
Both `gpt-4o-mini` and `deepseek-v4.1-flash` restate the schema before
answering, so every run died on the first agent with *"2 validation errors
for KnowledgeGapOutput"*.

**Progress by subclassing, not patching.** `_log_message` is the one place
both researchers announce what they are doing, and it is a method, so
`web/server.py` overrides it. Nothing upstream changes and nothing has to be
re-applied after a merge.

`check_agents_research_contract.py` watches both, plus the three frame
parameters and `/healthz`. It reports; it does not gate.

```
python check_agents_research_contract.py
```

## Its fast model is not STORM's, and cannot be

`FAST_MODEL` drives this library's tool calls, and not every model that
works for STORM works here:

| model | result |
| --- | --- |
| `openai/gpt-4o-mini` | works |
| `meta-llama/llama-4-scout` | **404 on every tool call** |

OpenRouter lists `tools` support for both, so this is not a capability
lookup away — it was found by running it. The default is `gpt-4o-mini` for
that reason. The reasoning and main models are the stack's usual
`deepseek-v4.1-flash`.

## Search is the stack's SearXNG

`SEARCH_PROVIDER=searchxng` — upstream's spelling of the name, typo and all
— pointed at `http://searxng:8080`. No key, no quota, one instance for all
four engines.

## Reports are not kept

Runs live in the container's memory and a restart loses them. That is the
right trade for a sibling whose reports are read once and copied out;
persistence would mean a volume, a schema and a retention question, none of
which this needs yet. The tab says so.

## Verified

Against this stack, through the app's tab:

- a Thai query returned an 8,333 character report, 26 headings, citing
  UNESCO, OECD.ai and moe.go.th, in 307s
- `/healthz` answers `{"status":"ok","model_key":true,"search":"searchxng"}`
- `?embed=1&lang=en&theme=dark` hides the page's own controls and applies
  both — checked in the browser, not just in the source
- with the container stopped, the tab says so and offers a retry, instead
  of framing a browser error page
