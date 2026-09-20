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

## Building the image

```
docker build -t lit-storm/research-ui:<commit> -t lit-storm/research-ui:latest ../../../deep-research-web-ui
```

The compose file runs `lit-storm/research-ui:latest` (override with
`RESEARCH_UI_IMAGE`). Until an image is pushed to a registry, this is a
local build and the pin carries no digest; the publisher's
`anotia/deep-research-web:latest` still works as a fallback — it just shows
its own controls in the frame.

## Search needs a provider both apps have

This app searches with tavily, firecrawl, crw, google-pse, youcom or serply.
The main app's saved source is Brave, which this one does not speak — so
`NUXT_TAVILY_API_KEY` in `.env` is blank and search fails until one of:

- a Tavily key is saved on the main app's Search sources page (press **Use
  this**, not just **Test**) and `.env` is regenerated from it;
- `NUXT_PUBLIC_WEB_SEARCH_PROVIDER=youcom`, which works with no key on a
  daily quota.
