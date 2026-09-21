# Deep Research, framed

[deep-research-web-ui](https://github.com/AnotiaWang/deep-research-web-ui) as
the app's third engine: an iterative researcher with a live research tree,
running in its own container and shown in a tab.

## Why a sibling and not an engine

The other two engines are Python this app calls. This one is a Nuxt 4
application with its own UI, which cannot become part of a Streamlit page
any more than OpenMAIC could become part of DeepWitya — the reasoning is
ADR-0005 in `Upstream_Deeptutor`, whose first attempt (a git subtree,
2,832 files) was torn out before this shape was settled on.

So: its own container, coupled to this app by **one URL and three query
parameters**. Providers, keys, search and history stay on its side. The
main app frames it with `st.iframe`.

## Running it

```bash
docker compose --env-file .env up -d
```

`.env` is gitignored. It carries the Gemini key through Gemini's
OpenAI-compatible endpoint (the app has no native Gemini provider), and the
one search provider both applications support:

| Setting | Value |
| --- | --- |
| `NUXT_PUBLIC_SERVER_MODE` | `true` — keys live here, not in the visitor's browser |
| `NUXT_PUBLIC_AI_PROVIDER` | `openai-compatible` |
| `NUXT_AI_API_BASE` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `NUXT_PUBLIC_WEB_SEARCH_PROVIDER` | `tavily` — the only overlap with this app's sources |

Listens on `127.0.0.1:3100`. The main app reads `RESEARCH_UI_URL` and
defaults to that.

**Verified:** `gemini-3.6-flash` answers through the OpenAI-compatible
endpoint in 4.5s; the page serves with no `X-Frame-Options` or
`frame-ancestors`, so it can be framed as-is.

## What the frame is told

The main app opens `/?embed=1&lang=<en|th>&theme=<light|dark>`. This is the
arrangement OpenMAIC's fork honours and this one's will:

- `embed=1` — hide its own language switcher, theme button, GitHub link and
  settings panel. Two sets of those in one window is how an embed announces
  itself as a second application.
- `lang`, `theme` — match the page around it. Read once on mount, so a
  change reloads the frame and a run in progress is lost. Accepted: changing
  either is a deliberate, infrequent act.

## The fork it runs from

[khunmax2/lit_deep-research-web](https://github.com/khunmax2/lit_deep-research-web),
following `Ups_openMAIC`: an own repository rather than a GitHub fork (a
repository GitHub classes as a fork does not run Actions until someone
enables them, and upstream's workflow triggers name upstream's branches),
with an `upstream` remote so a rebase can reach real history.

`research-ui-pin.json` records the fork commit this repo expects, the
upstream commit it is level with, and the image. `check_research_ui_contract.py`
compares a checkout against it and **reports** the distance — it does not
force a move:

```
python deploy/research-ui/check_research_ui_contract.py ../deep-research-web-ui
```

What the fork adds over upstream, in one commit:

- `app/composables/useEmbed.ts` — reads `?embed`, `?lang`, `?theme` once on
  mount.
- `?embed=1` hides `LangSwitcher`, `ColorModeButton`, `GitHubButton` and
  `ConfigManager`. History stays; it is the page's own.
- `i18n/th.json` — 194 strings, key-for-key with `en.json`.

Base path needs no code: Nuxt reads `NUXT_APP_BASE_URL` at runtime, and the
compose file exposes it as `RESEARCH_UI_BASE_PATH`.

## The image

The fork's own workflow (`.github/workflows/image.yml`) builds and pushes
`ghcr.io/khunmax2/lit_deep-research-web` on every push to main, tagged by
short sha and `latest`, and prints the digest in the run summary. The
compose file pins that digest; `research-ui-pin.json` records it.

The inherited upstream workflows are gone: one pushed to the author's
Docker Hub with secrets this repository does not have and failed on every
push, the other would have merged upstream into main nightly.

**The package is private until its visibility is set to public** — GitHub
creates it that way. Until then `docker compose pull` gets `unauthorized`.
Fix once, in the browser: the package's settings → Danger Zone → Change
visibility → Public. Or build locally and override:

```
docker build -t lit-storm/research-ui:latest ../../../deep-research-web-ui
RESEARCH_UI_IMAGE=lit-storm/research-ui:latest docker compose --env-file .env up -d
```

## Its model settings do not follow the main app's

`.env` is written by hand and read by the container **when it starts**.
Nothing propagates: changing a key on the Models page leaves this stack on
whatever it was started with, and the symptom is a stale key failing in a
tab that looks like part of the same application. After editing `.env`:

```
RESEARCH_UI_IMAGE=lit-storm/research-ui:searxng docker compose --env-file .env up -d --force-recreate
```

(the override is only needed while the GHCR package is private.)

This ran on the main app's `GOOGLE_API_KEY` first, and that is worth not
repeating. On Gemini's free tier one key is one quota for both
applications, and Deep Research spends it fast: every research node is
several model calls, and a depth-1 breadth-1 run was enough to reach
`429 You exceeded your current quota` — which then stops the main app too,
on its next run, for a reason that has nothing to do with it.

It now points at OpenRouter, which is a paid account rather than a shared
free quota, through the same `openai-compatible` provider:

```
NUXT_PUBLIC_AI_PROVIDER=openai-compatible
NUXT_AI_API_BASE=https://openrouter.ai/api/v1
NUXT_AI_API_KEY=sk-or-v1-…
NUXT_PUBLIC_AI_MODEL=deepseek/deepseek-v4.1-flash
```

A reasoning model puts its thinking in the completion before any answer,
so a small `max_tokens` returns an empty `content` with `finish_reason:
stop` — reachable, paid for, and silent. If this model is swapped for
another, check a reply comes back rather than that the call succeeded.

## Search: the same SearXNG the main app uses

Upstream searches with tavily, firecrawl, crw, google-pse, youcom or
serply — every one either a paid key or a daily quota, and none of them
what the main app is configured with. So the fork adds SearXNG as a
seventh provider, and this stack points at the instance `deploy/searxng`
already runs: no key, no quota, and one search service for both
applications instead of two bills.

```
NUXT_PUBLIC_WEB_SEARCH_PROVIDER=searxng
NUXT_WEB_SEARCH_API_BASE=http://host.docker.internal:8080
NUXT_PUBLIC_SEARXNG_ENGINES=          # optional: arxiv,pubmed,… to narrow it
```

`host.docker.internal` because the instance is published on the host's
loopback, not on this compose network. On a deployment where both sit on
one network, use the service name.

The address is an address, not a secret, so it goes in `NUXT_WEB_SEARCH_API_BASE`
and the API-key box stays empty. An instance behind a token can still use
one: it is sent as a bearer header.
