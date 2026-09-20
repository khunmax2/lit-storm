-- STORM — accounts, roles and run accounting.
-- Paste the whole file into the Supabase SQL editor and run it once. It is
-- safe to run again.
--
-- Two roles, because the app does two kinds of thing:
--   member — signs up, creates reports, sees their own
--   admin  — all of that, plus everyone's runs and the roster
--
-- Cost control is deliberately NOT a role. Every member can create reports,
-- which is the point of the product; what keeps one shared API key from being
-- drained is a per-person monthly limit an admin can raise or lower.

-- ---------------------------------------------------------------- profiles
create table if not exists public.profiles (
    id                 uuid primary key references auth.users on delete cascade,
    email              text not null,
    display_name       text,
    role               text not null default 'member'
                       check (role in ('member', 'admin')),
    monthly_run_limit  integer not null default 10 check (monthly_run_limit >= 0),
    is_active          boolean not null default true,
    created_at         timestamptz not null default now()
);

comment on column public.profiles.monthly_run_limit is
    'Research runs allowed per calendar month. 0 blocks new runs without '
    'removing the account; raise it for people who need more.';

-- Deliberately no trigger on auth.users. Supabase does not grant ownership of
-- that table, so `create trigger ... on auth.users` fails — and because the
-- editor runs the file as one transaction, that failure would roll back every
-- table above it. The app writes the profile row on first sign-in instead.

-- Creation provenance is written only by trusted server operations. Existing
-- accounts stay unknown; creating a profile at first sign-in is not proof of
-- how its Auth account was originally registered.
alter table public.profiles add column if not exists created_via text
    not null default 'legacy_unknown'
    check (created_via in ('legacy_unknown', 'first_sign_in', 'self_signup', 'admin_create'));
alter table public.profiles add column if not exists created_by uuid;
alter table public.profiles add column if not exists account_created_at timestamptz;

create table if not exists public.member_audit_log (
    id uuid primary key default gen_random_uuid(),
    actor_id uuid,
    target_id uuid,
    event text not null check (event in ('account_created', 'profile_created', 'profile_updated', 'account_creation_failed')),
    source text not null,
    outcome text not null check (outcome in ('success', 'failed')),
    before_values jsonb,
    after_values jsonb,
    details jsonb,
    occurred_at timestamptz not null default now()
);
create index if not exists member_audit_time_idx
    on public.member_audit_log (occurred_at desc);
-- No foreign keys on historical actor/target identifiers: audit history must
-- survive removal of an Auth account through the Supabase dashboard.

-- -------------------------------------------------------------------- runs
-- One row per research run: what was asked, how it ended, and what it cost in
-- quota. The article itself stays on disk; this is the ledger.
create table if not exists public.runs (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references public.profiles(id) on delete cascade,
    topic          text not null,
    language       text not null default 'English',
    status         text not null default 'running'
                   check (status in ('running', 'done', 'failed')),
    folder         text,
    word_count     integer,
    source_count   integer,
    error          text,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz
);

create index if not exists runs_user_started_idx
    on public.runs (user_id, started_at desc);

-- ------------------------------------------------------------------ policies
alter table public.profiles enable row level security;
alter table public.runs enable row level security;
alter table public.member_audit_log enable row level security;

-- Whether the caller is an admin. SECURITY DEFINER so the policies below can
-- read profiles without recursing through the very policy being evaluated.
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer set search_path = ''
as $$
    select exists (
        select 1 from public.profiles
        where id = auth.uid() and role = 'admin' and is_active
    );
$$;

create or replace function public.is_active_member()
returns boolean language sql stable security definer set search_path = ''
as $$
    select exists (select 1 from public.profiles where id = auth.uid() and is_active);
$$;

revoke all on public.member_audit_log from public, anon, authenticated;
grant select on public.member_audit_log to authenticated;
grant all on public.member_audit_log to service_role;
drop policy if exists "admin reads member audit" on public.member_audit_log;
create policy "admin reads member audit" on public.member_audit_log
    for select to authenticated using (public.is_admin());
