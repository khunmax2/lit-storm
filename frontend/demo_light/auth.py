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

import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import unquote

import streamlit as st

SESSION_KEY = "auth_session"
PROFILE_KEY = "auth_profile"
STARTED_KEY = "auth_started"
SEEN_KEY = "auth_seen"
WROTE_KEY = "auth_cookie_written"

# ------------------------------------------------------------- dev bypass
# Streamlit keeps the session in memory, so every code edit restarts the
# script and asks for the password again. `STORM_DEV_USER=1` stands a
# fabricated account in its place, so the pages behind the gate can be looked
# at while they are being built.
#
# An auth bypass that reaches a deployment is the whole system gone, so it is
# fenced three ways:
#   * off unless the variable is set, and it belongs in the environment or in
#     secrets.toml — neither of which is committed;
#   * refused unless the browser asked for the page over loopback, so setting
#     the variable on a served deployment still does nothing;
#   * never touches Supabase. The profile, the roster and the ledger are made
#     up in memory, so a stray flag can neither read nor write real rows.
# A bar across the top says so on every page and cannot be dismissed.
DEV_FLAG = "STORM_DEV_USER"
DEV_USER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
DEV_SIGNED_OUT = "dev_signed_out"
DEV_RUNS = "dev_runs"
_dev_announced = False


def _hostname(host):
    """The host out of a Host header, without its port. `[::1]:8501` too."""
    host = host.strip()
    if host.startswith("["):
        return host[1:].split("]")[0].lower()
    return host.split(":")[0].lower()


def _local_request():
    """Whether this page was asked for over a loopback address."""
    try:
        headers = st.context.headers or {}
    except Exception:  # noqa: BLE001 - no request behind this run
        return False
    return _hostname(headers.get("Host", "")) in ("localhost", "127.0.0.1", "::1")


