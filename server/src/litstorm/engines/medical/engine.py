"""Medical Review: MedicalReviewerAgent (MRA) as a remote Engine (docs/adr/0013).

MRA is a service of its own; this Engine is its client. It asks MRA for a
review over REST, follows the review's event stream (SSE) and tells this
Run's progress as it goes, then turns MRA's result into report.json
(convert.py) and keeps MRA's own report page beside it.

- **Asked once, followed to the end.** A busy MRA (503 or 429) is asked
  again after the Retry-After it gives, while the Run's time lasts; a
  dropped stream is followed again from the last event read.
- **A review MRA already has** (the same question within 24 hours, or one
  still running) comes back `cached`: it cost nothing, and the Run says so
  ("service_cache"), which also gives its quota back (worker/queue.finish).
- **Stopping.** The Run stops following; whether MRA is told to stop is
  the Worker's to decide, since another Run may share the review
  (worker/main.py, `release`).
- **Cost** is what MRA reports when the review is done, priced there.
"""

import json
import os
import re
import time

import httpx

from litstorm import outcomes
from litstorm.engines.base import EngineFailure

from . import convert

API = "/api/v1"
TIMEOUT = httpx.Timeout(connect=10.0, read=40.0, write=20.0, pool=10.0)  # MRA pings a stream every 15 s
SUBMIT_TRIES = 4  # an MRA that cannot be reached at all
STREAM_TRIES = 6  # a stream that keeps dropping
MAX_WAIT = 60  # seconds, the most one Retry-After is honoured for at a time
TERMINAL = ("done", "error", "rejected", "cancelled")

# MRA's events, by the stage of this Run they belong to (catalog: refine,
# search, screen, read, synthesize).
STAGE_OF = {
    "checking_topic": "refine", "refining": "refine", "question_refined": "refine",
    "planning": "search", "searching": "search", "enriching": "search",
    "screening": "screen", "screened": "screen",
    "external_lookup": "read", "citations_fetched": "read", "reading": "read", "extracted": "read",
    "synthesizing": "synthesize", "pooled": "synthesize", "localizing": "synthesize", "finalizing": "synthesize",
}
# MRA's options this Run may set (the tab's form, api/research.py).
OPTIONS = ("mode", "review_type", "study_types", "year_from")
REVIEW_ID = re.compile(r"^[0-9a-f-]{36}$")


def _message(response):
    """What MRA said, in the shape its refusals take."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        for key in ("message", "detail", "reason", "error"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(body, ensure_ascii=False)[:300]
    return str(body)[:300]


def _declined(response, language):
    """A refusal for the reader: MRA's message in the report's language, and its hotlines when it gives them."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    text = (body.get("message_th") if language == "th" else None) or body.get("message") or _message(response)
    hotlines = body.get("hotlines") or []
    lines = [h if isinstance(h, str) else " ".join(str(v) for v in h.values() if v) for h in hotlines]
    extra = [line for line in lines if line and line not in text]  # MRA's message often names them already
    if extra:
        text += " " + " · ".join(extra)
    return EngineFailure(outcomes.SERVICE_DECLINED, text)


