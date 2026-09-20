# Handoff — lit-storm, 2026-09-20

Written at the end of a macOS session, for whoever picks this up on Windows.
Everything described here is merged to `main` (`e9217bc`) unless a section says
otherwise. CI is green for the first time in this repository's history.

---

## 1. Where the work stands

Five pull requests, all merged:

| PR | Commit | What landed |
|----|--------|-------------|
| [#1](https://github.com/khunmax2/lit-storm/pull/1) | `ad901c8` | Co-STORM round table: a discussion you can interrupt |
| [#2](https://github.com/khunmax2/lit-storm/pull/2) | `cf06334` | Interactive HTML report, and a second way to read an article |
| [#3](https://github.com/khunmax2/lit-storm/pull/3) | `1d7508a` | Member management, google.genai migration, delete-to-trash |
| [#4](https://github.com/khunmax2/lit-storm/pull/4) | `947ef64`, `60f2170` | Run-ledger fix; Black formatting (CI green) |
| [#5](https://github.com/khunmax2/lit-storm/pull/5) | `1a757c8` | `.gitattributes`, LF everywhere |

PRs #1–#3 were merged over a **red CI check** that nobody looked at. #4 fixed
the cause. Check `gh pr checks <n>` before merging from here on.

### The app now has two engines behind one door

`Home` asks which, where the hero's eyebrow used to read "Powered by STORM":

- **STORM** — runs to completion on its own, hands back a cited article.
- **Co-STORM** — a panel discusses the topic while you watch, interrupt and
  steer; you ask for the report when the table has covered enough.

The switch is hidden while either engine is mid-flight, because at that point
it is not a way to change your mind, it is a way to lose ten minutes of work.

---

## 2. Running it

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r frontend/demo_light/requirements.txt
.venv/bin/streamlit run frontend/demo_light/storm.py --server.runOnSave true
```

Python 3.14.3 here. `.claude/launch.json` holds three dev configurations; its
paths are absolute macOS paths and **will need rewriting on Windows**:

| Config | Port | Sign-in | Use for |
|---|---|---|---|
| `storm-demo` | 8512 | bypassed (`STORM_DEV_USER=1`) | fast iteration |
| `storm-demo-nodev` | 8513 | real | anything touching accounts or RLS |
| `storm-demo-real` | 8512 | real | — |

`--server.runOnSave true` is on all three. It is not optional: without it,
Streamlit does not reload an edited *imported module*, so a change appears to
do nothing until the server is restarted. `watchdog` is also required, and
installed here — on Windows install it before wondering why edits do nothing.

**`runOnSave` has a cost worth knowing.** Saving a file during a Co-STORM warm
start restarts the script and kills the run. Do not edit while a discussion is
warming. This was learned twice, expensively.

---

## 3. What a new machine needs

### Secrets — `frontend/demo_light/.streamlit/secrets.toml`

Gitignored, so it does not travel. Recreate it with:

```
LLM_PROVIDER, GOOGLE_API_KEY, LLM_STRONG_MODEL
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SECRET_KEY
```

`LLM_STRONG_MODEL = "gemini-3.6-flash"`, pinned deliberately — see §5.

`SUPABASE_SECRET_KEY` is a server-only key that bypasses row-level security.
It enables admin account creation and must never reach a browser.

### Database

`docs/supabase-schema.sql` is applied to the live project already. A fresh
project needs it applied, then one admin promoted by hand:

```sql
update public.profiles set role = 'admin' where email = 'you@example.com';
```

### Tests

```
.venv/bin/python -m unittest discover -s tests
```

42 tests, all passing. `tests/test_member_database.py` needs real PostgreSQL
binaries — **it skips silently if they are missing**, so a green run on a
machine without Postgres is really 34 tests, not 42. On Windows, run Postgres
in Docker and check the count.

---

## 4. Verified, and not

### Verified by running it against live services

- A full Co-STORM discussion end to end: warm start (15 turns, 69 sources), a
  typed question answered on topic, a suggested question clicked and answered,
  the report written and opened in the library.
- Member management as a real signed-in admin: the roster reads from the
  database, the signed-in account's own role and status controls are disabled,
  another member's quota edited 10 → 15 → 10, each save landing in
  `profiles` with a matching `member_audit_log` row carrying before/after.
- Schema probes: `member_audit_log` and `admin_creation_ready` exist and
  correctly refuse the anon role.
- Interface language surviving a real browser refresh.
- Black and the 42 tests.

### Not verified — do these first

- **Creating a member.** The form is enabled (`admin_creation_configured()` is
  true, `admin_creation_ready()` passes) but no account was ever created, on
  purpose. The thing to watch: creating a member must **not** sign the admin
  out. That is what the backend-client path exists to prevent.
- **Self-demotion and self-suspension being refused by the database.** The UI
  locks those controls, so the rule underneath was never exercised through the
  app. `tests/test_member_database.py` covers it against a local Postgres.
- **Tavily.** Three real bugs fixed in `TavilySearchRM` (§5) and verified
  against the exact input that used to crash it, but never against a live
  Tavily key. A key exists; the test is one click on the Search sources page.
- **Any provider other than Gemini.**

---

## 5. Things that will bite, and why they are the way they are

### The model is pinned for a reason

`gemini-flash-latest` resolves to `gemini-3.7-flash`, which was returning 503s
and taking 30–57 seconds for a one-word prompt. Everything else answered in
1–8 seconds. `LLM_STRONG_MODEL` is pinned to `gemini-3.6-flash` to get off
that alias. Re-measure before unpinning.

Co-STORM's strong role runs at `max_tokens=3000`, not the paper's 1000:
reasoning models spend part of the budget thinking before writing, and at 1000
the answers came back truncated or empty.

### A discussion is 70–100 model calls

Roughly: 21 for the expert interviews, 2 for the outline, 21–40 to file each
snippet into the mind map, then **one call per mind-map node, twice** — once to
draft the report and once to turn it into the opening conversation. The last
two scale with the size of the map, which is why a warm start can take 15
minutes. If it needs to be faster, `warmstart_max_num_experts` and
`max_search_queries_per_turn` in `costorm.py` are the knobs.

### Library bugs fixed here, upstream unaware

- `knowledge_storm/encoder.py` — added Gemini. It knew only OpenAI and Azure,
  so a Gemini deployment could not build a mind map at all.
- `knowledge_storm/logging_wrapper.py` — `log_pipeline_stage` swallowed every
  exception without re-raising, so `generate_report` returned `None` with the
  cause printed nowhere. This is worth remembering: it hid a real failure for
  an hour.
- `knowledge_storm/dataclass.py` — `replace("[-1]", "")` called twice with both
  results discarded, inside a loop that does not run for a turn citing nothing.
- `knowledge_storm/rm.py` — `TavilySearchRM` named `result` in its own `except`
  clause where it is unbound if the *first* result is the one that failed,
  turning a skippable result into an `UnboundLocalError` that killed the whole
  search. Its `args` dict was also built and never passed, so `k` and
  `include_raw_content` had never once been honoured, and it read
  `raw_body_content` where Tavily sends `raw_content`.

All four are local changes to a vendored library. Upstream does not have them.

### The run ledger counted attempts, not discussions

Fixed in `947ef64`, but read it before touching `_warm_start`: `"warming"` is
the state for the whole warm start, so any rerun inside that window used to
re-enter from the top and open another ledger row. One topic produced 17 rows;
the account read 22 of 20 runs used for a month in which it started six. The
row id now lives in session state and is written only when absent.

The affected rows were reconciled in the database on 2026-09-20: 19 stuck at
`running` closed as `failed`, and 16 duplicates of one topic deleted. A backup
of the deleted rows was written to a session scratchpad that **no longer
exists** — it was not kept. The remaining ledger is correct.

### Search quality is capped by DuckDuckGo

The current source is DuckDuckGo, which is being rate-limited: Google and
Brave return 429 on most queries and results come from the fallbacks
(startpage, yandex, wikipedia, mojeek). A Tavily or Serper key would fix this
more cheaply than anything else on this list.

---

## 6. Next: four repositories

Cloned alongside this one, not yet integrated:

```
/Users/attapon/Project/antigravity/searxng
/Users/attapon/Project/antigravity/searxng-LDR-academic
/Users/attapon/Project/antigravity/deep-research-web-ui
/Users/attapon/Project/antigravity/agents-deep-research
```

The intent: the two SearXNG repositories become search-source options beside
the existing ones; the two deep-research repositories become engines beside
STORM and Co-STORM.

### What is already true

**STORM already supports SearXNG.** `class SearXNG` in
`knowledge_storm/rm.py:644` takes a `searxng_api_url`. Wiring it into
`frontend/demo_light/search_sources.py` is a small job, and it can point at a
remote instance — nothing has to run locally for this to work.

**`agents-deep-research` can be an engine the way Co-STORM is.** It is a Python
package, and `deep_researcher/llm_config.py` already supports Gemini and
OpenRouter, so it will not repeat the encoder fight.

**`deep-research-web-ui` cannot.** It is a Nuxt 4 application with its own UI,
not a library. Making it a tab means an iframe or a link, which is an
architecture decision nobody has made yet.

### The academic SearXNG fork — a correction

This document's author twice claimed that `searxng-LDR-academic` differs from
upstream SearXNG "only in configuration". **That is wrong.** Diffed against its
real merge-base (`b876d0be`, 2025-11-21):

- **74 files changed in `searx/`, +360 / −7,823**
- Dozens of engines deleted outright — spotify, steam, youtube_api,
  youtube_noapi, vimeo, unsplash, wallhaven, zlibrary, torznab, tokyotoshokan,
  tootfinder, yandex_music
- The torrent result template removed entirely
- `settings.yml` rewritten wholesale (−985)
- Templates and CSS changed: `base.html`, `index.html`,
  `page_with_header.html`, `index.less`
- nginx/uwsgi/httpd deployment templates deleted
- Container build changed

It is not SearXNG with academic engines switched on. It is SearXNG **cut down**
to academic work and rebranded. A single-repository, two-profile approach will
not reproduce it.

The mistake came from reading `git log --name-only` over the last 25 commits
of a fork that diverged ten months ago. Diff against the merge-base.

**It is also stale**: last commit 2026-02-17, diverged 2025-11-21. Upstream
SearXNG is active weekly, and its engines break often as target sites change.
Rebasing ten months of divergence across deleted files will not be pleasant.

Two ways forward, undecided:

1. Take the fork whole and rebase it onto current upstream.
2. Read what it selected and re-cut it from current upstream.

(2) is probably less total work and gives newer engines, but nobody has yet
looked at what its `settings.yml` actually enables. Do that before choosing.

### Repository layout

Follow the pattern already proven in `Upstream_Deeptutor` / `Ups_openMAIC`:
an own repository rather than a GitHub fork, because — quoting
`deploy/openmaic-patches/openmaic-pin.json` —

> a repository GitHub classes as a fork does not run Actions until someone
> enables them by hand, and upstream's workflow triggers name upstream's
> branches

with the `upstream` remote kept so a rebase can still reach real history, and a
`*-pin.json` recording which upstream commit the work sits on, checked by a
contract script that *reports* drift rather than forcing a move.

Suggested names, matching the existing `Ups_` prefix: `Ups_searxng`,
`Ups_searxng_academic`, `Ups_agents_research`, `Ups_research_ui`.

### The machine

This was assessed on the macOS machine and is the reason for the move:

| | macOS (here) | Windows (target) |
|---|---|---|
| RAM | 8 GB, 5.4 of 6 GB swap already used | 32 GB |
| Disk free | 20 GB of 228 GB | ? |
| Docker | installed, daemon not running | yes |

Running all four services beside this app needs roughly 1.5–3.5 GB of RAM and
2–4 GB of disk beyond what exists. 32 GB is comfortable. Check disk: Docker
Desktop with WSL2, a torch-bearing venv, Nuxt's `node_modules` and SearXNG
images together want 10–15 GB, and 40–50 GB free would be comfortable.

Note that `.venv` here is **1.9 GB**, over half of it torch, pulled in by
`sentence-transformers` in the root `requirements.txt`.

---

## 7. Open, unstarted

- A Co-STORM discussion does not survive a browser refresh; it lives in
  Streamlit session state. `CoStormRunner.to_dict()` exists, but `from_dict()`
  carries a FIXME — it ignores the saved `lm_config` and calls
  `lm_config.init(lm_type=os.getenv("OPENAI_API_TYPE"))`, which fails on
  Gemini. Persisting a discussion means writing the way back by hand.
- No CI runs the tests. `python-package.yml` is `workflow_dispatch` only, and
  `format-check.yml` runs Black over `knowledge_storm` alone — nothing checks
  `frontend/`. Adding a test job needs a Postgres service container.
- The admin account's own quota was 22 of 20 before the ledger was reconciled;
  it now reads 6 of 20. Nothing enforces the limit retroactively.
- `docs/` in this repository has no `CONTEXT.md` or `adr/`, unlike
  `Upstream_Deeptutor`. If this grows, it will want them.
