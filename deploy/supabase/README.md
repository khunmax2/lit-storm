# Supabase, self-hosted

Everything the app needs from Supabase, in four containers, on this machine.

## Why four and not ten

The official self-hosted stack runs Kong, GoTrue, PostgREST, Realtime,
Storage, imgproxy, meta, Studio, an analytics pipeline and a log collector.
Grepping this app for what it actually calls finds two services:

| Service | Calls |
| --- | --- |
| GoTrue | `sign_up`, `sign_in_with_password`, `sign_out`, `refresh_session`, `get_user` |
| PostgREST | `table()` ×10, `rpc()` ×2 |

No Storage, no Realtime, no Edge Functions, no Studio. So: Postgres, GoTrue,
PostgREST, and nginx in front presenting the two paths `supabase-py` builds
from `SUPABASE_URL`.

**Nothing in the application changes.** `SUPABASE_URL` points here and the
keys come from `.env`; the client cannot tell the difference.

## Running it

```bash
docker compose --env-file .env up -d
```

`.env` is gitignored and holds the database password, the JWT secret and the
two API keys signed with it. Regenerate it with the snippet at the bottom of
this file if it is ever lost — but note that regenerating the JWT secret
invalidates every session and both keys.

The stack listens on `127.0.0.1` only:

| Port | Service |
| --- | --- |
| 8000 | gateway — this is `SUPABASE_URL` |
| 5433 | Postgres, for restores and inspection |

To start over, deleting all data: `docker compose down -v`.

## What happens on first start

1. `init/00-roles.sql` runs on the empty data directory, creating the roles
   GoTrue and PostgREST sign in as, and the baseline table grants hosted
   Supabase applies for you.
2. GoTrue migrates the `auth` schema.
3. The one-shot `schema` service applies `docs/supabase-schema.sql` and tells
   PostgREST to reload.

Step 3 cannot move into step 1: the app's schema references `auth.users` and
`auth.uid()`, which do not exist until GoTrue has run.

## Three things that will bite

**`postgres` has to exist as a role.** The `supabase/postgres` image runs as
`supabase_admin`, but GoTrue's own migrations grant `select` on every auth
table to `postgres` by name and abort the whole startup if it is missing.

**The app's schema assumes a baseline grant.** It opens with
`revoke ... from anon, authenticated` and grants back named columns. With
nothing to revoke, every query returns `permission denied for table profiles`
— which reads like a policy problem and is not one. `init/00-roles.sql` sets
the default privileges that hosted Supabase gives you.

**PostgREST caches the schema at startup**, which happens before the schema is
applied. Without `notify pgrst, 'reload schema'`, every `rpc()` returns
"Could not find the function … in the schema cache" while the tables work
fine — tables are queried, functions are only read from the cache.

## Passwords do not migrate

Supabase's admin API does not return `encrypted_password`, and the hosted
project's database password is not among the app's settings. Accounts brought
over keep their id, email and confirmation state, so every profile, run and
audit row still points at the right person — but each account needs its
password set once on this side. From the project root:

```
.venv/Scripts/python deploy/supabase/set_password.py admin@example.com
```

Leave the email off and it lists the accounts and asks. The password is
typed at a prompt, not passed as an argument, so it stays out of shell
history and the process list.

## Before this faces anyone but you

- `GOTRUE_MAILER_AUTOCONFIRM` is `true`, because there is no SMTP here and a
  confirmation mail could never arrive. Wire `GOTRUE_SMTP_*` and turn it off.
- The ports bind to loopback. Putting this on a network means TLS in front and
  a real `SUPABASE_PUBLIC_URL`.
- `docker compose down -v` deletes the database. There is no backup job here;
  `pg_dump` against port 5433 is the whole story.

## Regenerating `.env`

```python
import secrets, time, jwt
jwt_secret = secrets.token_urlsafe(48)
iat = int(time.time()); exp = iat + 10 * 365 * 24 * 3600
key = lambda role: jwt.encode(
    {"role": role, "iss": "supabase", "iat": iat, "exp": exp},
    jwt_secret, algorithm="HS256")
print("JWT_SECRET=", jwt_secret)
print("SUPABASE_ANON_KEY=", key("anon"))
print("SUPABASE_SERVICE_ROLE_KEY=", key("service_role"))
```
