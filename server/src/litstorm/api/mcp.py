"""DeepLit's MCP server: research as tools for AI clients and other systems
(docs/adr/0009).

Streamable HTTP at /api/mcp, stateless: every request stands alone, so the
API's processes need no shared session, and a Run's state is in Postgres as
ever. Beside it, one server per research mode (/api/mcp/storm, /deep,
/agent): the same tools named for that mode, which start only that mode and
see only its Runs, so a client picks a server by what it can do. The official SDK's FastMCP does the protocol; `TokenGate` in front of
it admits a request only with a live API token (litstorm.tokens), and every
tool reads who is calling from that request.

The tools call what the web app's endpoints call, so a Run started here
meets the same quota, queue, modes and Search Providers. A Run takes minutes
and a client gives a tool call about a minute: research_start and
research_status follow the Run for up to WAIT seconds, telling progress as
they go, and then hand back its id to ask again.
"""

import asyncio
import json
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

from litstorm import modes, notify, quota, settings, tokens
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
APP_MIME = "text/html;profile=mcp-app"

# The modes with a server of their own, and what each is good for: what a
# client reads to choose one (times and sources measured on this stack's
# Runs, 2026-10-15, with the default model). Co-STORM talks in turns: not here.
MODES = ("storm", "deep", "agent")
ABOUT = {
    "storm": (
        "STORM writes a Wikipedia-style article. It imagines several expert perspectives on the topic, "
        "interviews a grounded expert from each, then outlines, writes section by section and polishes. "
        "Best for an overview of a subject: background, history, positions, current state, with broad coverage "
        "and many sources (about 15 at depth fast, 30 standard, 80 deep). Every sentence cites the passage it "
        "came from. Less suited to one narrow question. Usually about 1 minute (fast), 1 to 2 (standard), "
        "2 to 3 (deep). Works well in Thai."
    ),
    "deep": (
        "Deep Research answers a focused question by following leads. It writes several search queries, learns "
        "from the results, then searches deeper on what it learned; the depth level sets how wide and how deep. "
        "Best for a specific question, a comparison or the latest on something, quickly and cheaply: the "
        "fastest and cheapest mode. It works from the search results' text and does not open pages, so it "
        "cites fewer sources (about 3 at depth fast, 15 standard, 20 deep). Each finding keeps the passage it "
        "came from. Usually under 1 minute (fast), about 1 (standard), 2 to 3 (deep). Works in Thai and "
        "English; depth fast sends only two queries, so a narrow topic can come back thin: standard is safer."
    ),
    "agent": (
        "Agent Research runs a loop of agents. It notes what it knows, names the biggest knowledge gap, picks "
        "search or crawl tasks to fill it, runs them, and repeats until the gap agent judges the research "
        "complete. At depth deep a planner first splits the topic into sections, researched at once. Best "
        "for a complex or many-sided question that needs whole pages read (it crawls websites) and judgement "
        "about what is still missing. Slower and costlier than the others. Its report cites sources but keeps "
        "no source passages, so it has no evidence quotes or number charts. Usually about 1 minute (fast), "
        "2 (standard), 2 to 5 (deep)."
    ),
}
# What the combined server's `mode` parameter says of each, in a line.
LINE = {
    "storm": "storm (the default): a Wikipedia-style overview article from many perspectives, many sources",
    "deep": "deep: Deep Research, a focused question answered fast and cheaply by following leads",
    "agent": "agent: Agent Research, agents loop on knowledge gaps and read whole pages; slower, for complex questions",
}


def path_for(mode=None):
    return PATH if mode is None else f"{PATH}/{mode}"


def canvas_uri(mode=None):
    return f"ui://deeplit/{mode or 'research'}-canvas.html"


