"""DeepLit's MCP server: research as tools for AI clients and other systems
(docs/adr/0009).

Streamable HTTP at /api/mcp, stateless: every request stands alone, so the
API's processes need no shared session, and a Run's state is in Postgres as
ever. The official SDK's FastMCP does the protocol; `TokenGate` in front of
it admits a request only with a live API token (litstorm.tokens), and every
tool reads who is calling from that request.

The tools call what the web app's endpoints call, so a Run started here
meets the same quota, queue, modes and Search Providers. A Run takes minutes
and a client gives a tool call about a minute: research_start and
research_status follow the Run for up to WAIT seconds, telling progress as
they go, and then hand back its id to ask again.
"""

import asyncio
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from sqlalchemy import select
from starlette.responses import JSONResponse

from litstorm import notify, quota, settings, tokens
from litstorm.api import deps
from litstorm.catalog import ENGINES
from litstorm.db.models import FINAL, INTEGRATION, ApiToken, LlmModel, Run, SearchProvider, User

PATH = "/api/mcp"
# Seconds a tool follows a Run before handing back its id: WAIT unless the
# client asks for up to MAX_WAIT. Agenta, for one, cancels any tool call after
# 30 seconds (its gateway's budget), so the default stays well inside that.
WAIT = 20
MAX_WAIT = 45
# A research_start that repeats one this token made within this many seconds
# returns that Run instead of starting (and paying for) another: a client
# that gave up waiting and called again must not cost a second unit.
REPEAT_WINDOW = 10 * 60
CALLS_PER_MINUTE = 60  # per token, per API process

# The MCP App (docs/adr/0010): a host that renders MCP Apps shows this page
# beside research_start and research_status, a live canvas of the agents a
# Run spawns, fed by research_events. Other clients just get the tools' text.
CANVAS_URI = "ui://deeplit/research-canvas.html"
APP_MIME = "text/html;profile=mcp-app"
ON_CANVAS = {"ui": {"resourceUri": CANVAS_URI}}

INSTRUCTIONS = """DeepLit researches a topic on the web and in academic sources, then writes a report \
whose every claim cites its sources. Research takes from about one minute (depth "fast") to ten or more \
("deep"). Start it with research_start; if it is not finished when the call returns, follow it with \
research_status (each call follows it for 20 seconds by default, up to 45), then read it with research_report. Reports can be \
written in English ("en") or Thai ("th"). research_export gives a short-lived download link for a finished \
report as a file (one HTML page with its charts, plain HTML, Markdown or PDF). research_options lists the modes, \
depths, sources and the quota left. Clients that show MCP Apps draw research_start and research_status as a live canvas of the research agents."""

# What an API refusal means, for whoever reads the tool's error.
_MEANING = {
    "quota_exhausted": "This account has no research quota left this month.",
    "queue_full": "This account already has as many research runs waiting as it may.",
    "engine_not_available": "That mode is not offered on this server. See research_options.",
    "engine_not_allowed": "This account may not start that mode. See research_options.",
    "search_not_for_engine": "That source cannot be used with that mode.",
    "model_cannot_use_tools": "That mode needs a model that can call tools; choose another model or mode.",
    "too_many_sources": "Too many sources for that mode (up to three).",
    "no_default_configured": "The server has no default model or source configured yet.",
    "choice_not_available": "That model or source is switched off. See research_options.",
    "not_found": "No research with that id belongs to this account.",
    "cannot_cancel": "That research has already ended.",
    "no_report": "That research has no report: it did not finish successfully.",
}


def _fail(error):
    detail = getattr(error, "detail", None) or str(error)
    raise ToolError(_MEANING.get(detail, f"Refused: {detail}")) from error


# --- who is calling ---------------------------------------------------------------


class TokenGate:
    """Admits a request to the MCP app only with a live token, and at most
    CALLS_PER_MINUTE a minute for it; puts the token's id on the request for
    the tools. Anything else is answered here, before the protocol."""

    def __init__(self, app):
        self.app = app
        self.calls = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope.get("headers") or []).get(b"authorization", b"").decode("latin-1")
        try:
            _, token = await deps.with_session(lambda s: tokens.authenticate(s, header))
        except tokens.Refused as refused:
            status = 403 if refused.reason == "mcp_disabled" else 401
            response = JSONResponse(
                {"error": refused.reason, "message": _REFUSED.get(refused.reason, "")},
                status_code=status,
                headers={"WWW-Authenticate": 'Bearer realm="DeepLit"'} if status == 401 else None,
            )
            return await response(scope, receive, send)
        now = time.monotonic()
        recent = self.calls[token.id]
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= CALLS_PER_MINUTE:
            response = JSONResponse({"error": "rate_limited", "message": "Too many calls; wait a minute."}, 429,
                                    headers={"Retry-After": "60"})
            return await response(scope, receive, send)
        recent.append(now)
        scope.setdefault("state", {})["litstorm_token_id"] = token.id
        await self.app(scope, receive, send)


