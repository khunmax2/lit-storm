<p align="center">
  <img src="assets/logo.svg" style="width: 25%; height: auto;">
</p>

# lit-storm

A self-hosted research assistant built on [stanford-oval/storm](https://github.com/stanford-oval/storm). Give it a topic; it researches from several perspectives, gathers sources, and writes a cited, encyclopedia-style report you can check claim by claim.

Upstream is a research codebase you drive from Python. This fork is a web app a small team signs in to: accounts and monthly quotas, a queue that keeps working when you close the tab, a settings page instead of code edits, and reports whose every citation opens the evidence behind it.

<p align="center">
| <a href="https://arxiv.org/abs/2402.14207"><b>STORM paper</b></a> | <a href="https://www.arxiv.org/abs/2408.15232"><b>Co-STORM paper</b></a> | <a href="https://storm-project.stanford.edu/"><b>Upstream project site</b></a> |
</p>

---

## What it does

- **Research that runs on its own.** A topic becomes a Run on a background Worker, one process per Run. Close the page; come back to the report. Runs can be cancelled, retried, and filed in Projects — or left unfiled, as in ChatGPT or Claude.
- **Reports you can check.** Citations are renumbered in reading order; clicking one opens the source and the excerpt the engine actually used. Export as HTML (opens offline), Markdown or PDF, with or without the evidence.
- **Thai and English**, for the interface and for the report.
- **Accounts, quota and a fair queue.** Administrators create accounts and send one-time links. Each person has a monthly quota; the queue takes turns between people and refunds quota when a Run fails for reasons that are not theirs.
- **Settings on a page.** Models from OpenRouter, Gemini, OpenAI, Groq or any OpenAI-compatible server; search through SearXNG (bundled), Tavily or arXiv. Keys are stored encrypted and never shown again. Every model and search service can be tested before it is saved.
- **Usage and cost.** Tokens, searches and an estimated cost for every Run, per person and per month — without showing anyone's topics.
- **A 30-day Trash.**

| Engine | Status |
| --- | --- |
| STORM — a Wikipedia-style report from simulated expert interviews | Available |
| Agent Research, Deep Research, Co-STORM (a live discussion) | Second release — see the [design](docs/web-app-design.md) |

---

## Quick start

Requires Docker with Compose v2.

```bash
sh stack/init-secrets.sh
docker compose -f stack/compose.yml up -d --build
```

Open http://localhost:8090 and enter the code from `stack/secrets/bootstrap_code` to create the first Administrator. Then under **Settings**: add a model (with its provider's API key), check that the bundled SearXNG answers under **Search providers**, and create accounts under **Users**. Details, backups and data: [stack/README.md](stack/README.md).

**Back up `stack/secrets/secret_key`.** It encrypts every stored API key; without it they must all be entered again.

---

## Layout

| Path | What it is |
| --- | --- |
| `server/` | FastAPI API and the Worker (Python 3.12, `uv`). Migrations with Alembic. |
| `web/` | The web app: React, TypeScript, Vite, Tailwind and shadcn/ui. The API client is generated from the server's OpenAPI. |
| `stack/` | Docker Compose: Postgres, API, Worker, nginx serving the web app, SearXNG. |
| `knowledge_storm/` | The vendored STORM library, with the fixes listed below. |
| `docs/` | Glossary, design, plan, decisions (ADRs) and acceptance records. |

---

## Development

```bash
# Postgres for development (any Postgres 17 will do)
docker run -d --name litstorm-pg-dev -p 55432:5432 \
  -e POSTGRES_USER=litstorm -e POSTGRES_PASSWORD=litstorm -e POSTGRES_DB=litstorm postgres:17-alpine

cd server
uv sync --extra pdf        # --extra pdf keeps Playwright, which renders PDF exports
export LITSTORM_DATABASE_URL=postgresql+psycopg://litstorm:litstorm@127.0.0.1:55432/litstorm
uv run alembic upgrade head
uv run uvicorn litstorm.api:app --port 8000          # the API
uv run python -m litstorm.worker.main                # the Worker, in another shell

cd ../web
npm install
npm run dev                                          # http://localhost:5173, proxies /api to :8000
```

The server also reads `LITSTORM_SECRET_KEY_FILE`, `LITSTORM_BOOTSTRAP_CODE_FILE`, `LITSTORM_DATA_DIR` and `LITSTORM_PUBLIC_URL` (see `server/src/litstorm/settings.py`). After changing the API, regenerate the web client: write the OpenAPI document to `web/src/api/openapi.json` and run `npm run api`.

### Tests

```bash
cd server
uv run pytest            # everything; tests marked db start a throwaway Postgres (needs Docker)
uv run pytest -m "not db"
```

Browser scripts in `server/tests/` drive the real UI with Playwright against a running stack: `e2e_walkthrough.py` (setup to report, one real Run), `e2e_step4.py`, `e2e_queue_rules.py`, `e2e_screens.py` (screenshots of every page), and `acceptance.py` (the first-release acceptance criteria — it wipes the stack it runs against). Their selectors live in `server/tests/ui.py`. Scripts that make real Runs read the OpenRouter key from `stack/.env` (`OPENROUTER_API_KEY=…`, ignored by git).

---

## Choosing models

**A thinking model can answer nothing at all.** A model that writes out its thinking spends it from the same token budget as its answer. On a small budget that can be all of it: `deepseek/deepseek-v4.1-flash` and `qwen/qwen3.7-flash`, asked a short question with a Thai topic, used all 500 tokens thinking and returned nothing — a call that succeeded, was billed, and said nothing. Thai makes these models think longer. Set the model's reasoning to `off` or a low effort in Settings, or pick a model that does not think; the test button reports an empty answer instead of a pass.

| model | thinking | on 500 tokens, Thai prompt | per call |
| --- | --- | --- | --- |
| `qwen/qwen3.7-flash` | on (default) | **nothing, 3/3** | $0.000067 |
| `qwen/qwen3.7-flash` | off | good Thai, 1.1s | $0.000005 |
| `meta-llama/llama-4-scout` | none to switch | good Thai, 1.0s | $0.000014 |
| `deepseek/deepseek-v4.1-flash` | on (default) | **nothing, 3/3** | $0.000622 |

**Aliases move.** Gemini's `-latest` names resolve to whatever Google points them at; on 2026-09-20 `gemini-flash-latest` became a model that took 30–57 seconds on a one-word prompt. Pin a version, and measure before changing it.

---

## Changes to the upstream library

All local to the vendored `knowledge_storm` package. Upstream does not have them.

**`lm.py` — `GoogleModel` rewritten.** Moved off the deprecated `google-generativeai` SDK to `google-genai`, and re-based onto this package's own `LM` class instead of `dspy.dsp.modules.lm.LM`. It now accepts `GEMINI_API_KEY` as well as `GOOGLE_API_KEY`.

**`encoder.py` — Gemini added.** The encoder knew only OpenAI and Azure, so a Gemini deployment could not build a Co-STORM mind map at all.

**`logging_wrapper.py` — stop swallowing exceptions.** `log_pipeline_stage` caught every exception, printed it, and never re-raised. `generate_report` returns from inside such a block: when the exception was eaten, the return never ran and the caller got `None` with the cause reported nowhere.

**`dataclass.py` — `[-1]` markers reaching readers.** `replace("[-1]", "")` was called twice with both results discarded, inside a loop that does not run for a turn citing nothing. The marker for "no source found" survived every time.

**`rm.py` — six fixes.**

- `TavilySearchRM` named `result` in its own `except` clause, where it is unbound if the *first* result is the one that failed — turning a skippable result into an `UnboundLocalError` that killed the entire search.
- `TavilySearchRM` built an `args` dict and never passed it, so `k` and `include_raw_content` had never once been honoured.
- `TavilySearchRM` read `raw_body_content` where Tavily sends `raw_content`.
- `SearXNG` ignored `k` and collected the whole page — twenty or thirty results per query, all of which STORM went on to read. It also had no timeout, needed the `/search` path spelled out, and reported a 403 (JSON output is off by default) as a generic error. Now it honours `k`, times out at 30s, accepts the instance root, and raises `SearXNGConfigError` naming the cause when the address or setup is wrong.
- `SearXNG` skips blank queries, which STORM's question writer sometimes produces: SearXNG answers an empty query with 400, which used to end the whole run. A 400 for one query is now skipped like any failed search.
- `DuckDuckGoSearchRM` used `dsp`'s shared `giveup_hdlr`, which reads `err.message` — an attribute only Mistral's SDK exceptions carry. On a DuckDuckGo rate limit it raised `AttributeError` from inside backoff, hiding the real cause.

**`requirements.txt` — two package changes.** `duckduckgo_search` → `ddgs`: the old package still answers HTTP 200 but returns no results. And a floor of `sentence-transformers>=3`, because unpinned it resolves to 2.2.2, whose `cached_download` import no longer exists in `huggingface_hub`.

The rest of the diff against upstream is Black formatting and line-ending normalization.

---

## Documentation

| Document | Contents |
| --- | --- |
| [docs/CONTEXT.md](docs/CONTEXT.md) | Glossary: Project, Research Session, Run, Engine, Report, Source, Evidence… (Thai) |
| [docs/web-app-design.md](docs/web-app-design.md) | Every design decision, first and second release (Thai) |
| [docs/web-app-implementation-plan.md](docs/web-app-implementation-plan.md) | Build order and what each step delivered (Thai) |
| [docs/adr/](docs/adr/) | Decisions that are hard to reverse, with the options not taken |
| [docs/acceptance/](docs/acceptance/) | Acceptance runs and their evidence |
| [stack/README.md](stack/README.md) | Running the stack, secrets, data |
| [docs/archive/streamlit/](docs/archive/streamlit/) | The Streamlit app this replaced, for the record |

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