-- No DELETE operation is exposed by the application, including for admins.
revoke delete on public.profiles from anon, authenticated;

create or replace function public.audit_profile_creation()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
    if new.created_via = 'legacy_unknown' and auth.uid() = new.id then
        new.created_via := 'first_sign_in';
        new.created_by := null;
    end if;
    if new.account_created_at is null then
        select created_at into new.account_created_at from auth.users where id = new.id;
    end if;
    insert into public.member_audit_log (actor_id, target_id, event, source, outcome, after_values)
    values (coalesce(new.created_by, auth.uid()), new.id,
        case when new.created_via in ('admin_create', 'self_signup') then 'account_created' else 'profile_created' end,
        new.created_via, 'success',
        jsonb_build_object('email', new.email, 'display_name', new.display_name,
            'role', new.role, 'monthly_run_limit', new.monthly_run_limit, 'is_active', new.is_active));
    return new;
end;
$$;
drop trigger if exists profile_creation_audit on public.profiles;
create trigger profile_creation_audit before insert on public.profiles
    for each row execute function public.audit_profile_creation();
revoke all on function public.audit_profile_creation() from public, anon, authenticated;

-- Backend-only registration: identity, email and timestamps come from Auth,
-- never from editable user_metadata provenance or a browser-supplied actor.
create or replace function public.admin_creation_ready(actor uuid)
returns void language plpgsql security definer set search_path = ''
as $$
begin
    if not exists (select 1 from public.profiles where id = actor and role = 'admin' and is_active) then
        raise exception 'not authorised';
    end if;
end;
$$;
revoke all on function public.admin_creation_ready(uuid) from public, anon, authenticated;
grant execute on function public.admin_creation_ready(uuid) to service_role;

create or replace function public.register_account_creation(
    created_user uuid, creation_source text, creator uuid default null
)
returns void language plpgsql security definer set search_path = ''
as $$
declare
    identity_row auth.users%rowtype;
    existing_source text;
begin
    perform pg_catalog.pg_advisory_xact_lock(742019);
    if creation_source not in ('self_signup', 'admin_create') then
        raise exception 'unknown creation source';
    end if;
    if creation_source = 'admin_create' then
        perform public.admin_creation_ready(creator);
    elsif creator is not null then
        raise exception 'self registration cannot have an admin creator';
    end if;
    select * into identity_row from auth.users where id = created_user;
    if not found or identity_row.email is null then
        raise exception 'missing Auth account';
    end if;
    select created_via into existing_source from public.profiles where id = created_user for update;
    if found then
        -- A retry of the same completed operation is harmless. Never rewrite
        -- provenance of another operation or an existing legacy account.
        if existing_source = creation_source then return; end if;
        if creation_source <> 'self_signup' or existing_source <> 'first_sign_in' then
            raise exception 'account provenance already exists';
        end if;
        update public.profiles set created_via = creation_source, created_by = creator,
            account_created_at = identity_row.created_at where id = created_user;
        insert into public.member_audit_log (actor_id, target_id, event, source, outcome)
            values (creator, created_user, 'account_created', creation_source, 'success');
        return;
    end if;
    insert into public.profiles (id, email, display_name, created_via, created_by, account_created_at)
    values (identity_row.id, identity_row.email,
        coalesce(nullif(identity_row.raw_user_meta_data ->> 'display_name', ''), split_part(identity_row.email, '@', 1)),
        creation_source, creator, identity_row.created_at);
end;
$$;
revoke all on function public.register_account_creation(uuid, text, uuid) from public, anon, authenticated;
grant execute on function public.register_account_creation(uuid, text, uuid) to service_role;

