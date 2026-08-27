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
        where id = auth.uid() and role = 'admin'
    );
$$;

drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles
    for select using (auth.uid() = id or public.is_admin());

-- The app creates this row the first time someone signs in. Only ever your
-- own, and the columns that matter are locked down by the grants below.
drop policy if exists "create own profile" on public.profiles;
create policy "create own profile" on public.profiles
    for insert with check (auth.uid() = id);

drop policy if exists "update own profile" on public.profiles;
create policy "update own profile" on public.profiles
    for update using (auth.uid() = id) with check (auth.uid() = id);

-- A row policy cannot restrict *which columns* an update touches, so without
-- this a member could set their own role to 'admin', or hand themselves an
-- unlimited quota, through the same policy that lets them rename themselves.
-- Column grants are what actually prevent that. Role, limit and active state
-- change only through admin_set_profile() below.
revoke update on public.profiles from authenticated;
grant update (display_name) on public.profiles to authenticated;

drop policy if exists "read own runs" on public.runs;
create policy "read own runs" on public.runs
    for select using (auth.uid() = user_id or public.is_admin());

drop policy if exists "record own runs" on public.runs;
create policy "record own runs" on public.runs
    for insert with check (auth.uid() = user_id);

drop policy if exists "close own runs" on public.runs;
create policy "close own runs" on public.runs
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ------------------------------------------------------- admin edits
-- The one way role, quota and active state change. SECURITY DEFINER so it can
-- write columns the caller has no grant on, with the admin check inside rather
-- than trusting whoever called it.
create or replace function public.admin_set_profile(
    target      uuid,
    new_role    text default null,
    new_limit   integer default null,
    new_active  boolean default null
)
returns void
language plpgsql
security definer set search_path = ''
as $$
begin
    if not public.is_admin() then
        raise exception 'not authorised';
    end if;
    if new_role is not null and new_role not in ('member', 'admin') then
        raise exception 'unknown role %', new_role;
    end if;

    update public.profiles
    set role              = coalesce(new_role, role),
        monthly_run_limit = coalesce(new_limit, monthly_run_limit),
        is_active         = coalesce(new_active, is_active)
    where id = target;
end;
$$;

revoke all on function public.admin_set_profile(uuid, text, integer, boolean) from public;
grant execute on function public.admin_set_profile(uuid, text, integer, boolean)
    to authenticated;

-- ------------------------------------------------------------- first admin
-- Sign up through the app first, then run this once with your own address.
--   update public.profiles set role = 'admin' where email = 'you@example.com';
