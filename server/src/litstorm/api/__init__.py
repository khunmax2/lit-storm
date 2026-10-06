"""The HTTP API. Run with `uvicorn litstorm.api:app`."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Route

from litstorm.api import admin, auth, discussions, mcp, research, support, tokens


def create_app():
    gate, sessions = mcp.build()

    @asynccontextmanager
    async def lifespan(app):
        # The MCP server's task group, for the requests it answers.
        async with sessions.run():
            yield

    app = FastAPI(title="DeepLit", version="0.1.0", lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(research.router)
    app.include_router(discussions.router)
    app.include_router(support.router)
    app.include_router(tokens.router)
    app.include_router(tokens.admin)
    app.router.routes.append(Route(mcp.PATH, endpoint=gate))

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