def _instructions(mode, p):
    if mode is None:
        about = ("DeepLit researches a topic on the web and in academic sources, then writes a report whose every "
                 "claim cites its sources. It has three modes, chosen with the mode parameter of "
                 f"{p}_start: {'; '.join(LINE.values())}. DeepLit also offers one server per mode.")
    else:
        others = ", ".join(f"deeplit-{m} ({ENGINES[m]['label']})" for m in MODES if m != mode)
        about = (f"This is DeepLit's {ENGINES[mode]['label']} server: every research it starts is "
                 f"{ENGINES[mode]['label']}, and it sees only that mode's research. {ABOUT[mode]} "
                 f"DeepLit's other servers do the other modes: {others}.")
    return (
        f"{about} Start research with {p}_start; if it is not finished when the call returns, follow it with "
        f"{p}_status (each call follows it for 20 seconds by default, up to 45), then read it with {p}_report. "
        'Reports can be written in English ("en") or Thai ("th"). '
        f"{p}_export gives a short-lived download link for a finished report as a file (one HTML page with "
        f"its charts, plain HTML, Markdown or PDF). {p}_options lists the depths, sources and the quota left. "
        f"Clients that show MCP Apps draw {p}_start and {p}_status as a live canvas of the research agents."
    )

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


def _fail(error, p="research"):
    detail = getattr(error, "detail", None) or str(error)
    raise ToolError(_MEANING.get(detail, f"Refused: {detail}").replace("research_options", f"{p}_options")) from error


# --- who is calling ---------------------------------------------------------------


# Calls per token in the last minute, across every server in this process.
_CALLS = defaultdict(deque)


class TokenGate:
    """Admits a request to the MCP app only with a live token, and at most
    CALLS_PER_MINUTE a minute for it; puts the token's id on the request for
    the tools. A mode's server also wants the mode offered and the account
    allowed it. Anything else is answered here, before the protocol."""

    def __init__(self, app, mode=None):
        self.app = app
        self.mode = mode

    def _admit(self, session, header):
        user, token = tokens.authenticate(session, header)
        if self.mode is not None:
            if self.mode not in modes.offered(session):
                raise tokens.Refused("mode_disabled")
            if user.allowed_engines is not None and self.mode not in user.allowed_engines:
                raise tokens.Refused("mode_not_allowed")
        return token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope.get("headers") or []).get(b"authorization", b"").decode("latin-1")
        try:
            token = await deps.with_session(lambda s: self._admit(s, header))
        except tokens.Refused as refused:
            status = 401 if refused.reason in ("no_token", "bad_token") else 403
            label = ENGINES[self.mode]["label"] if self.mode else ""
            response = JSONResponse(
                {"error": refused.reason, "message": _REFUSED.get(refused.reason, "").format(label=label)},
                status_code=status,
                headers={"WWW-Authenticate": 'Bearer realm="DeepLit"'} if status == 401 else None,
            )
            return await response(scope, receive, send)
        now = time.monotonic()
        recent = _CALLS[token.id]
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
    "mode_disabled": "An Administrator has switched {label} off on this DeepLit; use another mode's server.",
    "mode_not_allowed": "This account may not use {label}; use the server of a mode it may use, or ask an Administrator.",
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


def _own(session, user, run_id, mode=None):
    """The caller's Run; on a mode's server, only one of that mode. Another
    mode's Run is named as such, with the server that reads it."""
    run = deps.own(session, Run, run_id, user)
    if mode is not None and run.engine != mode:
        label = ENGINES.get(run.engine, {}).get("label", run.engine)
        where = (f"DeepLit's {label} server (deeplit-{run.engine}, {settings.get().public_url.rstrip('/')}"
                 f"{path_for(run.engine)}) or " if run.engine in MODES else "")
        article = "an" if label[:1].upper() in "AEIOU" else "a"
        raise ToolError(f"That research is {article} {label} run, and this is DeepLit's {ENGINES[mode]['label']} "
                        f"server: read it through {where}the combined DeepLit server (deeplit).")
    return run


def _run_facts(session, user, run_id, mode=None, p="research"):
    run = _own(session, user, run_id, mode)
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
        facts["next"] = f"Finished. Call {p}_report with this id to read the report."
    elif run.status in FINAL:
        facts["next"] = f"It ended without a report; {p}_start can try again."
    elif run.status == "needs_selection":
        facts["next"] = "Its model or source was switched off; its owner must choose again in the web app."
    else:
        facts["next"] = f"Still working. Call {p}_status with this id to keep following it."
    return run, facts


