"""The HTTP API. Run with `uvicorn litstorm.api:app`."""

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Route

from litstorm.api import admin, auth, discussions, mcp, medical, research, support, tokens


def create_app():
    servers = mcp.build_all()

    @asynccontextmanager
    async def lifespan(app):
        # The MCP servers' task groups, for the requests they answer.
        async with AsyncExitStack() as stack:
            for _, _, sessions in servers:
                await stack.enter_async_context(sessions.run())
            yield

    app = FastAPI(title="DeepLit", version="0.1.0", lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(research.router)
    app.include_router(discussions.router)
    app.include_router(support.router)
    app.include_router(tokens.router)
    app.include_router(tokens.admin)
    app.include_router(medical.router)
    app.include_router(medical.admin)
    for path, gate, _ in servers:
        app.router.routes.append(Route(path, endpoint=gate))

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
