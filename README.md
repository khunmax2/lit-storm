<p align="center">
  <img src="assets/logo.svg" style="width: 25%; height: auto;">
</p>

# lit-storm

A deployable research assistant built on [stanford-oval/storm](https://github.com/stanford-oval/storm). Give it a topic; it researches from several perspectives, gathers sources from the web, and writes a cited, encyclopedia-style article.

Upstream is a research codebase you drive from Python. This fork turns it into something a team can sign in to and use: accounts and per-member quotas, a settings UI instead of code edits, two research engines behind one door, and a self-contained HTML report you can mail to someone.

| | STORM | Co-STORM | Deep Research |
| --- | --- | --- | --- |
| How it runs | Start to finish on its own | A panel discusses, one turn at a time | Iterates: search, read, ask, search again |
| Your role | Give a topic, wait | Watch, interrupt, steer | Answer its clarifying questions, watch the tree grow |
| Report | Handed back at the end | Written when you decide the table has covered enough | Written from the tree when it stops |
| What it is | This app | This app | A sibling application, framed — [deploy/research-ui](deploy/research-ui/README.md) |

<p align="center">
| <a href="https://arxiv.org/abs/2402.14207"><b>STORM paper</b></a> | <a href="https://www.arxiv.org/abs/2408.15232"><b>Co-STORM paper</b></a> | <a href="https://storm-project.stanford.edu/"><b>Upstream project site</b></a> |
</p>

---

## What this fork adds

Diffed against upstream `fb951af` (2025-09-30), where upstream stopped. This fork is 50 commits ahead and behind by none.

**A Streamlit application** (`frontend/demo_light/`, ~8,900 lines) — sign-in, a library, a member roster, settings pages:

- **Accounts on Supabase** — `member` / `admin` roles, monthly research quotas, suspension, and an audit log recording who changed what with before and after values. Row-level security keeps one account's reports out of another's reach.
- **Co-STORM as a first-class engine** — a round table where experts talk in the open and you can interrupt at any point.
- **Search sources chosen from a page** — test the key before saving; a saved key is never sent back to the browser. Upstream requires a code edit.
- **Per-run options** — depth (fast / standard / deep), which of the admin-offered sources to search, and which admin-offered model writes. Untouched, a run is exactly what the admin configured.
- **Self-contained HTML reports** — the article, its live citations, the evidence behind each one, and the interviews that produced it, in one file that opens with no server and no network.
- **Thai and English**, for both the interface and the generated article.
- **Provider-agnostic models** — Gemini, OpenRouter, Groq, OpenAI, or anything speaking the OpenAI API.

**Fixes to the upstream library** (12 files, +169/−123 excluding formatting) — several are bugs that make upstream unusable on a non-OpenAI deployment. See [below](#changes-to-the-upstream-library).

**42 tests**, covering article storage, account isolation, member management, and the database's own permission rules. Upstream has none for this surface.

---

## Quick start

Requires Python 3.11–3.14. From the project root:

macOS and Linux:

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install -r requirements.txt -r frontend/demo_light/requirements.txt watchdog
cp frontend/demo_light/.streamlit/secrets.toml.example \
   frontend/demo_light/.streamlit/secrets.toml
```

Windows (PowerShell):

```powershell
uv venv --python 3.14
.venv\Scripts\pip install -e .
.venv\Scripts\pip install -r requirements.txt -r frontend\demo_light\requirements.txt watchdog
Copy-Item frontend\demo_light\.streamlit\secrets.toml.example frontend\demo_light\.streamlit\secrets.toml
```

Fill in the settings file, then run — macOS and Linux:

```bash
cd frontend/demo_light
../../.venv/bin/streamlit run storm.py --server.runOnSave true
```

Windows (PowerShell), from the project root:

```powershell
.venv\Scripts\streamlit run frontend\demo_light\storm.py --server.runOnSave true
```

`-e .` is not optional — the app runs from inside `frontend/demo_light`, where Python cannot otherwise see `knowledge_storm`.

**`--server.runOnSave` is not cosmetic.** Without it Streamlit reloads only the main script, not *imported modules* like `demo_util.py` — so an edit appears to do nothing until you restart. `watchdog` must be installed or file watching does not work at all. The cost of having it on: saving a file while Co-STORM is warming up restarts the script and **destroys the run in progress**, which can be fifteen minutes of work.

Full walkthrough, including Windows commands and the Supabase setup: [frontend/demo_light/README.md](frontend/demo_light/README.md) (Thai).

---

## Configuration

[`secrets.toml.example`](frontend/demo_light/.streamlit/secrets.toml.example) is the reference for the settings it carries — providers, model names, Supabase keys, dev flags — each documented in place. This section covers only what that file does not, plus the traps worth knowing before you hit them.

Settings are read by `setting()` in `frontend/demo_light/auth.py`: **`secrets.toml` first, environment second.**

> A value present in `secrets.toml` cannot be overridden by an environment variable. Anything you vary per launch — `STORM_DEV_USER` especially — belongs in the environment only, or you cannot turn it off.

### Gemini's `-latest` aliases move without warning

The shipped defaults are `gemini-flash-lite-latest` and `gemini-flash-latest`, because Google returns 404 for pinned 2.x ids such as `gemini-2.5-flash` on recently created keys, even though `list_models()` still lists them.

But as of 2026-09-20 `gemini-flash-latest` resolved to `gemini-3.7-flash`, which returned frequent 503s and took 30–57 seconds on a one-word prompt where other models answered in 1–8. Pin the strong role off the alias:

```toml
LLM_STRONG_MODEL = "gemini-3.6-flash"
```

Measure response times before unpinning. A newer model is not automatically a faster one.

### Embeddings — Co-STORM only

Co-STORM files every snippet it collects into a mind map by **similarity**, not by asking a model where it belongs. That needs an embedding service, separate from chat completions.

It defaults to your chat provider, because for Gemini and OpenAI the same key buys both. But **OpenRouter and Groq have no embedding endpoint at all**, so those deployments must name a service of their own:

```toml
ENCODER_PROVIDER = "gemini"     # gemini, openai, or azure
```

The key comes from that provider's usual variable. If it is missing, the app says so before the discussion starts rather than failing partway through. STORM does not need this; Co-STORM cannot run without it.

### Search sources

The default is DuckDuckGo via `ddgs`, which needs no key. Admins change the source from the **Search sources** page — no code edit, no restart.

| Source | Key |
| --- | --- |
| DuckDuckGo, arXiv | none |
| Tavily | `TAVILY_API_KEY` |
| Serper (Google) | `SERPER_API_KEY` |
| Brave Search | `BRAVE_API_KEY` |
| You.com | `YDC_API_KEY` |
| SearXNG | `SEARXNG_URL` — an instance address, see [deploy/searxng](deploy/searxng/README.md) |

STORM takes one retriever, so the admin's page picks one — but a run can tick several from the list the admin has put on offer, and a `MultiRM` fans each query out to all of them and merges the results by URL. `SearXNG — academic` is the same instance restricted to its scholarly engines via `engines=`, not a second deployment. DuckDuckGo rate-limits aggressively; the app backs off and skips a query that keeps failing rather than ending the run. If search quality matters, a Tavily or Serper key is the cheapest improvement available.

### Sessions

Sign-in is restored from a cookie holding only a Supabase refresh token — no password — with `SameSite=Strict`, and `Secure` over HTTPS.

| Setting | Default | Meaning |
| --- | --- | --- |
| `SESSION_IDLE_MINUTES` | 30 | Idle time before sign-out |
| `SESSION_MAX_HOURS` | 12 | Absolute lifetime, even if active |

### Database setup

`SUPABASE_URL` and `SUPABASE_ANON_KEY` alone are not enough — the schema has to be applied:

1. Paste all of [docs/supabase-schema.sql](docs/supabase-schema.sql) into Supabase's **SQL Editor** and run it. This creates the profile, run-history and member-audit tables with their row-level security policies. Re-running it on an existing project is safe and preserves data.
2. Sign up through the app, then promote yourself:

   ```sql
   update public.profiles set role = 'admin' where email = 'you@example.com';
   ```

Quota is separate from role — `monthly_run_limit` on the profile, adjustable per account. Failed runs still count, because they may already have spent API calls.

---

## Running Co-STORM

**A discussion is 70–100 model calls.** Roughly 21 for expert interviews, 2 for the outline, 21–40 to file snippets into the mind map, then one call per mind-map node twice over — once to draft the report, once to turn it into the opening conversation. The last two scale with the map, which is why warm start can take fifteen minutes.

To trim it, pass `warmstart_max_num_experts` (default 3), `max_search_queries_per_turn` (default 3) or `max_search_thread` (default 5) to `RunnerArgument(...)` in `frontend/demo_light/costorm.py`.

A discussion lives in Streamlit session state and **does not survive a browser refresh**. `CoStormRunner.to_dict()` exists upstream, but `from_dict()` carries a FIXME — it ignores the saved `lm_config` and calls `lm_config.init(lm_type=os.getenv("OPENAI_API_TYPE"))`, which fails on Gemini. Persisting a discussion means writing the way back by hand.

---

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

`tests/test_member_database.py` checks the database's own rules — that an admin cannot demote or suspend themselves, that members cannot touch the audit log — by standing up a **temporary PostgreSQL cluster of its own** with `initdb`. It never touches Supabase, so running PostgreSQL in Docker does not help; install PostgreSQL or set `STORM_POSTGRES_BIN`, or these tests skip.

The cluster listens on 127.0.0.1 on a free port, with scram auth and a password generated per run, rather than on a Unix socket — Windows has none, and one code path keeps both platforms running the same test.

> **One test still does not run on Windows.** `test_article_store.py` has a symlink-escape check that needs symlink privileges and errors with `WinError 1314` unless Developer Mode is on. Expect 41 passing and 1 error.

---

## Changes to the upstream library

All local to the vendored `knowledge_storm` package. Upstream does not have them.

**`lm.py` — `GoogleModel` rewritten.** Moved off the deprecated `google-generativeai` SDK to `google-genai`, and re-based onto this package's own `LM` class instead of `dspy.dsp.modules.lm.LM`. It now accepts `GEMINI_API_KEY` as well as `GOOGLE_API_KEY`.

**`encoder.py` — Gemini added.** The encoder knew only OpenAI and Azure, so a Gemini deployment could not build a Co-STORM mind map at all.

**`logging_wrapper.py` — stop swallowing exceptions.** `log_pipeline_stage` caught every exception, printed it, and never re-raised. `generate_report` returns from inside such a block: when the exception was eaten, the return never ran and the caller got `None` with the cause reported nowhere.

**`dataclass.py` — `[-1]` markers reaching readers.** `replace("[-1]", "")` was called twice with both results discarded, inside a loop that does not run for a turn citing nothing. The marker for "no source found" survived every time.

**`rm.py` — five fixes.**

- `TavilySearchRM` named `result` in its own `except` clause, where it is unbound if the *first* result is the one that failed — turning a skippable result into an `UnboundLocalError` that killed the entire search.
- `TavilySearchRM` built an `args` dict and never passed it, so `k` and `include_raw_content` had never once been honoured.
- `TavilySearchRM` read `raw_body_content` where Tavily sends `raw_content`.
- `SearXNG` ignored `k` and collected the whole page — twenty or thirty results per query, all of which STORM went on to read. It also had no timeout, so a hung instance held the run open indefinitely; needed the `/search` path spelled out or `.json()` failed on the HTML front page; and reported a 403 — JSON output is off by default, and public instances almost never enable it — as a generic error indistinguishable from "no results". Now honours `k`, times out at 30s, accepts the instance root, and raises a `SearXNGConfigError` naming the cause for any 4xx.
- `DuckDuckGoSearchRM` used `dsp`'s shared `giveup_hdlr`, which reads `err.message` — an attribute only Mistral's SDK exceptions carry. On a DuckDuckGo rate limit it raised `AttributeError` from inside backoff, and *that* is what surfaced, killing the run and hiding the real cause.

**`requirements.txt` — two package changes.** `duckduckgo_search` → `ddgs`: the old package still imports and still answers HTTP 200, but returns no results, so the system looks like it is working while gathering nothing. And a floor of `sentence-transformers>=3`, because unpinned it resolves to 2.2.2, which calls `cached_download` — removed from `huggingface_hub` in 0.26 — and the resulting `ImportError` stops the app from starting at all. That one bites any fresh install on any OS.

The rest of the diff against upstream is Black formatting and line-ending normalization, which accounts for most of the raw line count.

---

## Documentation

| Document | Contents |
| --- | --- |
| This file | Overview, upstream differences, configuration not covered elsewhere |
| [`secrets.toml.example`](frontend/demo_light/.streamlit/secrets.toml.example) | Every setting it carries, documented in place |
| [frontend/demo_light/README.md](frontend/demo_light/README.md) | Full usage guide (Thai) — install, member management, Co-STORM, reports |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptom-to-fix guide (Thai) |
| [docs/supabase-schema.sql](docs/supabase-schema.sql) | Schema and row-level security policies |
| [deploy/supabase](deploy/supabase/README.md) | Self-hosted Supabase in four containers |
| [deploy/searxng](deploy/searxng/README.md) | Self-hosted metasearch, and why there is no academic fork |
| [deploy/research-ui](deploy/research-ui/README.md) | deep-research-web-ui as a framed sibling application |

---

## License and citation

MIT, as upstream. See [LICENSE](LICENSE).

This fork builds on the work of the Stanford OVAL group. Please cite their papers if you use this code or part of it:

```bibtex
@inproceedings{jiang-etal-2024-unknown,
    title = "Into the Unknown Unknowns: Engaged Human Learning through Participation in Language Model Agent Conversations",
    author = "Jiang, Yucheng  and
      Shao, Yijia  and
      Ma, Dekun  and
      Semnani, Sina  and
      Lam, Monica",
    editor = "Al-Onaizan, Yaser  and
      Bansal, Mohit  and
      Chen, Yun-Nung",
    booktitle = "Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing",
    month = nov,
    year = "2024",
    address = "Miami, Florida, USA",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2024.emnlp-main.554/",
    doi = "10.18653/v1/2024.emnlp-main.554",
    pages = "9917--9955",
}

@inproceedings{shao-etal-2024-assisting,
    title = "Assisting in Writing {W}ikipedia-like Articles From Scratch with Large Language Models",
    author = "Shao, Yijia  and
      Jiang, Yucheng  and
      Kanell, Theodore  and
      Xu, Peter  and
      Khattab, Omar  and
      Lam, Monica",
    editor = "Duh, Kevin  and
      Gomez, Helena  and
      Bethard, Steven",
    booktitle = "Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)",
    month = jun,
    year = "2024",
    address = "Mexico City, Mexico",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2024.naacl-long.347/",
    doi = "10.18653/v1/2024.naacl-long.347",
    pages = "6252--6278",
}
```
