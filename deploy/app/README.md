# The app as a container

Everything else this deployment runs was already a container — Supabase,
SearXNG, the Deep Research UI. The app itself was a process on somebody's
host: no image to pin, no healthcheck, no restart policy, and a 1.3GB
virtualenv to rebuild on a new machine. This is the missing piece.

```
cd ..
cp .env.example .env     # then fill it in
docker compose up -d --build
```

It listens on `127.0.0.1:8501`. It is one service of the stack in
`deploy/docker-compose.yml`, on one network with the rest.

## No secrets.toml, on purpose

`auth.setting` reads `secrets.toml` first and the environment second, and a
value in `secrets.toml` **cannot** be overridden by an environment variable.
That would make a mounted `secrets.toml` a trap — the container would ignore
half of `.env` — so the image carries none and the file is not mounted.
Everything comes from `.env`.

## Two things it writes, and where they go

| what | path in the container | why not the source tree |
| --- | --- | --- |
| the admin pages' saved settings | `/data/state` (`app-state`) | `model_settings.json` and `search_sources.json` live in `.streamlit` beside `config.toml`; a volume mounted there to keep them would take the theme with it |
| members' reports | `/app/frontend/demo_light/DEMO_WORKING_DIR` (`app-reports`) | `get_demo_dir()` puts them inside the tree, so the volume goes exactly there |

`STORM_STATE_DIR` is what moves the first one. Unset — a host run — it is
`.streamlit` beside the app, exactly where it has always been.

Note that the container's settings start empty. It does not inherit what the
host run saved: these are two deployments, and the Models page has to be
filled in once on each.

## Reaching things that are not in a container

Ollama runs on the host. `host.docker.internal` resolves on Docker Desktop
and, thanks to the `extra_hosts` line, on a Linux host too:

```
OLLAMA_API_BASE=http://host.docker.internal:11434
```

Supabase and SearXNG are containers, so they are reached by service name —
`http://gateway:8000` and `http://searxng:8080`. `localhost` is what a host
run uses and cannot work here: inside a container localhost is the container.

## The image is 3.2GB, and most of it is one import

```
torch         776MB
transformers  120MB
scipy         110MB
sympy          77MB
```

`knowledge_storm/storm_wiki/modules/storm_dataclass.py` ranks snippets with
`SentenceTransformer("paraphrase-MiniLM-L6-v2")` during article generation.
That is a real runtime dependency, not a stray import, so torch stays.

Two things keep it from being worse:

- **Torch comes from the CPU index.** Left to itself pip takes the CUDA
  build — roughly 2.5GB of nvidia libraries for a machine with no GPU.
- **The model ships inside the image** and `HF_HUB_OFFLINE=1` is set.
  Baking it in is not enough on its own: the hub client still calls
  huggingface.co to check the cached copy, which cost 11.5s with a network
  and **hung indefinitely without one**, and logged a permission error
  trying to write a marker into a cache this user cannot write to. Offline
  it reads the cache and nothing else — 6.3s with no network at all.

## Verified

Against this machine's stacks, on the image built from this Dockerfile:

- container reports healthy on Streamlit's `/_stcore/health`
- `http://gateway:8000/auth/v1/health` → `200 GoTrue v2.177.0`
- `http://searxng:8080/` → `200`
- sign-in page renders in Thai, in both light and dark
- settings write to `/data/state/model_settings.json` and read back
- `STORM_DEV_USER` unset, so sign-in is required

Those checks were run again after the four compose projects became one,
against the merged stack, and the row counts in every table matched what
they were before it.
