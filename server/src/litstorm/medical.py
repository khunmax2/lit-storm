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
    url: str = ""
    api_key_ciphertext: str = ""


def load(session):
    row = session.get(SystemSetting, KEY)
    return Stored(**(row.value if row else {}))


def save(session, url=None, api_key=None):
    """Change the address, the key, or both; an empty key leaves the stored one."""
    value = load(session)
    if url is not None:
        value.url = url.strip().rstrip("/")
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
