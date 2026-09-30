"""The HTTP API. Run with `uvicorn litstorm.api:app`."""

from fastapi import FastAPI

from litstorm.api import admin, auth, discussions, research


def create_app():
    app = FastAPI(title="lit-storm", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(research.router)
    app.include_router(discussions.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
