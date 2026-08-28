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

### 3. Add your keys

```bash
cp frontend/demo_light/.streamlit/secrets.toml.example \
   frontend/demo_light/.streamlit/secrets.toml
```

Then fill it in:

```toml
GOOGLE_API_KEY    = "..."   # https://ai.google.dev/gemini-api/docs/api-key
SUPABASE_URL      = "..."   # Supabase -> Project Settings -> Data API
SUPABASE_ANON_KEY = "..."   # the anon public key, never service_role
```

The quotes are required — TOML rejects a bare unquoted value, and Streamlit
reports it as a missing key rather than a syntax error.

`secrets.toml` is gitignored and must stay that way; only the `.example` is
tracked. Every one of these is also read from the environment when it is
absent from the file, which is how they reach a container.

Leave the Supabase pair empty to run without accounts — the sign-in screen
will say what is missing instead of failing.

### 3b. Set up accounts

Accounts, roles and the per-person run quota live in Supabase.

1. Create a project at [supabase.com](https://supabase.com).
2. Paste [docs/supabase-schema.sql](../../docs/supabase-schema.sql) into the
   SQL editor and run it once. It creates `profiles` and `runs`, the
   row-level policies, and a trigger that gives every sign-up a profile.
3. While testing locally, turn off e-mail confirmation under
   Authentication → Providers → Email, or no one can sign in until they open
   a confirmation link.
4. Sign up through the app, then make yourself an admin:

   ```sql
   update public.profiles set role = 'admin' where email = 'you@example.com';
   ```

There are two roles. A `member` signs up and creates reports — that is what
the app is for. An `admin` does that and also sees everyone's runs and manages
the roster under **Members**.

Spending is not a role: every member can create reports, and what keeps one
shared API key from paying for all of it is `monthly_run_limit` on each
profile, which an admin changes per person. Failed runs count against it.

Sessions live in Streamlit's session state, so reloading the page signs you
out. Streamlit has no cookie API; this is a limitation of running auth inside
it rather than a missing feature here.

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

### Working on the interface without signing in every time

Streamlit keeps the session in memory, so saving a file restarts the script and
puts you back at the sign-in screen. While building a page that lives behind
that screen, run with the bypass on:

```bash
STORM_DEV_USER=1 ../../.venv/bin/streamlit run storm.py
```

A stand-in account is signed in — admin by default, so the roster is reachable;
`STORM_DEV_ROLE=member` to see the app as everyone else sees it. An
undismissable strip across the top says the build is not asking anyone to sign
in, and **Sign out** stands the bypass down so the real sign-in screen can be
looked at too (reload to get back in).

Three things fence it off, because an auth bypass that reaches a deployment is
the whole system gone:

- it is off unless the variable is set, and the variable belongs in the
  environment or in `secrets.toml`, neither of which is committed;
- it is refused unless the browser asked for the page over loopback, so it does
  nothing on the network URL, behind a proxy, or in a container people can
  reach;
- it never touches Supabase. The profile, the roster and the run ledger are all
  fabricated in memory, so a stray flag can neither read nor write real rows —
  which also means the roster you see is made up, and saving it saves nothing.

The stand-in account gets its own folder under `DEMO_WORKING_DIR/`, like any
other account, so the library starts empty. Copy an article folder into it if
you need cards on the page.

Runs are real: the bypass skips sign-in, not the API bill.

## Models and quota

Two models, named by the work they do rather than by their size:

| Stage | Model |
| --- | --- |
| Asking questions, simulating the conversation | the **fast** one |
| Outline, article, polish | the **strong** one |

Which provider serves them is a setting, not a code change. The wrapper
underneath is litellm, so a hundred providers are reachable; these are the
ones with a key name of their own:

```toml
LLM_PROVIDER = "gemini"        # or openrouter, groq, openai, openai-compatible
GOOGLE_API_KEY = "..."
```

Gemini ships defaults — `gemini/gemini-flash-lite-latest` and
`gemini/gemini-flash-latest`. Use those `-latest` aliases rather than a pinned
id such as `gemini-2.5-flash`: Google returns 404 — *"no longer available to
new users"* — for pinned 2.x ids on keys created recently, even though
`list_models()` still lists them.

Every other provider needs its models named, because an id guessed here would
fail in the middle of a run rather than at startup:

```toml
LLM_PROVIDER     = "openrouter"
OPENROUTER_API_KEY = "..."
LLM_FAST_MODEL   = "google/gemini-2.5-flash-lite"
LLM_STRONG_MODEL = "anthropic/claude-sonnet-4"
```

Model ids are written the way the provider writes them; the provider part is
added for you. That matters for OpenRouter, whose own ids contain a slash —
`anthropic/claude-sonnet-4` is an OpenRouter id, not an instruction to call
Anthropic directly.

Either role can sit on a different provider than the other, which is how you
put the questions somewhere cheap and fast and the writing somewhere strong:

```toml
LLM_FAST_PROVIDER   = "groq"
GROQ_API_KEY        = "..."
LLM_FAST_MODEL      = "llama-3.1-8b-instant"

LLM_STRONG_PROVIDER = "openrouter"
OPENROUTER_API_KEY  = "..."
LLM_STRONG_MODEL    = "anthropic/claude-sonnet-4"
```

Anything else that speaks the OpenAI API — z.ai, Together, a model served on
your own machine — goes through `openai-compatible` with its own base URL:

```toml
LLM_PROVIDER = "openai-compatible"
LLM_API_BASE = "https://api.z.ai/api/paas/v4"
LLM_API_KEY  = "..."
LLM_FAST_MODEL   = "glm-4-flash"
LLM_STRONG_MODEL = "glm-4-plus"
```

Settings that do not describe a model we can call are reported on the page
before the run starts, rather than as a traceback partway through it.

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
