# STORM — minimal user interface

A Streamlit app for `STORMWikiRunner`: give it a topic, it researches the topic
from several perspectives, gathers sources from the web, and writes a cited,
Wikipedia-style article.

This is a fork of [stanford-oval/storm](https://github.com/stanford-oval/storm).
Upstream stopped receiving commits in September 2025 and several of its pinned
dependencies have since gone stale, so the setup below differs from the
instructions in the upstream README. See **Differences from upstream** at the
end for what changed and why.

Features:

1. Create an article from a topic, in **English or Thai**.
2. Watch STORM's research happen — perspectives, questions, pages visited.
3. Read the article beside its table of contents and references.
4. Browse and search previously created articles.
5. Light and dark themes, following your system or the Streamlit settings menu.

## Setup

Everything below is run from the repository root unless stated otherwise.

### 1. Create a virtual environment

```bash
python3.14 -m venv .venv
```

Python 3.11–3.14 all work. The upstream README suggests conda; a plain venv is
enough, since nothing here needs conda's non-Python packages.

### 2. Install the library and the interface

```bash
.venv/bin/pip install -e .
.venv/bin/pip install -r requirements.txt -r frontend/demo_light/requirements.txt
```

`-e .` is what puts `knowledge_storm` on the path. Skipping it is the usual
cause of `ModuleNotFoundError: No module named 'knowledge_storm'`.

### 3. Add your API key

Create `frontend/demo_light/.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY = "your-key-here"
```

Get a key from [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key).
The quotes are required — TOML rejects a bare unquoted value, and Streamlit
reports it as a missing key rather than a syntax error.

The file is gitignored and must stay that way.

### 4. Run

```bash
cd frontend/demo_light
../../.venv/bin/streamlit run storm.py
```

Then open http://localhost:8501.

Call the venv's `streamlit` by path as shown, or activate the venv first
(`source .venv/bin/activate`) — a bare `streamlit run` uses whatever is on your
system PATH, which is usually nothing at all.

Articles are written to `frontend/demo_light/DEMO_WORKING_DIR/`, which is
gitignored.

## Models and quota

The app uses Gemini through litellm, configured in `set_storm_runner()` in
[demo_util.py](demo_util.py):

| Stage | Model |
| --- | --- |
| Asking questions, simulating the conversation | `gemini/gemini-flash-lite-latest` |
| Outline, article, polish | `gemini/gemini-flash-latest` |

Use the `-latest` aliases rather than a pinned id such as
`gemini-2.5-flash`. Google returns 404 — *"no longer available to new users"* —
for pinned 2.x ids on keys created recently, even though `list_models()` still
lists them.

The engine ships configured for a **paid key**:

```python
max_conv_turn=3, max_perspective=3, num_retries=6   # max_thread_num defaults to 10
```

**On the free tier** Gemini allows 15 requests per minute per model, and STORM
bursts straight past that when it researches perspectives in parallel. Lower
them in `set_storm_runner()`:

```python
max_conv_turn=2, max_perspective=2, max_thread_num=1
```

Keep `num_retries` either way; paid keys still see the occasional 429. In our
testing the parallel settings produced twice the research in half the
wall-clock time, so raise them again as soon as the quota allows.

If every model suddenly returns `RateLimitError`, read the message body before
touching the code — *"Your prepayment credits are depleted"* is a billing
state, not a bug.

## Search

Sources come from DuckDuckGo via the `ddgs` package, so no second API key is
needed. DuckDuckGo rate-limits aggressively; the retriever retries with backoff
and skips a query it cannot complete rather than failing the whole run.

For source quality closer to academic work, `knowledge_storm/rm.py` also ships
`StanfordOvalArxivRM`, `SerperRM`, `BraveRM` and `TavilySearchRM`. Swapping the
retriever is a one-line change in `set_storm_runner()`; all but arXiv need
their own API key.

## Languages

Two separate choices:

- **Interface language** — the sidebar picker. Adds strings in
  [ui_language.py](ui_language.py).
- **Article language** — the dropdown on the create page. Implemented in
  [article_language.py](article_language.py), which appends a language
  directive to the docstrings of the DSPy signatures whose output a reader
  sees. Search queries are deliberately left alone: query wording decides which
  sources are found, and pinning it to one language shrinks the evidence the
  article is built from.

Adding a language means adding one entry to `LANGUAGES` in each file.

## Customization

`STORMWikiRunner` is built in `set_storm_runner()` in [demo_util.py](demo_util.py).
Change `STORMWikiRunnerArguments`, the per-stage models in `STORMWikiLMConfigs`,
or the retriever there. The upstream
[customization guide](https://github.com/stanford-oval/storm?tab=readme-ov-file#customize-storm)
still applies.

## Differences from upstream

Fixes, all of which upstream still has:

- `duckduckgo_search` was renamed to `ddgs`. The old package imports fine and
  returns HTTP 200 but yields zero results, so STORM appeared to work while
  researching nothing.
- STORM calls its progress callbacks from worker threads. On Streamlit 1.5x and
  later, writing to a container from a thread with no script context raises
  instead of warning, which ended every run.
- Table-of-contents links resolved nowhere. Headings with no Latin characters
  collapsed to an empty anchor, and Streamlit's hash-based heading ids never
  matched a text slug — broken for English too, not only Thai.
- `streamlit==1.31.1` cannot be installed alongside NumPy 2.

Additions:

- Rebuilt interface, dark mode, Thai article and interface support.
- Article length is reported in characters for scripts that do not put spaces
  between words, where splitting on whitespace counts a sentence as one word.

Tested against Streamlit 1.60 on Python 3.14.
