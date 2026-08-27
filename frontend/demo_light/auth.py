"""Accounts, roles and run quota, backed by Supabase.

Two roles. `member` is everyone who signs up and is what the product is for:
they create reports. `admin` is that plus the roster and everyone's runs.

Spending is not a role. A member creating reports is the point, so what keeps
one shared API key from being drained is `monthly_run_limit` on each profile,
which an admin raises or lowers per person.

The schema and its row-level policies live in docs/supabase-schema.sql; the
policies are what actually enforce this, and the checks here only decide what
to draw.
"""

import os
from datetime import datetime, timezone

import streamlit as st

SESSION_KEY = "auth_session"
PROFILE_KEY = "auth_profile"


class AuthUnavailable(RuntimeError):
    """Supabase is not configured, so there is nothing to sign in to."""


def setting(name):
    """A secret from secrets.toml, or failing that the environment.

    A container image should not carry secrets.toml, so the same settings have
    to be reachable as environment variables for a Docker deployment.
    """
    try:
        if name in st.secrets:
            return st.secrets[name]
    except FileNotFoundError:
        pass
    return os.environ.get(name)


@st.cache_resource(show_spinner=False)
def _client():
    """The Supabase client, built once per process."""
    from supabase import create_client

    url = setting("SUPABASE_URL")
    key = setting("SUPABASE_ANON_KEY")
    if not url or not key:
        raise AuthUnavailable(
            "SUPABASE_URL and SUPABASE_ANON_KEY are missing from "
            ".streamlit/secrets.toml and from the environment"
        )
    return create_client(url, key)


def configured():
    """Whether sign-in is possible at all."""
    try:
        _client()
    except AuthUnavailable:
        return False
    return True


# --------------------------------------------------------------- session
def _remember(session):
    """Hold the session for this browser tab and load the profile with it.

    Streamlit has no cookie API, so this lives in session state: reloading the
    page ends the session and asks for the password again. That is a real
    limitation, not an oversight — see the README.
    """
    st.session_state[SESSION_KEY] = session
    st.session_state.pop(PROFILE_KEY, None)


def sign_up(email, password, display_name):
    result = _client().auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {"data": {"display_name": display_name}},
        }
    )
    # With e-mail confirmation on, Supabase returns a user but no session.
    if result.session:
        _remember(result.session)
    return result


def sign_in(email, password):
    result = _client().auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    _remember(result.session)
    return result


def sign_out():
    try:
        _client().auth.sign_out()
    except Exception:  # noqa: BLE001 - signing out must not raise at the user
        pass
    for key in (SESSION_KEY, PROFILE_KEY):
        st.session_state.pop(key, None)


def session():
    return st.session_state.get(SESSION_KEY)


def signed_in():
    return session() is not None


def user_id():
    current = session()
    return current.user.id if current else None


# --------------------------------------------------------------- profile
def profile():
    """The signed-in user's row from `profiles`, fetched once per session."""
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]
    if not signed_in():
        return None

    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("profiles").select("*").eq("id", user_id()).limit(1).execute()
    )
    found = rows.data[0] if rows.data else None

    if found is None:
        # First sign-in. The row is written here rather than by a trigger on
        # auth.users, which Supabase does not let a project own.
        found = _create_profile(client)

    st.session_state[PROFILE_KEY] = found
    return found


def _create_profile(client):
    """Write this account's profile row. Role and quota keep their defaults —
    the insert policy allows only your own id, and the column grants mean the
    values that matter cannot be chosen here anyway."""
    current = session().user
    meta = current.user_metadata or {}
    try:
        rows = (
            client.table("profiles")
            .insert(
                {
                    "id": current.id,
                    "email": current.email,
                    "display_name": meta.get("display_name")
                    or (current.email or "").split("@")[0],
                }
            )
            .execute()
        )
    except Exception:  # noqa: BLE001 - a racing sign-in may have won
        rows = (
            client.table("profiles").select("*").eq("id", current.id).limit(1).execute()
        )
    return rows.data[0] if rows.data else None


def is_admin():
    current = profile()
    return bool(current and current.get("role") == "admin")


def display_name():
    current = profile()
    if current:
        return current.get("display_name") or current.get("email", "")
    return ""


# ----------------------------------------------------------------- quota
def _month_start():
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def runs_this_month():
    """How many runs the signed-in user has started since the 1st.

    Failures count. A run that fails still spent the tokens it spent before it
    failed, and not counting them would make the limit trivial to sidestep.
    """
    if not signed_in():
        return 0
    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("runs")
        .select("id")
        .eq("user_id", user_id())
        .gte("started_at", _month_start().isoformat())
        .execute()
    )
    return len(rows.data or [])


def quota():
    """(used, limit) for the current month. A limit of 0 blocks new runs."""
    current = profile()
    limit = current.get("monthly_run_limit", 0) if current else 0
    return runs_this_month(), limit


def may_run():
    used, limit = quota()
    return used < limit


def record_run_start(topic, language):
    """Open a row in the ledger and return its id, or None if unavailable."""
    if not signed_in():
        return None
    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("runs")
        .insert(
            {
                "user_id": user_id(),
                "topic": topic,
                "language": language,
                "status": "running",
            }
        )
        .execute()
    )
    return rows.data[0]["id"] if rows.data else None


def record_run_end(run_id, status, folder=None, error=None):
    if not run_id or not signed_in():
        return
    client = _client()
    client.postgrest.auth(session().access_token)
    client.table("runs").update(
        {
            "status": status,
            "folder": folder,
            "error": (error or "")[:500] or None,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", run_id).execute()


# ----------------------------------------------------------------- admin
# These read and write other people's rows. The row-level policies are what
# actually permit or refuse that; `is_admin()` here only decides what to draw.
def list_profiles():
    """Every profile, newest first. Empty for a member — by policy, not by us."""
    if not signed_in():
        return []
    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("profiles")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return rows.data or []


def update_profile(profile_id, **fields):
    """Change role, limit or active state on one profile.

    Through a SECURITY DEFINER function, not a table write: `authenticated`
    deliberately has no grant on those three columns, so that a member cannot
    promote themselves through the same policy that lets them rename
    themselves. The admin check lives inside the function.
    """
    client = _client()
    client.postgrest.auth(session().access_token)
    client.rpc(
        "admin_set_profile",
        {
            "target": profile_id,
            "new_role": fields.get("role"),
            "new_limit": fields.get("monthly_run_limit"),
            "new_active": fields.get("is_active"),
        },
    ).execute()
    # The signed-in user may have just changed their own row.
    st.session_state.pop(PROFILE_KEY, None)


def usage_since_month_start():
    """Runs started this month, counted per user id."""
    if not signed_in():
        return {}
    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("runs")
        .select("user_id")
        .gte("started_at", _month_start().isoformat())
        .execute()
    )
    counts = {}
    for row in rows.data or []:
        counts[row["user_id"]] = counts.get(row["user_id"], 0) + 1
    return counts


def recent_runs(limit=25):
    if not signed_in():
        return []
    client = _client()
    client.postgrest.auth(session().access_token)
    rows = (
        client.table("runs")
        .select("topic,language,status,started_at,user_id")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return rows.data or []


def admin_count(profiles):
    return sum(1 for row in profiles if row.get("role") == "admin")