async def _follow(ctx, user, run_id, seconds, mode=None, p="research"):
    """The Run's facts, after following it for up to `seconds`, telling its
    progress as its stage changes."""
    deadline = time.monotonic() + max(0, min(seconds, MAX_WAIT))
    key = notify.runs.subscribe(run_id)
    told = None
    try:
        while True:
            run, facts = await deps.with_session(lambda s: _run_facts(s, user, run_id, mode, p))
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
def _canvas_html(mode=None):
    """The canvas page for one mode's server, or for the combined one: the
    shared shell (mcp_canvas/base.html) with that mode's scene, or every
    scene, and the names of the server's own tools (docs/adr/0010)."""
    folder = Path(__file__).parent / "mcp_canvas"
    html = (folder / "base.html").read_text(encoding="utf-8")
    p = "research" if mode is None else f"{mode}_research"
    config = {"mode": mode, "events": f"{p}_events", "status": f"{p}_status", "report": f"{p}_report"}
    html = re.sub(r"/\*CONFIG\*/.*?/\*END\*/", lambda _: json.dumps(config), html, count=1)
    scenes = "\n".join(
        f"<script>\n{(folder / f'{m}.js').read_text(encoding='utf-8')}</script>" for m in ((mode,) if mode else MODES)
    )
    return html.replace("<!--SCENES-->", scenes, 1)


def _events(session, user, run_id, after, mode=None, p="research"):
    """What the canvas draws: the Run's facts and its events after `after`."""
    from litstorm.api import research

    run, facts = _run_facts(session, user, run_id, mode, p)  # the owner's only, as every tool
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

Topic = Annotated[str, Field(description="What to research, as a question or a subject (3 to 500 characters).")]
Language = Annotated[Literal["en", "th"], Field(description="The report's language: en or th.")]
Depth = Annotated[Literal["fast", "standard", "deep"], Field(description="How thorough, and so how long.")]
Wait = Annotated[
    int,
    Field(description="How long to follow it before returning: 0 to 45 seconds, 20 by default. Stay under your "
                      "client's own limit for a tool call.", ge=0, le=MAX_WAIT),
]
Model = Annotated[str | None, Field(description="A model by name or id; omit for the default.")]
Id = Annotated[str, Field(description="The research id.")]