_REFUSED = {
    "no_token": "Send an API token as 'Authorization: Bearer dlk_…'. Make one in DeepLit under Connections.",
    "bad_token": "That token is not valid: unknown, expired or revoked.",
    "mcp_disabled": "An Administrator has switched DeepLit's MCP server off.",
}


async def _caller(ctx, scope=None):
    """The calling token's User and token, fresh from the database."""
    request = ctx.request_context.request
    token_id = getattr(getattr(request, "state", None), "litstorm_token_id", None)
    if token_id is None:
        raise ToolError("Not signed in with a token.")

    def load(session):
        token = session.get(ApiToken, token_id)
        user = session.get(User, token.user_id) if token else None
        if token is None or user is None or tokens.state(token) != "live" or not user.is_active:
            raise ToolError("That token is no longer valid.")
        return user, token

    user, token = await deps.with_session(load)
    if scope:
        try:
            tokens.require(token, scope)
        except tokens.Refused as refused:
            raise ToolError(f"This token may not do that: it lacks the '{scope}' scope.") from refused
    return user, token


# --- what the tools say about a Run --------------------------------------------------


def _web_url(user, run_id):
    if user.kind == INTEGRATION:
        return None  # no one signs in as it; an Administrator reads it on the web
    return f"{settings.get().public_url.rstrip('/')}/runs/{run_id}"


def _progress(run):
    stages = ENGINES.get(run.engine, {}).get("stages", ())
    if run.status in FINAL:
        return len(stages) + 1, len(stages) + 1
    if run.stage in stages:
        return stages.index(run.stage) + 1, len(stages) + 1
    if run.stage == "normalize":  # every engine's last step, after its own
        return len(stages), len(stages) + 1
    return 0, len(stages) + 1


