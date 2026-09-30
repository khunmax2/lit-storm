"""Phase 2.3 acceptance: Discussions with Co-STORM, against a running stack.

    uv run python tests/e2e_discussion.py <output dir>

Checks what docs/web-app-implementation-plan.md sets for 2.3 and writes
<output dir>/discussion.md with the evidence:

- real Discussions in Thai and in English: the warm start, speaking into it,
  the table going on by itself, and reports;
- coming back after the page was closed: the conversation and what is left
  of its block of Turns are where they were;
- a Worker that dies mid-Turn loses only that Turn: it is interrupted and not
  counted, and the next Turn goes on from the last one that finished;
- a Discussion files into a Project, goes to the Trash and comes back.

The first release's twelve criteria are acceptance.py's, run separately.

Runs against the stack in daily use, the mirror of host 203
(LITSTORM_E2E_URL, default http://127.0.0.1:8090/litstorm), signed in as
benchmark.py's Administrator. Real model calls: a few cents.
"""

import os
import re
import subprocess
import sys
import time

import httpx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = os.environ.get("LITSTORM_E2E_URL", "http://127.0.0.1:8090/litstorm")
PROJECT = os.environ.get("LITSTORM_E2E_PROJECT", "litstorm")
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", os.path.join(ROOT, "stack", "compose.yml"),
           "-f", os.path.join(ROOT, "stack", "compose.mirror.yml")]
EMAIL = os.environ.get("LITSTORM_BENCH_EMAIL", "admin@example.org")
PASSWORD = os.environ.get("LITSTORM_BENCH_PASSWORD", "acceptance admin pw")
THAI = re.compile(r"[฀-๿]")


