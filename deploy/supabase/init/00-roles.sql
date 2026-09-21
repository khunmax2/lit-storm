-- Roles GoTrue and PostgREST sign in as.
--
-- The supabase/postgres image creates most of these already, so every
-- statement here has to be safe to run against a cluster that has them.
-- Postgres has no CREATE ROLE IF NOT EXISTS, hence the DO blocks.
--
-- This runs once, on an empty data directory, before any other container
-- starts. The application's own schema cannot run here: it references
-- auth.users and auth.uid(), and the auth schema does not exist until GoTrue
-- has run its migrations. That is the `schema` service in the compose file.

do $$
begin
  -- The supabase/postgres image runs as `supabase_admin`, so `postgres` does
  -- not exist here — but GoTrue's own migrations grant SELECT on every auth
  -- table to `postgres` by name, and fail the whole startup if it is missing.
  -- Hosted Supabase has this role; so must this.
  if not exists (select 1 from pg_roles where rolname = 'postgres') then
    create role postgres login superuser createdb createrole;
  end if;

  -- Read-only, unauthenticated. PostgREST starts every request as this role
  -- and switches to `authenticated` when a JWT says so.
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;

  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;

  -- Bypasses row-level security. This is the role behind SUPABASE_SECRET_KEY,
  -- and the reason that key must never reach a browser.
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;

  -- PostgREST's own login. It holds no privileges of its own; it can only
  -- become one of the three roles above.
  if not exists (select 1 from pg_roles where rolname = 'authenticator') then
    create role authenticator login noinherit;
  end if;

  -- GoTrue's login, owner of the auth schema it migrates.
  if not exists (select 1 from pg_roles where rolname = 'supabase_auth_admin') then
    create role supabase_auth_admin login noinherit createrole;
  end if;
end
$$;

-- Passwords, applied whether the roles were just created or already existed.
-- :'password' is passed by the entrypoint as POSTGRES_PASSWORD.
\set password `echo "$POSTGRES_PASSWORD"`
alter role postgres with password :'password';
alter role authenticator with password :'password';
alter role supabase_auth_admin with password :'password';

grant anon, authenticated, service_role to authenticator;

-- GoTrue creates and owns `auth`; grant it the room to do so.
create schema if not exists auth authorization supabase_auth_admin;
grant all privileges on schema auth to supabase_auth_admin;
alter role supabase_auth_admin set search_path = auth, public;

grant usage on schema public to anon, authenticated, service_role;

-- The baseline grant hosted Supabase applies for you, and which the app's
-- schema assumes: it opens with `revoke ... from anon, authenticated` and then
-- grants back named columns. Without something to revoke, those grants leave
-- the tables unreachable and every query comes back "permission denied for
-- table profiles" — which looks like a policy problem and is not one.
--
-- Set as default privileges rather than granted directly, because the tables
-- do not exist yet: they are created by `postgres` when the schema service
-- runs, and inherit this. Row-level security is what actually filters rows;
-- these grants only decide who may ask.
alter default privileges for role postgres in schema public
  grant all on tables to anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant all on sequences to anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant all on functions to anon, authenticated, service_role;
