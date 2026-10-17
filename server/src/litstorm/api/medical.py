"""Medical Review's settings and state (docs/adr/0013): where
MedicalReviewerAgent is and its key, for an Administrator; whether it takes
reviews now, for the tab. MRA's own settings stay in MRA's console."""

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from litstorm import medical
from litstorm.api import deps

router = APIRouter(prefix="/api", tags=["medical"])
admin = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(deps.admin)])

STATUS_TTL = 30.0  # seconds a look at MRA's /status is reused for the tab
_status = {"at": 0.0, "url": None, "value": None}


class MedicalCheck(BaseModel):
    reachable: bool
    accepting: bool
    reason: str | None
    key_ok: bool | None = None  # None: not asked (no key) or not answered
    sources: list[str] = []


class MedicalSettingsOut(BaseModel):
    url: str
    web_url: str
    console_url: str  # MRA's admin console, for people
    has_key: bool
    configured: bool


class MedicalSettingsIn(BaseModel):
    url: str = Field(max_length=500)
    web_url: str = Field(default="", max_length=500)
    # Empty: keep the stored one.
    api_key: str | None = Field(default=None, max_length=500)


def _out(value):
    web = value.web_url or value.url
    return MedicalSettingsOut(
        url=value.url, web_url=value.web_url, console_url=f"{web}/admin" if web else "",
        has_key=bool(value.api_key_ciphertext), configured=bool(value.url and value.api_key_ciphertext),
    )


@admin.get("/medical", response_model=MedicalSettingsOut)
def get_settings(session=Depends(deps.database)):
    return _out(medical.load(session))


@admin.put("/medical", response_model=MedicalSettingsOut)
def put_settings(body: MedicalSettingsIn, session=Depends(deps.database)):
    value = medical.save(session, url=body.url, api_key=body.api_key, web_url=body.web_url)
    session.commit()
    _status["at"] = 0.0
    return _out(value)


@admin.post("/medical/check", response_model=MedicalCheck)
def check_settings(session=Depends(deps.database)):
    """Ask MRA now, with the stored address and key."""
    return MedicalCheck(**medical.check(medical.load(session).url, medical.key(session)))


@router.get("/medical/status", response_model=MedicalCheck)
def status(user=Depends(deps.current_user), session=Depends(deps.database)):
    """Whether Medical Review can take a question now, for the tab's notice.
    Looked up at most every STATUS_TTL seconds, and never with the key."""
    url = medical.load(session).url
    now = time.monotonic()
    if _status["value"] is None or _status["url"] != url or now - _status["at"] > STATUS_TTL:
        _status.update(at=now, url=url, value=medical.check(url, None, timeout=3.0))
    return MedicalCheck(**_status["value"])
