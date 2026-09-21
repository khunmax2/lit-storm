# The stack

Ten services, one compose project, one network, one `.env`.

```
cp .env.example .env     # then fill it in
docker compose up -d --build
```

**One port is published: the edge.** Everything else is reached through it
or by service name from inside.

| service | what it is | reachable at |
| --- | --- | --- |
| `edge` | nginx, the stack's only door | `127.0.0.1:${LIT_STORM_HTTP_PORT}` |

`/` redirects to the app. `LIT_STORM_BASE_PATH` moves it, and is read by
both the proxy and Streamlit so the two cannot disagree.

| `app` | the Streamlit app | `/lit-storm/` |
| `research-ui` | Deep Research, framed in a tab | `/research/` |
| `agents-research` | Agent Research, framed in a tab | `/agents/` |
| `searxng` | metasearch for all of them | inside only |
| `gateway` | nginx, presenting the two Supabase paths | inside only |
| `auth` | GoTrue | inside only |
| `rest` | PostgREST | inside only |
| `db` | Postgres | inside only |
| `schema` | applies the app's schema, then exits 0 | one shot |

Each has a README of its own in the directory beside this file, for the
things specific to it.

## Why only one port

**The host's ports are one namespace shared with every other stack on it.**
This stack used to claim six of them, and starting it beside another project
that publishes 8080 failed with

```
Bind for 127.0.0.1:8080 failed: port is already allocated
```

Moving the port would have been the small fix. Publishing one port is the
real one — and it makes the laptop the same shape as a host, so `/research/`
working here is evidence that it will work deployed rather than something to
find out later.

Only three services are reached by a browser at all:

| service | who reaches it | needs publishing? |
| --- | --- | --- |
| `app` | the person's browser | yes — behind the proxy |
| `research-ui` | the browser, through the app's iframe | yes — behind the proxy |
| `agents-research` | the browser, through the app's iframe | yes — behind the proxy |
| `searxng` | the other three, by service name | **no** |
| `gateway`, `auth`, `rest` | the app, server-side — `supabase-py` runs in the app, not in the browser | **no** |
| `db` | `rest`, `auth`, and a human doing maintenance | **no** |

That is what `edge` does. Nothing in the application changed to make it
possible — the app already reached Supabase at `http://gateway:8000` and
SearXNG at `http://searxng:8080`, neither through a published port. A
deployment swaps this one port for 443 and a certificate.

Two stacks can sit on one host without knowing about each other, because
neither asks the host for anything except through its own proxy.

Getting there needed three things that are easy to get wrong, all recorded
in the files that fix them:

- **Streamlit needs the WebSocket upgrade.** Without `Upgrade`/`Connection`
  headers the page loads and then sits there, because the socket carrying
  every rerun never opens.
- **Redirects must be relative.** nginx builds an absolute `Location`
  from its own listen port by default — 8080 inside the container, not
  the port anyone typed — so `/` sent the browser somewhere nothing
  serves. `absolute_redirect off`.
- **`/research/` must not have its prefix stripped.** Nuxt is told it lives
  there and builds its pages and asset URLs under it; handed `/` it answers
  500.
- **`/agents/` must.** Our own page fetches `api/runs` relative, so it works
  at whatever path it is mounted.

## Running the app outside the stack

`streamlit run` on a laptop against these containers reaches neither the
service names nor the edge's paths. Point it at the edge — and note the
app itself is then at `/`, because `STREAMLIT_SERVER_BASE_URL_PATH` is
set by the compose file and not by your shell:

```
RESEARCH_UI_URL=http://localhost:8080/research/
AGENTS_RESEARCH_URL=http://localhost:8080/agents/
```

## It used to be four projects

`deploy/supabase`, `deploy/searxng`, `deploy/research-ui` and `deploy/app`,
each with its own compose file, network and `.env`. That cost two things,
and both arrived as bugs rather than as inconvenience:

- **Cross-stack networking needed `external` network declarations.** The
  research UI could not reach SearXNG at all until its compose file joined
  `lit-storm-searxng_default` by name — `host.docker.internal` does not
  resolve from a Linux container without a host-gateway entry, and points at
  the host rather than at the service even when it does.
- **Three `.env` files meant three copies of the same key.** A key changed on
  the Models page sat stale in the research UI's copy, and the failure
  surfaced as a quota error in a tab that looks like part of the same
  application.

Both are gone. Services reach each other by name on `lit-storm_default`, and
there is one file to change a key in.

## Volumes are named explicitly, and that is deliberate

```yaml
volumes:
  db-data:
    name: lit-storm-supabase_db-data
```

Compose normally prefixes a volume with the project name, so merging four
projects into one would have renamed all four volumes — and pointed Postgres
at an empty one. That looks exactly like losing the database. Naming them
explicitly keeps the volumes that were already filled, and means renaming the
project later cannot do it either.

The merge was done with a `pg_dumpall` taken first and the row counts in
every table compared after: `auth.users` 2, `profiles` 2, `runs` 11,
`member_audit_log` 5, before and after.

## Ollama is not in here

It runs on the host. `app` gets `host.docker.internal` through an
`extra_hosts` entry, which Docker Desktop would have provided anyway and a
Linux host would not:

```
OLLAMA_API_BASE=http://host.docker.internal:11434
```

## Starting over

`docker compose down` stops everything and keeps the data.
`docker compose down -v` **deletes the database**. There is no backup job
here; `deploy/supabase/README.md` says what to do about that.