create or replace function public.record_account_creation_failure(actor uuid, target_email text, reason text)
returns void language sql security definer set search_path = ''
as $$
    insert into public.member_audit_log (actor_id, event, source, outcome, details)
    values (actor, 'account_creation_failed', 'admin_create', 'failed',
        jsonb_build_object('email', target_email, 'reason', reason));
$$;
revoke all on function public.record_account_creation_failure(uuid, text, text) from public, anon, authenticated;
grant execute on function public.record_account_creation_failure(uuid, text, text) to service_role;

-- Only authorised backend calls can supply identity/provenance above. Ordinary
-- authenticated accounts can still create their own default profile below.

drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles
    for select using (auth.uid() = id or public.is_admin());

-- The app creates this row the first time someone signs in. Only ever your
-- own, and the columns that matter are locked down by the grants below.
--
-- `email` is checked against the token rather than left to the caller. It is
-- only ever displayed, so a wrong value impersonates nobody — but it is the
-- address an admin reads off the roster before deciding who to promote, and
-- that decision should not be made from a self-declared string.
drop policy if exists "create own profile" on public.profiles;
create policy "create own profile" on public.profiles
    for insert with check (
        auth.uid() = id
        and email = auth.jwt() ->> 'email'
    );

drop policy if exists "update own profile" on public.profiles;
create policy "update own profile" on public.profiles
    for update using (auth.uid() = id) with check (auth.uid() = id);

-- A row policy cannot restrict *which columns* a statement touches, so on its
-- own the policy above would let a member set their own role to 'admin', or
-- hand themselves an unlimited quota, through the same rule that lets them
-- rename themselves. Column grants are what actually prevent that.
--
-- Both verbs need locking down, not just one. Revoking UPDATE alone still
-- leaves INSERT, and the insert policy only checks that the row is yours —
-- so a new account could simply *arrive* as an admin on the request that
-- creates its profile. What is not granted falls back to the column default.
revoke update on public.profiles from authenticated;
grant update (display_name) on public.profiles to authenticated;

revoke insert on public.profiles from authenticated;
grant insert (id, email, display_name) on public.profiles to authenticated;

drop policy if exists "read own runs" on public.runs;
create policy "read own runs" on public.runs
    for select using ((auth.uid() = user_id and public.is_active_member()) or public.is_admin());

drop policy if exists "record own runs" on public.runs;
create policy "record own runs" on public.runs
    for insert with check (auth.uid() = user_id and public.is_active_member());

drop policy if exists "close own runs" on public.runs;
create policy "close own runs" on public.runs
    for update using (auth.uid() = user_id and public.is_active_member()) with check (auth.uid() = user_id and public.is_active_member());

-- The ledger is what the monthly limit is counted from, so the columns that
-- decide whether a row counts are not the caller's to write. `started_at`
-- especially: left writable, anyone could backdate their own runs out of the
-- current month and start again from zero.
revoke insert, update on public.runs from authenticated;
grant insert (user_id, topic, language, status) on public.runs to authenticated;
grant update (status, folder, word_count, source_count, error, finished_at)
    on public.runs to authenticated;

-- ------------------------------------------------------- admin edits
-- The one way role, quota and active state change. SECURITY DEFINER so it can
-- write columns the caller has no grant on, with the admin check inside rather
-- than trusting whoever called it.
-- All edits in a save are atomic. The shared transaction lock also prevents
-- concurrent admins from leaving the system without an active admin.
create or replace function public.admin_set_profiles(edits jsonb)
returns integer language plpgsql security definer set search_path = ''
as $$
declare
    item jsonb;
    changes jsonb;
    old_row public.profiles%rowtype;
    desired_role text;
    desired_active boolean;
    desired_limit integer;
    written integer := 0;
    actor uuid := auth.uid();
