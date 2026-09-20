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

Upstream ignores parameters it does not know, so the publisher's image works
today and simply shows its own controls. The fork is where they go away.

## The fork this will run from

Following `Ups_openMAIC`: an own repository rather than a GitHub fork (a
repository GitHub classes as a fork does not run Actions until someone
enables them, and upstream's workflow triggers name upstream's branches),
with an `upstream` remote so a rebase can reach real history, and a pin file
here recording which upstream commit the work sits on.

What the fork has to add, in order of size:

1. `?embed=1` — a query flag read on mount that hides `LangSwitcher`,
   `ColorModeButton`, `GitHubButton` and `ConfigManager`.
2. `?lang=` and `?theme=` — set the locale and colour mode from the query
   instead of the visitor's stored preference.
3. `i18n/th.json` — the app ships en, ko, nl, zh.
4. `app.baseURL` — to sit under a path beside the main app, since a
   deployment host opens 443 and nothing else.

Until the fork's image exists, `image:` in the compose file is the
publisher's `anotia/deep-research-web:latest`.

## Search will fail until a Tavily key is set

`NUXT_TAVILY_API_KEY` in `.env` is blank: the key was typed into the Search
sources page's test box but never saved. Paste it there, or save it on that
page and regenerate `.env`.
