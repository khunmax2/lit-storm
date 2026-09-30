# stack

The web app that replaces Streamlit, as one Docker Compose project on one
machine: `db` (Postgres), `api` (FastAPI, runs migrations on start),
`worker` (runs Runs, one process each), `web` (nginx serving the app and
forwarding `/api`), and `searxng`. Only `web` publishes a port, on
`127.0.0.1:${LITSTORM_PORT:-8090}`.

## First time

```bash
sh stack/init-secrets.sh
docker compose -f stack/compose.yml up -d --build
```

Open http://localhost:8090 and enter the code in `stack/secrets/bootstrap_code`
to create the first Administrator. Then, under Settings:

1. **Models** — add an API key (for example OpenRouter), then a model. For
   `google/gemini-3.5-flash-lite` set reasoning to `effort:minimal` and the
   reply budget to 1500 / 4000: it cannot turn thinking off.
2. **Search providers** — the stack's SearXNG is already there as the default.
3. **Users** — create accounts and send each person their one-time link.

## Secrets

`stack/secrets/` is ignored by git.

- `secret_key` encrypts stored API keys. **Back it up.** Without it every
  stored key has to be entered again.
- `bootstrap_code` is used once, for the first Administrator.

## Data

Two named volumes: `db-data` (Postgres) and `run-data` (each Run's files and
its `report.json`). `docker compose down` keeps them; `down -v` deletes them.

## On host 203

`docs/deploy/HOST-203.md` is the runbook. The files it uses:

- `build-images.sh` — the two images, from this checkout and the Engine
  forks pinned in `engines.lock.json` (run by `.github/workflows/images.yml`)
- `compose.host.yml` + `host.env` (from `host.env.example`) — the stack
  pulling those images by digest, on one loopback port
- `host/apply-nginx.sh` — `/litstorm` in the host's nginx: preview, install,
  uninstall; `host/rehearse-nginx.sh` rehearses it off the host
- `backup.sh` — back up, verify and restore a stack

## Walkthrough

`server/tests/e2e_walkthrough.py` drives the whole path through a real
browser against a fresh stack, including one real Run (it costs money).
