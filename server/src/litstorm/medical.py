"""Where MedicalReviewerAgent is, for the Medical Review mode (docs/adr/0013).

MRA is a service of its own (its own Postgres, Redis, workers, academic
SearXNG and web app); this system only knows its address and an API key
minted there (`python -m app.cli.keys mint`). The address is MRA's site
origin, its Caddy, which serves both its API (/api/v1) and its report pages
(/r/{id}). The key is kept encrypted, like every other key here.
Its models, sources, limits and glossary are set in MRA's own console.
"""

from pydantic import BaseModel

from litstorm import security
from litstorm.db.models import SystemSetting

KEY = "medical"
API = "/api/v1"
REVIEW_TYPES = ("slr", "meta_analysis", "scoping", "narrative")
MODES = ("quick", "full")
STUDY_TYPES = (
    "RCT", "Cohort", "Case-control", "Cross-sectional", "Non-randomized trial", "Qualitative", "Mixed methods",
    "Systematic review", "Meta-analysis",
)


class Stored(BaseModel):
    url: str = ""  # where this system's Worker and API reach MRA
    web_url: str = ""  # where people open it, when that differs (links to its console); empty: `url`
    api_key_ciphertext: str = ""


def load(session):
    row = session.get(SystemSetting, KEY)
    return Stored(**(row.value if row else {}))


def save(session, url=None, api_key=None, web_url=None):
    """Change the addresses, the key, or all; an empty key leaves the stored one."""
    value = load(session)
    if url is not None:
        value.url = url.strip().rstrip("/")
    if web_url is not None:
        value.web_url = web_url.strip().rstrip("/")
    if api_key:
        value.api_key_ciphertext = security.encrypt(api_key.strip())
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)
    return value


def configured(session):
    value = load(session)
    return bool(value.url and value.api_key_ciphertext)


def key(session):
    value = load(session)
    return security.decrypt(value.api_key_ciphertext) if value.api_key_ciphertext else ""


def release(session, run_id, url, api_key):
    """Tell MRA to stop the review a cancelled Run was following, unless
    another Run still follows it: the same question asked twice within a
    day is one review there (its cache), and one owner stopping must not stop
    the other's. Best effort: a review left running costs only MRA's time."""
    import httpx
    from sqlalchemy import select

    from litstorm.db.models import ACTIVE, Run

    run = session.get(Run, run_id)
    review_id = ((run.notes or {}).get("service") or {}).get("review_id") if run else None
    if not review_id or not url or not api_key:
        return False
    sharing = session.scalar(
        select(Run.id).where(
            Run.id != run_id, Run.status.in_(ACTIVE), Run.notes["service"]["review_id"].astext == review_id
        ).limit(1)
    )
    if sharing is not None:
        return False
    try:
        httpx.delete(f"{url.rstrip('/')}{API}/reviews/{review_id}", headers={"X-API-Key": api_key}, timeout=10.0)
    except httpx.HTTPError:
        return False
    return True


NO_REVIEW = "00000000-0000-0000-0000-000000000000"


def check(url, api_key, timeout=5.0):
    """Whether MRA answers at `url`, takes reviews now, and takes this key:
    {reachable, accepting, reason, key_ok, sources}. Asking for a review
    that does not exist with the key costs nothing: MRA answers 401 to a key
    it does not know and 404 otherwise."""
    import httpx

    out = {"reachable": False, "accepting": False, "reason": None, "key_ok": None, "sources": []}
    if not url:
        out["reason"] = "not_configured"
        return out
    try:
        status = httpx.get(f"{url.rstrip('/')}{API}/status", timeout=timeout)
        status.raise_for_status()
        body = status.json()
    except (httpx.HTTPError, ValueError) as error:
        out["reason"] = f"unreachable: {str(error)[:200]}"
        return out
    out.update(reachable=True, accepting=bool(body.get("accepting")), reason=body.get("reason"),
               sources=[s.get("label") or s.get("id") for s in body.get("sources") or []])
    if api_key:
        try:
            probe = httpx.get(f"{url.rstrip('/')}{API}/reviews/{NO_REVIEW}", headers={"X-API-Key": api_key},
                              timeout=timeout)
            out["key_ok"] = probe.status_code != 401
        except httpx.HTTPError:
            out["key_ok"] = None
    return out
