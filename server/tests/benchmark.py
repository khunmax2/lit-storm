"""How long research takes, what it costs, and how much it finds.

    uv run python tests/benchmark.py <output dir> [--search SearXNG,arXiv] [--topics 4] [--level standard] [--engine agent]

Runs a fixed set of topics through the API of a running stack, one Run at a
time, and writes <output dir>/benchmark.json and benchmark.md: per Run the
time spent waiting, starting the process, and in each stage, the tokens,
searches and estimated cost, and the number of sources in the report.

The second release sets a time target per depth level (docs/web-app-
design.md, "รุ่นสอง: ระดับความลึก เวลา และความเร็ว") and changes the
engines one step at a time; this is how each step is measured. Every Run is
real and costs money — a few cents each with a flash-class model.

Signs in as an Administrator (costs come from the admin usage API):
LITSTORM_BENCH_URL, LITSTORM_BENCH_EMAIL and LITSTORM_BENCH_PASSWORD, which
default to the stack and the account acceptance.py makes.
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime

import httpx

BASE = os.environ.get("LITSTORM_BENCH_URL", "http://127.0.0.1:8090")
EMAIL = os.environ.get("LITSTORM_BENCH_EMAIL", "admin@example.org")
PASSWORD = os.environ.get("LITSTORM_BENCH_PASSWORD", "acceptance admin pw")

# Fixed so that runs on different days compare: two Thai, two English, each
# pair one academic and one general topic.
TOPICS = [
    ("Retrieval-augmented generation", "en"),
    ("โมเดลภาษาขนาดใหญ่สำหรับภาษาที่มีทรัพยากรน้อย", "th"),
    ("History of the Songkran festival", "en"),
    ("ผลกระทบของการนอนดึกต่อสุขภาพ", "th"),
]
FINAL = {"succeeded", "failed", "cancelled", "interrupted"}
STAGES = ("research", "outline", "article", "polish", "normalize")


def _t(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


class Api:
    def __init__(self):
        self.c = httpx.Client(base_url=BASE, timeout=60)
        r = self.c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        self.h = {"X-CSRF-Token": self.c.cookies.get("litstorm_csrf")}

    def get(self, path):
        r = self.c.get(path)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        r = self.c.post(path, json=body, headers=self.h)
        r.raise_for_status()
        return r.json()


def timings(run):
    """Seconds spent in each part of a finished Run."""
    out = {"queued": _t(run["started_at"]) - _t(run["queued_at"]) if run["started_at"] else None}
    marks = [(e["data"]["stage"], _t(e["at"])) for e in run["events"] if e["type"] == "stage"]
    if run["started_at"] and marks:
        out["startup"] = marks[0][1] - _t(run["started_at"])
    ends = [t for _, t in marks[1:]] + [_t(run["finished_at"])]
    for (stage, start), end in zip(marks, ends):
        out[stage] = end - start
    out["total"] = _t(run["finished_at"]) - _t(run["started_at"]) if run["started_at"] else None
    return out


def one(api, topic, language, search_id, level, engine="storm"):
    body = {"topic": topic, "language": language, "search_provider_id": search_id, "engine": engine}
    if level:
        body["depth"] = level
    session = api.post("/api/sessions", body)
    run_id = session["runs"][0]["id"]
    while True:
        run = api.get(f"/api/runs/{run_id}")
        if run["status"] in FINAL:
            break
        time.sleep(3)
    usage = next((r for r in api.get("/api/admin/runs?limit=50") if r["id"] == run_id), {})
    return {
        "run_id": run_id,
        "topic": topic,
        "language": language,
        "status": run["status"],
        "reason": run["reason"],
        "sources": run["source_count"],
        "model": run["model_label"],
        "search": run["search_label"],
        "engine": run.get("engine", "storm"),
        "seconds": timings(run),
        "tokens_in": usage.get("tokens_in"),
        "tokens_out": usage.get("tokens_out"),
        "searches": usage.get("search_calls"),
        "cost_usd": float(usage["cost_usd"]) if usage.get("cost_usd") is not None else None,
    }


def _fmt(x, digits=0):
    return "–" if x is None else f"{x:.{digits}f}"


def report(results, out, note):
    rows = [
        "| Topic | Search | Status | Total s | Start | Research | Outline | Article | Polish | Searches | Tokens in/out | Cost $ | Sources |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["seconds"]
        rows.append(
            f"| {r['topic'][:40]} ({r['language']}) | {r['search']} | {r['status']} | {_fmt(s.get('total'))} "
            f"| {_fmt(s.get('startup'))} | {_fmt(s.get('research'))} | {_fmt(s.get('outline'))} "
            f"| {_fmt(s.get('article'))} | {_fmt(s.get('polish'))} | {r['searches'] or '–'} "
            f"| {r['tokens_in'] or '–'} / {r['tokens_out'] or '–'} | {_fmt(r['cost_usd'], 4)} | {r['sources'] or '–'} |"
        )
    done = [r for r in results if r["status"] == "succeeded"]
    summary = []
    for search in sorted({r["search"] for r in done}):
        mine = [r for r in done if r["search"] == search]
        totals = [r["seconds"]["total"] for r in mine]
        summary.append(
            f"- **{search}** ({len(mine)} Runs): median {statistics.median(totals):.0f}s, "
            f"slowest {max(totals):.0f}s, median cost ${statistics.median([r['cost_usd'] or 0 for r in mine]):.4f}"
        )
    lines = [f"# Benchmark {time.strftime('%Y-%m-%d %H:%M')}", "", note, "", *summary, "", *rows, ""]
    with open(os.path.join(out, "benchmark.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(out, "benchmark.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n".join(summary))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--search", default="SearXNG", help="Search Provider labels, comma-separated")
    ap.add_argument("--topics", type=int, default=len(TOPICS), help="how many of the fixed topics")
    ap.add_argument("--level", default=None, help="depth level, once Runs take one")
    ap.add_argument("--note", default="", help="what this run measures, for the report")
    ap.add_argument("--engine", default="storm", help="research mode: storm, agent, ...")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    api = Api()
    providers = {p["label"]: p["id"] for p in api.get("/api/admin/search-providers")}
    results = []
    for label in args.search.split(","):
        for topic, language in TOPICS[: args.topics]:
            print(f"{label:>8} · {topic} ...", flush=True)
            r = one(api, topic, language, providers[label], args.level, args.engine)
            s = r["seconds"]
            print(f"         {r['status']} in {_fmt(s.get('total'))}s (start {_fmt(s.get('startup'))}, "
                  f"research {_fmt(s.get('research'))}), {r['searches']} searches, ${_fmt(r['cost_usd'], 4)}", flush=True)
            results.append(r)
    report(results, args.out, args.note)


if __name__ == "__main__":
    main()
