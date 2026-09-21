# The stack

Nine services, one compose project, one network, one `.env`.

```
cp .env.example .env     # then fill it in
docker compose up -d --build
```

| service | what it is | reachable at |
| --- | --- | --- |
| `app` | the Streamlit app | `127.0.0.1:8501` |
| `research-ui` | Deep Research, framed in a tab | `127.0.0.1:3100` |
| `agents-research` | Agent Research, framed in a tab | `127.0.0.1:3200` |
| `searxng` | metasearch for all of them | `127.0.0.1:8080` |
| `gateway` | nginx, presenting the two Supabase paths | `127.0.0.1:8000` |
| `auth` | GoTrue | inside only |
| `rest` | PostgREST | inside only |
| `db` | Postgres | `127.0.0.1:5433` |
| `schema` | applies the app's schema, then exits 0 | one shot |

Each has a README of its own in the directory beside this file, for the
things specific to it. Everything binds to loopback; a deployment puts a
reverse proxy in front.

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