def _run_facts(session, user, run_id):
    run = deps.own(session, Run, run_id, user)
    facts = {
        "id": str(run.id),
        "topic": run.topic,
        "mode": ENGINES.get(run.engine, {}).get("label", run.engine),
        "depth": (run.config or {}).get("depth", "standard"),
        "language": run.language,
        "status": run.status,
        "stage": run.stage,
        "title": run.report_title,
        "sources": run.source_count,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    if run.reason and run.status != "succeeded":
        facts["reason"] = run.reason
        facts["message"] = run.message
        facts["quota_refunded"] = run.quota_refunded
    url = _web_url(user, run.id)
    if url:
        facts["web_url"] = url
    if run.status == "succeeded":
        facts["next"] = "Finished. Call research_report with this id to read the report."
    elif run.status in FINAL:
        facts["next"] = "It ended without a report; research_start can try again."
    elif run.status == "needs_selection":
        facts["next"] = "Its model or source was switched off; its owner must choose again in the web app."
    else:
        facts["next"] = "Still working. Call research_status with this id to keep following it."
    return run, facts


async def _follow(ctx, user, run_id, seconds):
    """The Run's facts, after following it for up to `seconds`, telling its
    progress as its stage changes."""
    deadline = time.monotonic() + max(0, min(seconds, MAX_WAIT))
    key = notify.runs.subscribe(run_id)
    told = None
    try:
        while True:
            run, facts = await deps.with_session(lambda s: _run_facts(s, user, run_id))
            step, total = _progress(run)
            if (run.status, run.stage) != told:
                told = (run.status, run.stage)
                await ctx.report_progress(step, total, f"{run.status}" + (f": {run.stage}" if run.stage else ""))
            left = deadline - time.monotonic()
            if run.status in FINAL or left <= 0:
                return facts
            await notify.woken(key, min(left, 10))
    finally:
        notify.runs.unsubscribe(run_id, key)


def _repeat_of(session, user, token, topic, mode, depth, language, provider_ids, model_id):
    """The Run this token started for the very same request within REPEAT_WINDOW,
    unless it ended without a report; else None."""
    from datetime import timedelta

    since = datetime.now(UTC) - timedelta(seconds=REPEAT_WINDOW)
    query = (
        select(Run)
        .where(
            Run.owner_id == user.id, Run.via_token_id == token.id, Run.turn.is_(None),
            Run.topic == topic.strip(), Run.engine == mode, Run.language == language,
            Run.queued_at >= since, Run.status.not_in(("failed", "cancelled", "interrupted")),
        )
        .order_by(Run.queued_at.desc())
    )
    for run in session.scalars(query):
        if (run.config or {}).get("depth", "standard") != depth:
            continue
        if provider_ids and run.search_provider_id != provider_ids[0]:
            continue
        if model_id and run.llm_model_id != model_id:
            continue
        return run
    return None


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except ValueError as error:
        raise ToolError("That is not a research id.") from error


def _pick_named(session, model, wanted, what):
    """A switched-on row by its id or label (any case), or a ToolError."""
    rows = list(session.scalars(select(model).where(model.enabled)))
    for row in rows:
        if str(row.id) == wanted or row.label.casefold() == wanted.strip().casefold():
            return row
    names = ", ".join(r.label for r in rows)
    raise ToolError(f"No {what} named '{wanted}'. Choose from: {names}.")


# --- reports -----------------------------------------------------------------------------


def _outline(report):
    lines = [f"# {report['title']}"]

    def walk(sections, prefix):
        for i, s in enumerate(sections, 1):
            number = f"{prefix}{i}"
            lines.append(f"{'  ' * number.count('.')}{number}. {s['heading']}")
            walk(s["children"], f"{number}.")

    walk(report["sections"], "")
    lines.append("")
    lines.append(f"{len(report['sources'])} sources. Ask for part 'section:N' to read section N, or 'full'.")
    return "\n".join(lines)


def _section(report, wanted):
    from litstorm.render import markdown

    sections = report["sections"]
    index = int(wanted) - 1 if wanted.isdigit() else next(
        (i for i, s in enumerate(sections) if s["heading"].casefold() == wanted.casefold()), -1
    )
    if not 0 <= index < len(sections):
        raise ToolError(f"No section '{wanted}'. The report has sections 1 to {len(sections)}; see part 'outline'.")
    part = sections[index]
    out = []
    markdown._sections([part], 2, out)
    text = "\n\n".join(out)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    sources = [f"{s['id']}. [{s['title']}]({s['url']})" for s in report["sources"] if s["id"] in cited]
    return text + ("\n\n## Sources\n\n" + "\n".join(sources) if sources else "")


# --- the canvas (MCP App) -----------------------------------------------------------------------


@cache
def _canvas_html():
    return (Path(__file__).parent / "mcp_canvas.html").read_text(encoding="utf-8")


def _events(session, user, run_id, after):
    """What the canvas draws: the Run's facts and its events after `after`."""
    from litstorm.api import research

    run, facts = _run_facts(session, user, run_id)  # the owner's only, as every tool
    detail, last, more = research._run_detail(session, run_id, user, after, record=False)
    facts["engine"] = run.engine
    return {
        "run": facts,
        "events": [e.model_dump(mode="json") for e in detail.events],
        "after": last,
        "more": more,
        "final": run.status in FINAL and not more,
    }


# --- the server -----------------------------------------------------------------------------


def build():
    """A FastMCP with DeepLit's tools: (the gated ASGI app, its session manager)."""
    server = FastMCP(
        "DeepLit",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        streamable_http_path=PATH,
        # A token in a header, never a cookie: a page on another site cannot
        # use it, so the DNS-rebinding guard (for local servers) has nothing
        # to protect, and it would refuse the public host name.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @server.tool()
    async def research_options(ctx: Context) -> dict:
        """What this account can start: research modes, depths (with their usual minutes), sources,
        models, report languages, and the research quota left this month."""
        from litstorm.api import research

        user, _ = await _caller(ctx)

        def read(session):
            o = research.options(user=user, session=session).model_dump()
            if user.allowed_engines is not None:
                o["engines"] = [e for e in o["engines"] if e["id"] in user.allowed_engines]
            # Discussions talk in turns; not offered through MCP yet.
            o["engines"] = [e for e in o["engines"] if e["id"] != "co-storm"]
            u = quota.usage(session, user)
            o["quota"] = {"month": u.month, "limit": u.limit, "used": u.used, "remaining": u.remaining}
            return o

        return await deps.with_session(read)

    @server.tool(meta=ON_CANVAS)
    async def research_start(
        ctx: Context,
        topic: Annotated[str, Field(description="What to research, as a question or a subject (3 to 500 characters).")],
        language: Annotated[Literal["en", "th"], Field(description="The report's language: en or th.")] = "en",
        mode: Annotated[
            str,
            Field(description="Research mode: storm (Wikipedia-style article from many perspectives, the default), "
                              "deep (Deep Research, follows leads breadth and depth), or agent (Agent Research, "
                              "iterates on knowledge gaps). See research_options."),
        ] = "storm",
        depth: Annotated[Literal["fast", "standard", "deep"], Field(description="How thorough, and so how long.")] = "standard",
        sources: Annotated[
            list[str] | None,
            Field(description="Up to three sources by name or id (see research_options), the first the main one. "
                              "Omit for the server's default."),
        ] = None,
        model: Annotated[str | None, Field(description="A model by name or id; omit for the default.")] = None,
        wait_seconds: Annotated[
            int,
            Field(description="How long to follow it before returning: 0 to 45 seconds, 20 by default. Stay under your "
                              "client's own limit for a tool call.", ge=0, le=MAX_WAIT),
        ] = WAIT,
    ) -> dict:
        """Start researching a topic. Returns when the research finishes or after wait_seconds, whichever
        comes first, with its id and status; then use research_status to keep following it and
        research_report to read the finished report. Uses one unit of the account's research quota."""
        from litstorm.api import research

        user, token = await _caller(ctx, "research")
        if mode == "co-storm":
            raise ToolError("Discussions (Co-STORM) are not available through MCP yet; use the web app.")

        def start(session):
            provider_ids = [_pick_named(session, SearchProvider, s, "source").id for s in (sources or [])]
            model_id = _pick_named(session, LlmModel, model, "model").id if model else None
            again = _repeat_of(session, user, token, topic, mode, depth, language, provider_ids, model_id)
            if again is not None:
                return again.id, True
            body = research.NewSessionIn(
                topic=topic, language=language, engine=mode, depth=depth,
                llm_model_id=model_id,
                search_provider_id=provider_ids[0] if provider_ids else None,
                extra_search_provider_ids=provider_ids[1:],
            )
            try:
                made = research._start_session(session, user, None, body)
            except HTTPException as error:
                _fail(error)
            run = session.get(Run, uuid.UUID(made.runs[0].id))
            run.via_token_id = token.id
            session.commit()
            return run.id, False

        try:
            run_id, repeated = await deps.with_session(start)
        except ValueError as error:  # the body's own checks: a topic too short, too long
            raise ToolError(str(error).splitlines()[0]) from error
        facts = await _follow(ctx, user, run_id, wait_seconds)
        if repeated:
            facts["repeated"] = ("This token started the same research a moment ago; this is that run, "
                                 "not a new one, and no quota was used. Follow it with research_status.")
        return facts

    @server.tool(meta=ON_CANVAS)
    async def research_status(
        ctx: Context,
        id: Annotated[str, Field(description="The research id from research_start or research_list.")],
        wait_seconds: Annotated[
            int,
            Field(description="How long to follow it before returning: 0 to 45 seconds, 20 by default. Stay under your "
                              "client's own limit for a tool call.", ge=0, le=MAX_WAIT),
        ] = WAIT,
    ) -> dict:
        """Follow a research run: returns when it finishes or after wait_seconds, with its status, stage,
        sources found so far, and what to do next."""
        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            await deps.with_session(lambda s: deps.own(s, Run, run_id, user))
        except HTTPException as error:
            _fail(error)
        return await _follow(ctx, user, run_id, wait_seconds)

    @server.tool()
    async def research_report(
        ctx: Context,
        id: Annotated[str, Field(description="The research id.")],
        part: Annotated[
            str,
            Field(description="'full' (the whole report in Markdown with numbered citations and its sources), "
                              "'outline' (the sections, numbered), or 'section:N' for section N alone with the "
                              "sources it cites. Use outline then sections for long reports."),
        ] = "full",
    ) -> str:
        """Read a finished research report, in Markdown. Every [n] cites source n, listed at the end."""
        from litstorm.api import research
        from litstorm.render import markdown

        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)

        def read(session):
            run = deps.own(session, Run, run_id, user)
            if run.status != "succeeded":
                raise HTTPException(409, "no_report")
            return research._report(session, run_id, user, "mcp")[1]

        try:
            report = await deps.with_session(read)
        except HTTPException as error:
            _fail(error)
        if part == "outline":
            return _outline(report)
        if part.startswith("section:"):
            return _section(report, part.split(":", 1)[1].strip())
        if part != "full":
            raise ToolError("part is 'full', 'outline', or 'section:N'.")
        return markdown.render(report)

    @server.tool()
    async def research_export(
        ctx: Context,
        id: Annotated[str, Field(description="The research id.")],
        format: Annotated[
            Literal["interactive", "html", "md", "pdf"],
            Field(description="'interactive' (the default: one HTML file with the report's charts and figures, "
                              "opens offline), 'html' (the plain report page), 'md' (Markdown) or 'pdf'."),
        ] = "interactive",
    ) -> dict:
        """A download link for a finished report as a file, good for 15 minutes and for that one file: fetch it
        with a plain GET, no sign-in (to save it beside your work, or for a person to open). The file itself
        does not pass through this call."""
        from litstorm import exports
        from litstorm.api import research

        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)

        def read(session):
            run = deps.own(session, Run, run_id, user)
            if run.status != "succeeded":
                raise HTTPException(409, "no_report")
            return research._report(session, run_id, user, "export")[1]

        try:
            report = await deps.with_session(read)
        except HTTPException as error:
            _fail(error)
        token, expires = exports.sign(run_id, user.id, format)
        filename = research._filename(report, exports.EXTENSIONS[format])
        url = f"{settings.get().export_url}/api/exports/{token}"
        return {
            "id": str(run_id),
            "format": format,
            "filename": filename,
            "url": url,
            "expires_at": datetime.fromtimestamp(expires, UTC).isoformat(),
            "next": f"Download it within {exports.LIFETIME // 60} minutes, e.g. "
                    f"curl -fsSL -o '{filename}' '{url}'. The link opens this report without signing in: "
                    "keep it to whoever should read it.",
        }

    @server.tool()
    async def research_list(
        ctx: Context,
        limit: Annotated[int, Field(description="How many, newest first (1 to 50).", ge=1, le=50)] = 10,
    ) -> list[dict]:
        """This account's research, newest first: id, topic, mode, status, report title, sources."""
        user, _ = await _caller(ctx, "read")

        def read(session):
            runs = session.scalars(
                select(Run)
                .where(Run.owner_id == user.id, Run.trashed_at.is_(None), Run.turn.is_(None))
                .order_by(Run.queued_at.desc())
                .limit(limit)
            )
            return [
                {
                    "id": str(r.id), "topic": r.topic, "mode": ENGINES.get(r.engine, {}).get("label", r.engine),
                    "status": r.status, "title": r.report_title, "sources": r.source_count,
                    "queued_at": r.queued_at.isoformat(),
                }
                for r in runs
            ]

        return await deps.with_session(read)

    @server.tool()
    async def research_cancel(
        ctx: Context,
        id: Annotated[str, Field(description="The research id.")],
    ) -> dict:
        """Stop a research run. One still waiting stops at once and its quota comes back; one running is
        asked to stop and ends shortly."""
        from litstorm.api import research

        user, _ = await _caller(ctx, "research")
        run_id = _uuid(id)

        def cancel(session):
            try:
                research.cancel_run(run_id, user=user, session=session)
            except HTTPException as error:
                _fail(error)
            return _run_facts(session, user, run_id)[1]

        return await deps.with_session(cancel)

    @server.tool(meta={"ui": {"resourceUri": CANVAS_URI, "visibility": ["app"]}})
    async def research_events(
        ctx: Context,
        id: Annotated[str, Field(description="The research id.")],
        after: Annotated[int, Field(description="The last event id already read; 0 for all.", ge=0)] = 0,
    ) -> dict:
        """The research canvas's feed, called by the canvas itself: a run's status and its events
        (stages, perspectives, research tree, agent steps, pages read) after the given event id."""
        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            return await deps.with_session(lambda s: _events(s, user, run_id, after))
        except HTTPException as error:
            _fail(error)

    @server.resource(
        CANVAS_URI, name="research-canvas", title="DeepLit research canvas", mime_type=APP_MIME,
        description="A live canvas of the agents a DeepLit research run spawns.",
        meta={"ui": {"prefersBorder": True}},
    )
    def research_canvas() -> str:
        return _canvas_html()

    # A docstring's line breaks and indent are for this file, not for the
    # model reading the description.
    for tool in server._tool_manager.list_tools():
        tool.description = " ".join(tool.description.split())

    # The protocol's endpoint itself, to sit on the API's own router at PATH
    # (a mounted sub-app would answer /api/mcp with a redirect to /api/mcp/).
    endpoint = next(r.endpoint for r in server.streamable_http_app().routes if getattr(r, "path", None) == PATH)
    return TokenGate(endpoint), server.session_manager
