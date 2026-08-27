-- STORM — accounts, roles and run accounting.
-- Paste this into the Supabase SQL editor once, on a fresh project.
--
-- Two roles, because the app does two kinds of thing:
--   member — signs up, creates reports, sees their own
--   admin  — all of that, plus sees everyone and manages the roster
--
-- Cost control is deliberately NOT a role. Every member can create reports,
-- which is the point of the product; what keeps one shared API key from being
-- drained is a per-person monthly limit that an admin can raise or lower.

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

-- A profile row for every new sign-up, so the app never meets a user it has
-- no record of.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
    insert into public.profiles (id, email, display_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1))
    );
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

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

drop policy if exists "update own name" on public.profiles;
create policy "update own name" on public.profiles
    for update using (auth.uid() = id) with check (auth.uid() = id);

-- Only an admin changes roles, limits or active state.
drop policy if exists "admin manages profiles" on public.profiles;
create policy "admin manages profiles" on public.profiles
    for update using (public.is_admin()) with check (public.is_admin());

drop policy if exists "read own runs" on public.runs;
create policy "read own runs" on public.runs
    for select using (auth.uid() = user_id or public.is_admin());

drop policy if exists "record own runs" on public.runs;
create policy "record own runs" on public.runs
    for insert with check (auth.uid() = user_id);

drop policy if exists "close own runs" on public.runs;
create policy "close own runs" on public.runs
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ------------------------------------------------------------- first admin
-- Sign up through the app first, then run this once with your own address.
--   update public.profiles set role = 'admin' where email = 'you@example.com';