def build(mode=None):
    """A FastMCP with DeepLit's tools, for every mode or for `mode` alone:
    (its path, the gated ASGI app, its session manager)."""
    p = "research" if mode is None else f"{mode}_research"  # the tools' names: {p}_start, ...
    label = ENGINES[mode]["label"] if mode else ""
    path = path_for(mode)
    uri = canvas_uri(mode)
    on_canvas = {"ui": {"resourceUri": uri}}
    server = FastMCP(
        f"DeepLit {label}".strip(),
        instructions=" ".join(_instructions(mode, p).split()),
        stateless_http=True,
        streamable_http_path=path,
        # A token in a header, never a cookie: a page on another site cannot
        # use it, so the DNS-rebinding guard (for local servers) has nothing
        # to protect, and it would refuse the public host name.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    Sources = Annotated[
        list[str] | None,
        Field(description=f"Up to three sources by name or id (see {p}_options), the first the main one. "
                          "Omit for the server's default."),
    ]

    @server.tool(
        name=f"{p}_options",
        description=f"What this account can start{'' if mode else ': research modes'}: depths (with their usual "
                    "minutes), sources, models, report languages, and the research quota left this month.",
    )
    async def options(ctx: Context) -> dict:
        from litstorm.api import research

        user, _ = await _caller(ctx)

        def read(session):
            o = research.options(user=user, session=session).model_dump()
            if user.allowed_engines is not None:
                o["engines"] = [e for e in o["engines"] if e["id"] in user.allowed_engines]
            # Discussions talk in turns; not offered through MCP yet.
            o["engines"] = [e for e in o["engines"] if e["id"] != "co-storm" and (mode is None or e["id"] == mode)]
            u = quota.usage(session, user)
            o["quota"] = {"month": u.month, "limit": u.limit, "used": u.used, "remaining": u.remaining}
            return o

        return await deps.with_session(read)

    async def start(ctx, topic, language, engine, depth, sources, model, wait_seconds):
        from litstorm.api import research

        user, token = await _caller(ctx, "research")
        if engine == "co-storm":
            raise ToolError("Discussions (Co-STORM) are not available through MCP yet; use the web app.")

        def begin(session):
            provider_ids = [_pick_named(session, SearchProvider, s, "source").id for s in (sources or [])]
            model_id = _pick_named(session, LlmModel, model, "model").id if model else None
            again = _repeat_of(session, user, token, topic, engine, depth, language, provider_ids, model_id)
            if again is not None:
                return again.id, True
            body = research.NewSessionIn(
                topic=topic, language=language, engine=engine, depth=depth,
                llm_model_id=model_id,
                search_provider_id=provider_ids[0] if provider_ids else None,
                extra_search_provider_ids=provider_ids[1:],
            )
            try:
                made = research._start_session(session, user, None, body)
            except HTTPException as error:
                _fail(error, p)
            run = session.get(Run, uuid.UUID(made.runs[0].id))
            run.via_token_id = token.id
            session.commit()
            return run.id, False

        try:
            run_id, repeated = await deps.with_session(begin)
        except ValueError as error:  # the body's own checks: a topic too short, too long
            raise ToolError(str(error).splitlines()[0]) from error
        facts = await _follow(ctx, user, run_id, wait_seconds, mode, p)
        if repeated:
            facts["repeated"] = ("This token started the same research a moment ago; this is that run, "
                                 f"not a new one, and no quota was used. Follow it with {p}_status.")
        return facts

    started = (
        f"Returns when the research finishes or after wait_seconds, whichever comes first, with its id and "
        f"status; then use {p}_status to keep following it and {p}_report to read the finished report. "
        "Uses one unit of the account's research quota."
    )
    if mode is None:

        @server.tool(name=f"{p}_start", description=f"Start researching a topic. {started}", meta=on_canvas)
        async def research_start(
            ctx: Context,
            topic: Topic,
            language: Language = "en",
            mode: Annotated[
                str, Field(description=f"Research mode: {'; '.join(LINE.values())}. See {p}_options."),
            ] = "storm",
            depth: Depth = "standard",
            sources: Sources = None,
            model: Model = None,
            wait_seconds: Wait = WAIT,
        ) -> dict:
            return await start(ctx, topic, language, mode, depth, sources, model, wait_seconds)

    else:

        @server.tool(name=f"{p}_start", description=f"Start {label} on a topic. {ABOUT[mode]} {started}", meta=on_canvas)
        async def mode_start(
            ctx: Context,
            topic: Topic,
            language: Language = "en",
            depth: Depth = "standard",
            sources: Sources = None,
            model: Model = None,
            wait_seconds: Wait = WAIT,
        ) -> dict:
            return await start(ctx, topic, language, mode, depth, sources, model, wait_seconds)

    @server.tool(
        name=f"{p}_status",
        description="Follow a research run: returns when it finishes or after wait_seconds, with its status, "
                    "stage, sources found so far, and what to do next.",
        meta=on_canvas,
    )
    async def status(
        ctx: Context,
        id: Annotated[str, Field(description=f"The research id from {p}_start or {p}_list.")],
        wait_seconds: Wait = WAIT,
    ) -> dict:
        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            await deps.with_session(lambda s: _own(s, user, run_id, mode))
        except HTTPException as error:
            _fail(error, p)
        return await _follow(ctx, user, run_id, wait_seconds, mode, p)

    def finished(session, user, run_id, how):
        from litstorm.api import research

        run = _own(session, user, run_id, mode)
        if run.status != "succeeded":
            raise HTTPException(409, "no_report")
        return research._report(session, run_id, user, how)[1]

    @server.tool(
        name=f"{p}_report",
        description="Read a finished research report, in Markdown. Every [n] cites source n, listed at the end.",
    )
    async def report(
        ctx: Context,
        id: Id,
        part: Annotated[
            str,
            Field(description="'full' (the whole report in Markdown with numbered citations and its sources), "
                              "'outline' (the sections, numbered), or 'section:N' for section N alone with the "
                              "sources it cites. Use outline then sections for long reports."),
        ] = "full",
    ) -> str:
        from litstorm.render import markdown

        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            found = await deps.with_session(lambda s: finished(s, user, run_id, "mcp"))
        except HTTPException as error:
            _fail(error, p)
        if part == "outline":
            return _outline(found)
        if part.startswith("section:"):
            return _section(found, part.split(":", 1)[1].strip())
        if part != "full":
            raise ToolError("part is 'full', 'outline', or 'section:N'.")
        return markdown.render(found)

    @server.tool(
        name=f"{p}_export",
        description="A download link for a finished report as a file, good for 15 minutes and for that one file: "
                    "fetch it with a plain GET, no sign-in (to save it beside your work, or for a person to open). "
                    "The file itself does not pass through this call.",
    )
    async def export(
        ctx: Context,
        id: Id,
        format: Annotated[
            Literal["interactive", "html", "md", "pdf", "observatory"],
            Field(description="'interactive' (the default: one HTML file with the report's charts and figures, "
                              "opens offline), 'html' (the plain report page), 'md' (Markdown), 'pdf', or "
                              "'observatory' (one HTML file that replays the research: its agents being spawned, "
                              "what they read, then each cited sentence lit up against its source's passage)."),
        ] = "interactive",
    ) -> dict:
        from litstorm import exports
        from litstorm.api import research

        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            found = await deps.with_session(lambda s: finished(s, user, run_id, "export"))
        except HTTPException as error:
            _fail(error, p)
        token, expires = exports.sign(run_id, user.id, format)
        filename = research._filename(found, exports.EXTENSIONS[format])
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

    @server.tool(
        name=f"{p}_list",
        description=f"This account's {label + ' ' if mode else ''}research, newest first: id, topic, mode, "
                    "status, report title, sources.",
    )
    async def listed(
        ctx: Context,
        limit: Annotated[int, Field(description="How many, newest first (1 to 50).", ge=1, le=50)] = 10,
    ) -> list[dict]:
        user, _ = await _caller(ctx, "read")

        def read(session):
            query = select(Run).where(Run.owner_id == user.id, Run.trashed_at.is_(None), Run.turn.is_(None))
            if mode is not None:
                query = query.where(Run.engine == mode)
            runs = session.scalars(query.order_by(Run.queued_at.desc()).limit(limit))
            return [
                {
                    "id": str(r.id), "topic": r.topic, "mode": ENGINES.get(r.engine, {}).get("label", r.engine),
                    "status": r.status, "title": r.report_title, "sources": r.source_count,
                    "queued_at": r.queued_at.isoformat(),
                }
                for r in runs
            ]

        return await deps.with_session(read)

    @server.tool(
        name=f"{p}_cancel",
        description="Stop a research run. One still waiting stops at once and its quota comes back; one running "
                    "is asked to stop and ends shortly.",
    )
    async def cancel(ctx: Context, id: Id) -> dict:
        from litstorm.api import research

        user, _ = await _caller(ctx, "research")
        run_id = _uuid(id)

        def stop(session):
            try:
                _own(session, user, run_id, mode)
                research.cancel_run(run_id, user=user, session=session)
            except HTTPException as error:
                _fail(error, p)
            return _run_facts(session, user, run_id, mode, p)[1]

        return await deps.with_session(stop)

    @server.tool(
        name=f"{p}_events",
        description="The research canvas's feed, called by the canvas itself: a run's status and its events "
                    "(stages, perspectives, research tree, agent steps, pages read) after the given event id.",
        meta={"ui": {"resourceUri": uri, "visibility": ["app"]}},
    )
    async def events(
        ctx: Context,
        id: Id,
        after: Annotated[int, Field(description="The last event id already read; 0 for all.", ge=0)] = 0,
    ) -> dict:
        user, _ = await _caller(ctx, "read")
        run_id = _uuid(id)
        try:
            return await deps.with_session(lambda s: _events(s, user, run_id, after, mode, p))
        except HTTPException as error:
            _fail(error, p)

    @server.resource(
        uri, name=f"{mode or 'research'}-canvas", title=f"DeepLit {label or 'research'} canvas".replace("  ", " "),
        mime_type=APP_MIME,
        description=f"A live canvas of the agents a DeepLit {label + ' ' if mode else ''}research run spawns.",
        meta={"ui": {"prefersBorder": True}},
    )
    def canvas() -> str:
        return _canvas_html(mode)

    # A description's line breaks and indent are for this file, not for the
    # model reading it.
    for tool in server._tool_manager.list_tools():
        tool.description = " ".join(tool.description.split())

    # The protocol's endpoint itself, to sit on the API's own router at its
    # path (a mounted sub-app would answer it with a redirect to path + "/").
    endpoint = next(r.endpoint for r in server.streamable_http_app().routes if getattr(r, "path", None) == path)
    return path, TokenGate(endpoint, mode), server.session_manager


def build_all():
    """The combined server and one per mode: [(path, gated app, session manager)]."""
    return [build(m) for m in (None, *MODES)]
