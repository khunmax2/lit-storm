"""DeepLit's API on a throwaway Postgres, with Runs to draw on the research
canvas: no LLM, no worker, nothing from the real stack. For looking at the
MCP App with tests/mcp_app_harness.py, end to end through the real MCP server.

    uv run python tests/canvas_demo_server.py events1.json [events2.json ...]

Each file is one Run's events, as exported from a stack (read only):

    select json_build_object(
      'run', (select json_build_object('topic', topic, 'engine', engine, 'language', language,
              'depth', coalesce(config->>'depth', 'standard')) from runs where id = :id),
      'events', (select json_agg(json_build_object('type', type, 'data', data) order by id)
                 from run_events where run_id = :id))

The first file's Run is replayed live (an event every LIVE_STEP seconds, then
succeeded) so the canvas shows agents spawning; the others are finished Runs.
Prints the API's MCP URL, a token, and each Run's id; serves until stopped.
"""

import json
import os
import sys
import tempfile
import threading
import time

LIVE_STEP = 0.8
LIVE_DELAY = float(os.environ.get("LIVE_DELAY", "20"))  # seconds before the live Run begins
PORT = 8898


def main(paths):
    from cryptography.fernet import Fernet
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg, tempfile.TemporaryDirectory() as tmp:
        code = os.path.join(tmp, "code")
        with open(code, "w") as f:
            f.write("demo-setup-code\n")
        os.environ.update({
            "LITSTORM_DATABASE_URL": pg.get_connection_url(),
            "LITSTORM_DATA_DIR": os.path.join(tmp, "data"),
            "LITSTORM_SECRET_KEY": Fernet.generate_key().decode(),
            "LITSTORM_PUBLIC_URL": f"http://127.0.0.1:{PORT}",
            "LITSTORM_BOOTSTRAP_CODE_FILE": code,
        })
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")

        from conftest import Browser
        from fastapi.testclient import TestClient

        from litstorm import db
        from litstorm.api import create_app
        from litstorm.db.models import Run, RunEvent

        admin = Browser(TestClient(create_app()))
        assert admin.post("/api/setup", json={"code": "demo-setup-code", "email": "admin@example.org",
                                              "name": "Admin", "password": "demo password 1"}).status_code == 200
        admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-demo-0000"})
        admin.post("/api/admin/llm-models", json={"label": "Demo", "provider": "openrouter", "model": "demo/x",
                                                  "is_default": True})
        admin.post("/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True})
        token = admin.post("/api/me/tokens", json={"name": "canvas", "scopes": ["read"], "days": 30}).json()["token"]

        runs = []
        for i, path in enumerate(paths):
            with open(path, encoding="utf-8") as f:
                sample = json.load(f)
            facts = sample["run"]
            made = admin.post("/api/sessions", json={"topic": facts["topic"][:500], "language": facts["language"]})
            run_id = made.json()["runs"][0]["id"]
            events = [e for e in sample["events"] if e["type"] in ("stage", "note", "usage")]
            with db.sessions()() as s:
                run = s.get(Run, run_id)
                run.engine = facts["engine"]
                run.config = {**(run.config or {}), "depth": facts.get("depth", "standard")}
                run.status = "running" if i == 0 else "succeeded"
                if i:
                    for e in events:
                        s.add(RunEvent(run_id=run.id, type=e["type"], data=e["data"]))
                s.commit()
            runs.append((run_id, facts, events))
            print(f"run {run_id}  {facts['engine']:<6} {facts.get('depth', ''):<8} {'LIVE' if i == 0 else 'done'}  "
                  f"{facts['topic'][:60]}")

        def live(run_id, events):
            time.sleep(LIVE_DELAY)  # time to open the harness
            for e in events:
                with db.sessions()() as s:
                    s.add(RunEvent(run_id=run_id, type=e["type"], data=e["data"]))
                    if e["type"] == "stage":
                        s.get(Run, run_id).stage = e["data"]["stage"]
                    s.commit()
                time.sleep(LIVE_STEP)
            with db.sessions()() as s:
                s.get(Run, run_id).status = "succeeded"
                s.commit()
            print("live run finished")

        if runs:
            threading.Thread(target=live, args=(runs[0][0], runs[0][2]), daemon=True).start()
        print(f"\nLITSTORM_MCP_URL=http://127.0.0.1:{PORT}/api/mcp")
        print(f"LITSTORM_MCP_TOKEN={token}", flush=True)

        import uvicorn

        uvicorn.run(create_app(), host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main(sys.argv[1:])