def dev_enabled():
    """Whether the bypass is switched on and permitted on this request."""
    global _dev_announced
    flag = str(setting(DEV_FLAG) or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    if not _local_request():
        return False
    if not _dev_announced:
        _dev_announced = True
        print(
            f"[storm] {DEV_FLAG} is on: sign-in is bypassed with a "
            "fabricated local account."
        )
    return True


def dev_mode():
    """`dev_enabled()`, unless the stand-in account has been signed out.

    Signing out only stands it down, so that the real sign-in screen can be
    looked at as well. The strip at the top stays up either way.
    """
    return dev_enabled() and not st.session_state.get(DEV_SIGNED_OUT)


def _dev_profile():
    """The stand-in account. Admin by default, so the roster is reachable;
    set STORM_DEV_ROLE=member to see the app as everyone else sees it."""
    role = str(setting("STORM_DEV_ROLE") or "admin").strip().lower()
    return {
        "id": DEV_USER_ID,
        "email": "dev@localhost",
        "display_name": "Dev User",
        "role": "admin" if role == "admin" else "member",
        "monthly_run_limit": 10,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _dev_roster():
    """A roster for the admin page. Made up, and named so it reads that way."""
    return [
        _dev_profile(),
        {
            "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "email": "member@localhost",
            "display_name": "Dev Member",
            "role": "member",
            "monthly_run_limit": 10,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]


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
# Streamlit's own session state dies with the page, so a refresh used to end
# the session and ask for the password again. What survives a refresh is a
# cookie, and Streamlit can read one but not write one — `st.context.cookies`
# is read-only and there is no `set_cookie`. A component can write it, and
# the one below already ships with the app.
#
# Two clocks, as sessions normally have:
#   idle      nothing touched for this long, and the session ends
#   absolute  the session ends this long after signing in, however busy
COOKIE_NAME = "storm_session"
IDLE_MINUTES = 30
MAX_HOURS = 12
# How stale the "last seen" stamp may get before it is written again. Every
# write is a round trip to the browser, so it is not done on every rerun.
_TOUCH_EVERY = 120


def _limits():
    idle = float(setting("SESSION_IDLE_MINUTES") or IDLE_MINUTES) * 60
    absolute = float(setting("SESSION_MAX_HOURS") or MAX_HOURS) * 3600
    return idle, absolute


COOKIE_MANAGER_KEY = "auth_cookie_manager"


def _cookies():
    """One cookie component per session. Instantiating it twice draws two.

    Held in session state rather than @st.cache_resource: it is a widget, and
    Streamlit refuses to build a widget inside a cached function — the cache
    would hand the same widget to every session.
    """
    if COOKIE_MANAGER_KEY not in st.session_state:
        import extra_streamlit_components as stx

        st.session_state[COOKIE_MANAGER_KEY] = stx.CookieManager(key="storm_cookies")
    return st.session_state[COOKIE_MANAGER_KEY]


def _secure_cookie():
    """Whether the browser reached us over https.

    A Secure cookie is dropped on plain http, which is how a local run is
    served — so this follows the request rather than being set either way.
    """
    try:
        return (st.context.headers or {}).get("X-Forwarded-Proto") == "https" or (
            st.context.url or ""
        ).startswith("https://")
    except Exception:  # noqa: BLE001 - no request behind this run
        return False


def _write_cookie(refresh_token, started, seen=None):
    _, absolute = _limits()
    remaining = absolute - (time.time() - started)
    if remaining <= 0:
        return
    payload = json.dumps(
        {"t": refresh_token, "start": started, "seen": seen or time.time()}
    )
    _cookies().set(
        COOKIE_NAME,
        payload,
        key="storm_cookie_set",
        max_age=remaining,
        same_site="strict",
        secure=_secure_cookie(),
    )


def _read_cookie():
    """The crumb from the browser, read from the request that carried it.

    Not through the component: its `get` returns None on the first render of
    a page load, because the value has not come back from the browser yet —
    which is exactly the moment a refreshed page needs it. `st.context.cookies`
    carries the cookies the browser sent with the request itself, so it is
    there before the first line of the script runs. The component still does
    the writing, which is the half Streamlit has no API for.
    """
    try:
        raw = (st.context.cookies or {}).get(COOKIE_NAME)
    except Exception:  # noqa: BLE001 - no request behind this run
        raw = None
    if not raw:
        # A cookie written earlier in this same page load is not in the
        # request that started it; the component knows about that one.
        try:
            raw = _cookies().get(COOKIE_NAME)
        except Exception:  # noqa: BLE001 - component not ready
            return None
    if not raw:
        return None
    try:
        return json.loads(unquote(raw))
    except (ValueError, TypeError):  # a corrupt cookie is no cookie
        return None


def _clear_cookie():
    try:
        _cookies().delete(COOKIE_NAME, key="storm_cookie_delete")
    except Exception:  # noqa: BLE001 - already gone
        pass


def _remember(session):
    """Hold the session for this tab, and leave a crumb for the next load.

    Only the refresh token is kept. It is what Supabase issues for exactly
    this purpose, it expires, and it is not the password.
    """
    st.session_state[SESSION_KEY] = session
    st.session_state[STARTED_KEY] = time.time()
    st.session_state[SEEN_KEY] = time.time()
    st.session_state.pop(PROFILE_KEY, None)
    token = getattr(session, "refresh_token", None)
    if token:
        _write_cookie(token, st.session_state[STARTED_KEY])


def restore():
    """Bring back a session the browser still remembers.

    Returns True when the caller should carry on as signed in. Called before
    the gate, so a refresh does not land on the sign-in screen.
    """
    if dev_mode() or signed_in():
        return True
    crumb = _read_cookie()
    if not crumb:
        return False

    idle, absolute = _limits()
    now = time.time()
    if now - crumb.get("seen", 0) > idle or now - crumb.get("start", 0) > absolute:
        _clear_cookie()
        return False

    try:
        result = _client().auth.refresh_session(crumb["t"])
    except Exception:  # noqa: BLE001 - a refused token is a signed-out user
        _clear_cookie()
        return False
    if not result or not result.session:
        _clear_cookie()
        return False

    st.session_state[SESSION_KEY] = result.session
    st.session_state[STARTED_KEY] = crumb["start"]
    st.session_state[SEEN_KEY] = now
    st.session_state.pop(PROFILE_KEY, None)
    _write_cookie(result.session.refresh_token, crumb["start"], now)
    return True


def touch():
    """Mark the session as still in use, and end it when it is not.

    Returns False when the session has just been ended, so the caller can
    draw the sign-in screen instead of a page the user is no longer allowed.
    """
    if dev_mode() or not signed_in():
        return signed_in()

    idle, absolute = _limits()
    now = time.time()
    seen = st.session_state.get(SEEN_KEY, now)
    started = st.session_state.get(STARTED_KEY, now)
    if now - seen > idle or now - started > absolute:
        sign_out()
        return False

    st.session_state[SEEN_KEY] = now
    if now - st.session_state.get(WROTE_KEY, 0) > _TOUCH_EVERY:
        st.session_state[WROTE_KEY] = now
        token = getattr(session(), "refresh_token", None)
        if token:
            _write_cookie(token, started, now)
    return True


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
    if dev_mode():
        # Leaves the bypass switched on but stood down, so the real sign-in
        # screen can be looked at too. Reloading the page brings it back.
        st.session_state[DEV_SIGNED_OUT] = True
        st.session_state.pop(PROFILE_KEY, None)
        return
    try:
        _client().auth.sign_out()
    except Exception:  # noqa: BLE001 - signing out must not raise at the user
        pass
    _clear_cookie()
    for key in (SESSION_KEY, PROFILE_KEY, STARTED_KEY, SEEN_KEY, WROTE_KEY):
        st.session_state.pop(key, None)


def session():
    return st.session_state.get(SESSION_KEY)


def signed_in():
    return dev_mode() or session() is not None


def user_id():
    if dev_mode():
        return DEV_USER_ID
    current = session()
    return current.user.id if current else None


# --------------------------------------------------------------- profile
def profile():
    """The signed-in user's row from `profiles`, fetched once per session."""
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]
    if dev_mode():
        return _dev_profile()
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
    if dev_mode():
        return st.session_state.get(DEV_RUNS, 0)
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
    if dev_mode():
        st.session_state[DEV_RUNS] = st.session_state.get(DEV_RUNS, 0) + 1
        return None
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
    if dev_mode():
        return _dev_roster()
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
    if dev_mode():
        st.toast("Dev mode: the roster is fabricated, so nothing was saved.")
        return
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
    if dev_mode():
        return {DEV_USER_ID: st.session_state.get(DEV_RUNS, 0)}
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
    if dev_mode():
        return []
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
