"""Does reading the topic first help? (litstorm.interpret, docs/adr/0014)

    uv run python tests/interpret_benchmark.py <session.json> <output.json> [--engines storm,deep] [--topics 6] < judge key

For each topic and mode, two Runs at the fast level, made one after the
other so they meet the same search engines and the same queue: one with its
mode set to read the topic first, one without. The mode's setting is put
back to on at the end. Per Run: how it ended, the sources its report cites,
how many of them are on the topic, how many are in Thai, the time and the
cost.

"On the topic" is judged per source by one call to a cheap model (OpenRouter,
Gemini Flash Lite) that sees the topic and the source's title and site, and
not which Run it came from. Its key comes on stdin, never the command line.

<session.json> is {"token", "csrf"} for an Administrator's browser session,
made on the stack (not a password). LITSTORM_BENCH_URL is the stack's
address. Every Run is real and costs money: about $0.02 for STORM, $0.01 for
Deep Research and $0.05 for Agent Research at the fast level.
"""

import argparse
import json
import os
import re
import sys
import time

import httpx

BASE = os.environ.get("LITSTORM_BENCH_URL", "http://localhost:8095/litstorm")
JUDGE_MODEL = "google/gemini-3.1-flash-lite"
FINAL = {"succeeded", "failed", "cancelled", "interrupted"}
THAI = re.compile(r"[฀-๿]")

# Three Thai, three English; in each, one narrow, one broad, one short and open.
TOPICS = [
    ("ผลกระทบของฝุ่น PM2.5 ต่อสุขภาพเด็กในเชียงใหม่", "th"),
    ("การใช้ ChatGPT ในการเรียนการสอนระดับมหาวิทยาลัยไทย", "th"),
    ("ภาษีคาร์บอน", "th"),
    ("CRISPR gene therapy for sickle cell disease", "en"),
    ("Microplastics in drinking water", "en"),
    ("Remote work", "en"),
]

JUDGE = """Topic of a research report: {topic}

Below are the sources the report cites, by number, as title and site. For each, say whether it \
is about the topic, i.e. a reader researching the topic would find it relevant.

{sources}

Answer with one JSON object mapping each number to true or false, and nothing else."""


class Api:
    def __init__(self, session):
        self.c = httpx.Client(base_url=BASE, timeout=60, cookies={
            "litstorm_session": session["token"], "litstorm_csrf": session["csrf"]})
        self.h = {"X-CSRF-Token": session["csrf"]}

    def get(self, path):
        r = self.c.get(path)
        r.raise_for_status()
        return r.json()

    def send(self, method, path, body):
        r = self.c.request(method, path, json=body, headers=self.h)
        r.raise_for_status()
        return r.json()


def judge(key, topic, sources):
    """({source id: on the topic}, what the call cost), from one call; nothing judged if it fails."""
    try:
        return _judge(key, topic, sources)
    except (httpx.HTTPError, KeyError, IndexError) as error:
        print(f"  the judge failed: {type(error).__name__}", flush=True)
        return {}, None


def _judge(key, topic, sources):
    listing = "\n".join(f"{s['id']}. {s['title']} — {httpx.URL(s['url']).host}" for s in sources)
    r = httpx.post("https://openrouter.ai/api/v1/chat/completions", timeout=60, headers={"Authorization": f"Bearer {key}"},
                   json={"model": JUDGE_MODEL, "max_tokens": 1500, "temperature": 0,
                         "messages": [{"role": "user", "content": JUDGE.format(topic=topic, sources=listing)}]})
    r.raise_for_status()
    body = r.json()
    text = body["choices"][0]["message"]["content"] or ""
    match = re.search(r"\{.*\}", text, re.S)
    try:
        verdicts = {int(k): bool(v) for k, v in json.loads(match.group(0)).items()} if match else {}
    except ValueError:
        verdicts = {}
    usage = body.get("usage") or {}
    return verdicts, usage.get("cost")


def follow(api, run_ids):
    while True:
        runs = {i: api.get(f"/api/runs/{i}") for i in run_ids}
        if all(r["status"] in FINAL for r in runs.values()):
            return runs
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session")
    parser.add_argument("output")
    parser.add_argument("--engines", default="storm,deep")
    parser.add_argument("--topics", type=int, default=len(TOPICS))
    args = parser.parse_args()
    key = sys.stdin.readline().strip()
    with open(args.session, encoding="utf-8") as f:
        api = Api(json.load(f))
    engines = args.engines.split(",")
    results = []
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            results = json.load(f)  # carry on from where it stopped
    done = {(r["topic"], r["engine"], r["interpret"]) for r in results}
    try:
        for topic, language in TOPICS[: args.topics]:
            for engine in engines:
                made = {}
                for interpret in (True, False):
                    if (topic, engine, interpret) in done:
                        continue
                    api.send("PUT", f"/api/admin/engines/{engine}", {"interpret": interpret})
                    session = api.send("POST", "/api/sessions",
                                       {"topic": topic, "language": language, "engine": engine, "depth": "fast"})
                    made[interpret] = session["runs"][0]["id"]
                if not made:
                    continue
                print(f"{engine} · {topic}: {list(made.values())}", flush=True)
                finished = follow(api, made.values())
                costs = {r["id"]: r["cost_usd"] for r in api.get("/api/admin/runs?limit=50")}
                for interpret, run_id in made.items():
                    run = finished[run_id]
                    sources = []
                    if run["status"] == "succeeded":
                        sources = api.get(f"/api/runs/{run_id}/report")["sources"]
                    verdicts, judged_usd = judge(key, topic, sources) if sources else ({}, None)
                    reading = (run.get("notes") or {}).get("interpretation") or {}
                    row = {
                        "topic": topic, "language": language, "engine": engine, "interpret": interpret, "run_id": run_id,
                        "status": run["status"], "reason": run.get("reason"),
                        "seconds": round(_seconds(run)), "cost_usd": float(costs.get(run_id) or 0),
                        "sources": len(sources), "on_topic": sum(1 for s in sources if verdicts.get(s["id"])),
                        "judged": len(verdicts), "thai_sources": sum(1 for s in sources if THAI.search(s["title"])),
                        "judge_usd": judged_usd, "reading": reading or None,
                    }
                    results.append(row)
                    print(f"  {'on ' if interpret else 'off'} {row['status']:9} sources={row['sources']:3} "
                          f"on_topic={row['on_topic']:3} thai={row['thai_sources']:3} {row['seconds']:4}s "
                          f"${row['cost_usd']:.4f}", flush=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=1)
    finally:
        for engine in engines:
            api.send("PUT", f"/api/admin/engines/{engine}", {"interpret": True})


def _seconds(run):
    from datetime import datetime

    if not run.get("started_at") or not run.get("finished_at"):
        return 0
    start, end = (datetime.fromisoformat(run[k].replace("Z", "+00:00")) for k in ("started_at", "finished_at"))
    return (end - start).total_seconds()


if __name__ == "__main__":
    main()