class Api:
    def __init__(self):
        self.c = httpx.Client(base_url=BASE, timeout=120)
        r = self.c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        r.raise_for_status()

    def _h(self):
        return {"X-CSRF-Token": self.c.cookies.get("litstorm_csrf")}

    def get(self, path):
        r = self.c.get(path)
        r.raise_for_status()
        return r.json()

    def post(self, path, body=None):
        return self.c.post(path, json=body or {}, headers=self._h())

    def patch(self, path, body):
        return self.c.patch(path, json=body, headers=self._h())

    def delete(self, path):
        return self.c.delete(path, headers=self._h())

    def discussion(self, did):
        return self.get(f"/api/discussions/{did}")

    def wait(self, did, timeout=900, every=3):
        """Until no Turn is waiting or running; the Discussion then."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            d = self.discussion(did)
            if d["current"] is None:
                return d
            time.sleep(every)
        raise TimeoutError(f"discussion {did} still busy after {timeout}s")

    def turn(self, did, **body):
        r = self.post(f"/api/discussions/{did}/turns", body)
        assert r.status_code == 201, r.text
        return r.json()


class Record:
    def __init__(self):
        self.lines = []
        self.failed = 0

    def section(self, title):
        print(f"\n== {title}", flush=True)
        self.lines += ["", f"## {title}", ""]

    def check(self, ok, text):
        mark = "✓" if ok else "✗"
        self.failed += 0 if ok else 1
        print(f"  {mark} {text}", flush=True)
        self.lines.append(f"- {mark} {text}")
        return ok

    def note(self, text):
        print(f"    {text}", flush=True)
        self.lines.append(f"- {text}")


def compose(*args):
    return subprocess.run([*COMPOSE, *args], capture_output=True, text=True, check=False)


def last_turn(d):
    return d["turns"][-1]


def seconds(turn):
    from datetime import datetime

    a = datetime.fromisoformat(turn["started_at"].replace("Z", "+00:00"))
    b = datetime.fromisoformat(turn["finished_at"].replace("Z", "+00:00"))
    return (b - a).total_seconds()


def conversation(api, rec, topic, language, question, depth="fast"):
    r = api.post("/api/discussions", {"topic": topic, "language": language, "depth": depth})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    d = api.wait(did)
    start = last_turn(d)
    if not rec.check(start["status"] == "succeeded", f"warm start ({depth}): {start['status']} in {seconds(start):.0f}s"
                     + (f" — {start['reason']}: {start['message']}" if start["status"] != "succeeded" else "")):
        return did, None
    view = d["view"]
    rec.check(len(view["turns"]) > 0 and len(view["sources"]) > 0,
              f"the briefing: {len(view['turns'])} messages, {len(view['sources'])} sources, "
              f"mind map {[n['name'] for n in view['mind_map']]}")
    text = " ".join(t["text"] for t in view["turns"])
    if language == "th":
        rec.check(len(THAI.findall(text)) > len(text) * 0.3, "the table speaks Thai")
    else:
        rec.check(len(THAI.findall(text)) == 0, "the table speaks English")

    before = len(view["turns"])
    api.turn(did, action="say", text=question)
    d = api.wait(did)
    said = last_turn(d)
    turns = d["view"]["turns"]
    guest = [t for t in turns if t["role"] == "Guest"]
    rec.check(said["status"] == "succeeded" and guest and guest[-1]["text"] == question and turns[-1]["role"] != "Guest",
              f"the owner speaks and the table answers ({seconds(said):.0f}s): "
              f"{turns[-1]['role']}: {turns[-1]['text'][:120]!r}")

    api.turn(did, action="auto", steps=3)
    d = api.wait(did)
    auto = last_turn(d)
    rec.check(auto["status"] == "succeeded" and len(d["view"]["turns"]) >= before + 2 + 3,
              f"three rounds on their own ({seconds(auto):.0f}s): now {len(d['view']['turns'])} messages")

    api.turn(did, action="report")
    d = api.wait(did)
    rep = last_turn(d)
    if rec.check(rep["status"] == "succeeded" and d["reports"], f"a report ({seconds(rep):.0f}s)"):
        report = api.get(f"/api/runs/{d['reports'][-1]['run_id']}/report")
        body = report["lead"] + " ".join(s["body"] for s in report["sections"])
        rec.check(bool(report["sources"]) and all(s["evidence"] for s in report["sources"]),
                  f"{len(report['sources'])} sources, each with its evidence; sections {[s['heading'] for s in report['sections']]}")
        rec.check(bool(report["lead"]), f"it has a lead: {report['lead'][:100]!r}")
        if language == "th":
            rec.check(len(THAI.findall(body)) > len(body) * 0.3, "the report is in Thai")
    rec.check(d["allowance"]["used"] == 4 and d["allowance"]["remaining"] == d["allowance"]["per_block"] - 4,
              f"four Turns used of the block: {d['allowance']}")
    return did, d


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    api = Api()
    rec = Record()
    quota0 = api.get("/api/me/quota")

    rec.section("A Discussion in Thai")
    th, d_th = conversation(api, rec, "ผลกระทบของเทศกาลสงกรานต์ต่อการท่องเที่ยว", "th",
                            "แล้วเศรษฐกิจของชุมชนท้องถิ่นได้ประโยชน์จริงไหม")

    rec.section("A Discussion in English")
    en, _ = conversation(api, rec, "Microplastics in drinking water", "en",
                         "What can a household actually do about it?")

    quota1 = api.get("/api/me/quota")
    rec.check(quota1["used"] - quota0["used"] == 2, f"two Discussions took two quota units ({quota0['used']} → {quota1['used']})")

    rec.section("Coming back after the page was closed")
    again = Api()  # a new sign-in, as a browser opened later
    d = again.discussion(th)
    rec.check(d["view"]["turns"] == d_th["view"]["turns"], f"the conversation is as it was: {len(d['view']['turns'])} messages")
    rec.check(d["allowance"] == d_th["allowance"], f"so is what is left of the block: {d['allowance']['remaining']} Turns")
    again.turn(th, action="step")
    d = again.wait(th)
    rec.check(last_turn(d)["status"] == "succeeded" and len(d["view"]["turns"]) == len(d_th["view"]["turns"]) + 1,
              "one more round goes on from there")
    before = d

    rec.section("A Worker that dies mid-Turn")
    turn = api.turn(th, action="auto", steps=3)
    deadline = time.time() + 120
    while time.time() < deadline and api.get(f"/api/runs/{turn['id']}")["status"] != "running":
        time.sleep(1)
    time.sleep(4)
    compose("kill", "worker")
    rec.note("the worker container was killed while the Turn was running")
    time.sleep(75)  # past the 60-second lease
    compose("start", "worker")
    d = api.wait(th, timeout=180)
    lost = next(t for t in d["turns"] if t["id"] == turn["id"])
    rec.check(lost["status"] == "interrupted" and lost["quota_refunded"],
              f"the Turn is {lost['status']}, and not counted")
    rec.check(d["view"]["turns"] == before["view"]["turns"], "the conversation is the last finished Turn's")
    rec.check(d["allowance"]["used"] == before["allowance"]["used"], f"Turns used unchanged: {d['allowance']['used']}")
    time.sleep(10)
    rec.check(api.discussion(th)["current"] is None, "the lost Turn is not started again on its own")
    retried = api.post(f"/api/runs/{turn['id']}/retry").json()
    d = api.wait(th)
    rec.check(last_turn(d)["id"] == retried["id"] and last_turn(d)["status"] == "succeeded"
              and len(d["view"]["turns"]) >= len(before["view"]["turns"]) + 3,
              f"asked again, it goes on from the last finished Turn: {len(d['view']['turns'])} messages")

    rec.section("Projects and the Trash")
    project = api.post("/api/projects", {"name": "Discussions"}).json()
    moved = api.patch(f"/api/sessions/{en}", {"project_id": project["id"]}).json()
    listed = api.get(f"/api/projects/{project['id']}")["sessions"]
    rec.check(moved["project_id"] == project["id"] and listed[0]["kind"] == "discussion",
              "the English Discussion is filed in a Project, and listed there as a Discussion")
    rec.check(api.discussion(en)["project_name"] == "Discussions", "its page shows the Project")
    api.delete(f"/api/sessions/{en}")
    trash = api.get("/api/trash")
    rec.check(any(i["id"] == en and i["kind"] == "session" for i in trash), "deleted, it is in the Trash")
    rec.check(api.c.get(f"/api/discussions/{en}").status_code == 404, "and cannot be opened")
    api.post(f"/api/trash/session/{en}/restore")
    d = api.discussion(en)
    rec.check(bool(d["reports"]) and d["view"] is not None, "restored, it comes back with its conversation and report")

    verdict = "ผ่าน" if not rec.failed else f"ไม่ผ่าน {rec.failed} ข้อ"
    head = [f"# ตรวจรับช่วง 2.3 Discussion ({time.strftime('%Y-%m-%d')})", "",
            f"**ผล: {verdict}** — stack `{PROJECT}` ที่ {BASE}", "",
            "Co-STORM ทำงานเป็น Discussion ทีละ Turn ผ่านคิวเดียวกับ Run สคริปต์: `server/tests/e2e_discussion.py`"]
    with open(os.path.join(out, "discussion.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(head + rec.lines) + "\n")
    print(f"\n{verdict}")
    return 1 if rec.failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