class MedicalEngine:
    name = "medical"

    def run(self, config, secrets, workspace, progress, cancel):
        url = (config.service or {}).get("url", "").rstrip("/")
        if not url or not secrets.service_api_key:
            raise EngineFailure(outcomes.BAD_CONFIGURATION, "Medical Review has no MRA address or key")
        with httpx.Client(base_url=url, headers={"X-API-Key": secrets.service_api_key}, timeout=TIMEOUT) as client:
            review_id, cached = self._submit(client, config, progress, cancel)
            progress.note("service", review_id=review_id, cached=cached)
            if cached:
                progress.note("service_cache", review_id=review_id)
            ended = self._follow(client, review_id, progress, cancel)
            if ended["type"] != "done":
                self._fail(ended, cancel)
            review = client.get(f"{API}/reviews/{review_id}").raise_for_status().json()
            _save(workspace, "mra_review.json", json.dumps(review, ensure_ascii=False))
            if (config.service or {}).get("mode") != "quick":
                _keep_page(client, review_id, workspace, progress)
        usd = None if cached else ended["data"].get("cost_usd", review.get("cost_usd"))
        progress.usage("synthesize", llm={}, search={}, usd=usd or 0.0)
        return convert.to_report(review, config.language, config.topic)

    # --- asking -----------------------------------------------------------------------------

    def _submit(self, client, config, progress, cancel):
        service = config.service or {}
        options = {k: service[k] for k in OPTIONS if service.get(k) not in (None, "", [])}
        body = {"topic": config.topic, "language": config.language, "options": options}
        failures = 0
        while True:
            cancel.check()
            try:
                response = client.post(f"{API}/reviews", json=body)
            except httpx.HTTPError as error:
                failures += 1
                if failures >= SUBMIT_TRIES:
                    raise EngineFailure(outcomes.SERVICE_UNAVAILABLE, f"MRA cannot be reached: {error}") from error
                _sleep(2 ** failures, cancel)
                continue
            if response.status_code in (200, 201, 202):
                answer = response.json()
                review_id = str(answer.get("review_id") or "")
                if not REVIEW_ID.match(review_id):
                    raise EngineFailure(outcomes.ENGINE_ERROR, f"MRA answered without a review id: {answer}")
                return review_id, bool(answer.get("cached"))
            if response.status_code in (429, 503):
                # Busy: its queue or daily capacity is full. Waited out, while the Run's time lasts.
                progress.note("service_busy", status=response.status_code, reason=_message(response))
                _sleep(_retry_after(response), cancel)
                continue
            if response.status_code == 422 and _code(response) == "emergency":
                raise _declined(response, config.language)
            if response.status_code in (401, 403):
                raise EngineFailure(outcomes.BAD_CONFIGURATION, f"MRA refused the key: {_message(response)}")
            raise EngineFailure(outcomes.BAD_CONFIGURATION, f"MRA refused the request ({response.status_code}): "
                                                            f"{_message(response)}")

    # --- following --------------------------------------------------------------------------

    def _follow(self, client, review_id, progress, cancel):
        """Read the review's events until one ends it; return that event."""
        since, stage, drops = 0, None, 0
        while True:
            cancel.check()
            try:
                with client.stream("GET", f"{API}/reviews/{review_id}/events", params={"since": since}) as response:
                    response.raise_for_status()
                    for event in _frames(response.iter_lines(), cancel):
                        since = max(since, event["id"])
                        kind, data = event["type"], event["data"]
                        progress.note("medical", event=kind, seq=event["id"], **data)
                        if STAGE_OF.get(kind) and STAGE_OF[kind] != stage:
                            stage = STAGE_OF[kind]
                            progress.stage(stage)
                        if kind in TERMINAL:
                            return event
                        drops = 0
            except httpx.HTTPError as error:
                drops += 1
                if drops >= STREAM_TRIES:
                    raise EngineFailure(outcomes.SERVICE_UNAVAILABLE, f"MRA stopped answering: {error}") from error
                _sleep(min(2 ** drops, 30), cancel)
                continue
            # The stream closed without an ending: the review may have ended between reads.
            state = client.get(f"{API}/reviews/{review_id}").raise_for_status().json()
            if state.get("status") in TERMINAL:
                return {"id": since, "type": state["status"],
                        "data": {"cost_usd": state.get("cost_usd"), "message": state.get("error")}}
            drops += 1
            if drops >= STREAM_TRIES:
                raise EngineFailure(outcomes.SERVICE_UNAVAILABLE, "MRA's event stream keeps closing")
            _sleep(2, cancel)

    def _fail(self, ended, cancel):
        kind, data = ended["type"], ended.get("data") or {}
        if kind == "cancelled":
            if cancel.requested():
                cancel.check()
            raise EngineFailure(outcomes.SERVICE_UNAVAILABLE, "MRA's administrator cancelled the review")
        if kind == "rejected":
            raise EngineFailure(outcomes.SERVICE_DECLINED, data.get("reason") or "MRA declined the question")
        raise EngineFailure(outcomes.ENGINE_ERROR, f"MRA: {data.get('message') or 'the review failed'}")


def _frames(lines, cancel):
    """SSE frames as {"id", "type", "data"}; a ping or comment is skipped."""
    frame = {}
    for line in lines:
        cancel.check()
        if not line:
            if "type" in frame:
                try:
                    data = json.loads(frame.get("data") or "{}")
                except ValueError:
                    data = {}
                yield {"id": int(frame.get("id") or 0), "type": frame["type"], "data": data if isinstance(data, dict) else {}}
            frame = {}
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            frame["type"] = value
        elif field == "data":
            frame["data"] = frame.get("data", "") + value
        elif field == "id":
            frame["id"] = value


def _keep_page(client, review_id, workspace, progress):
    """MRA's interactive report as one offline HTML file, kept with the Run (the reader's full view)."""
    try:
        response = client.get(f"/r/{review_id}/report.html", timeout=httpx.Timeout(60.0), follow_redirects=False)
    except httpx.HTTPError as error:
        progress.note("service_page", kept=False, reason=str(error)[:200])
        return
    if response.status_code == 200 and response.content:
        _save(workspace, "mra_report.html", response.content)
        progress.note("service_page", kept=True, bytes=len(response.content))
    else:
        progress.note("service_page", kept=False, reason=f"HTTP {response.status_code}")


def _save(workspace, name, content):
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(os.path.join(workspace, name), mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
        f.write(content)


def _code(response):
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    return body.get("code") or (detail.get("code") if isinstance(detail, dict) else None)


def _retry_after(response):
    try:
        return max(1, min(int(response.headers.get("Retry-After", "10")), MAX_WAIT))
    except ValueError:
        return 10


def _sleep(seconds, cancel):
    """Wait, stopping at once if the Run is cancelled."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        cancel.check()
        time.sleep(min(0.5, end - time.monotonic()))
