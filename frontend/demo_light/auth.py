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

from datetime import datetime, timezone

import streamlit as st

SESSION_KEY = "auth_session"
PROFILE_KEY = "auth_profile"


class AuthUnavailable(RuntimeError):
    """Supabase is not configured, so there is nothing to sign in to."""


@st.cache_resource(show_spinner=False)
def _client():
    """The Supabase client, built once per process."""
    from supabase import create_client

    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except (KeyError, FileNotFoundError) as error:
        raise AuthUnavailable(
            "SUPABASE_URL and SUPABASE_ANON_KEY are missing from "
            ".streamlit/secrets.toml"
        ) from error
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
    st.session_state[PROFILE_KEY] = found
    return found


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