begin
    perform pg_catalog.pg_advisory_xact_lock(742019);
    if not exists (select 1 from public.profiles where id = actor and role = 'admin' and is_active) then
        raise exception 'not authorised';
    end if;
    if jsonb_typeof(edits) <> 'array' then raise exception 'invalid edits'; end if;
    for item in select value from jsonb_array_elements(edits) loop
        select * into old_row from public.profiles where id = (item ->> 'target')::uuid for update;
        if not found then raise exception 'missing member'; end if;
        changes := item -> 'changes';
        if jsonb_typeof(changes) <> 'object' or changes - array['role', 'monthly_run_limit', 'is_active'] <> '{}'::jsonb then
            raise exception 'invalid fields';
        end if;
        if item -> 'expected' is not null and item -> 'expected' <> 'null'::jsonb
           and item -> 'expected' <> jsonb_build_object('role', old_row.role,
                'monthly_run_limit', old_row.monthly_run_limit, 'is_active', old_row.is_active) then
            raise exception 'member changed; reload before saving';
        end if;
        if changes ? 'role' and (jsonb_typeof(changes -> 'role') <> 'string' or changes ->> 'role' not in ('member', 'admin')) then
            raise exception 'unknown role';
        end if;
        if changes ? 'is_active' and jsonb_typeof(changes -> 'is_active') <> 'boolean' then
            raise exception 'invalid status';
        end if;
        if changes ? 'monthly_run_limit' and (jsonb_typeof(changes -> 'monthly_run_limit') <> 'number'
            or (changes ->> 'monthly_run_limit') !~ '^[0-9]+$') then
            raise exception 'invalid limit';
        end if;
        desired_role := coalesce(changes ->> 'role', old_row.role);
        desired_active := coalesce((changes ->> 'is_active')::boolean, old_row.is_active);
        desired_limit := coalesce((changes ->> 'monthly_run_limit')::integer, old_row.monthly_run_limit);
        if old_row.id = actor and (desired_role <> 'admin' or not desired_active) then
            raise exception 'cannot demote or suspend your own account';
        end if;
        if desired_limit < 0 then raise exception 'invalid limit'; end if;
        if (desired_role, desired_active, desired_limit) = (old_row.role, old_row.is_active, old_row.monthly_run_limit) then
            continue;
        end if;
        update public.profiles set role = desired_role, is_active = desired_active,
            monthly_run_limit = desired_limit where id = old_row.id;
        if not exists (select 1 from public.profiles where role = 'admin' and is_active) then
            raise exception 'at least one active admin is required';
        end if;
        insert into public.member_audit_log (actor_id, target_id, event, source, outcome, before_values, after_values)
        values (actor, old_row.id, 'profile_updated', 'admin_edit', 'success',
            jsonb_build_object('role', old_row.role, 'monthly_run_limit', old_row.monthly_run_limit, 'is_active', old_row.is_active),
            jsonb_build_object('role', desired_role, 'monthly_run_limit', desired_limit, 'is_active', desired_active));
        written := written + 1;
    end loop;
    return written;
end;
$$;
revoke all on function public.admin_set_profiles(jsonb) from public, anon;
grant execute on function public.admin_set_profiles(jsonb) to authenticated;

-- Keep the original RPC compatible, enforcing the same guards and audit log.
create or replace function public.admin_set_profile(
    target uuid, new_role text default null,
    new_limit integer default null, new_active boolean default null
)
returns void language plpgsql security definer set search_path = ''
as $$
begin
    perform public.admin_set_profiles(jsonb_build_array(jsonb_build_object(
        'target', target, 'changes', jsonb_strip_nulls(jsonb_build_object(
            'role', new_role, 'monthly_run_limit', new_limit, 'is_active', new_active)))));
end;
$$;
revoke all on function public.admin_set_profile(uuid, text, integer, boolean) from public, anon;
grant execute on function public.admin_set_profile(uuid, text, integer, boolean) to authenticated;

-- ------------------------------------------------------------- first admin
-- Sign up through the app first, then run this once with your own address.
--   update public.profiles set role = 'admin' where email = 'you@example.com';
