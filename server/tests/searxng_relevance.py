"""How many of SearXNG's first five results are about the query, engine by
engine (docs/research/2026-10-06-thai-deep-empty-report.md). Run inside the
stack, where `searxng` resolves:

    docker exec -i litstorm-worker-1 python - < server/tests/searxng_relevance.py

A result counts as relevant when it contains one of its query's key terms,
a rough label, but it does not count a dictionary page with Thai on it as
relevant, as `top5_thai` in compare_searxng.py did. `kept` is what
knowledge_storm.rm.on_topic keeps of them.
"""
import json
import time
import urllib.parse
import urllib.request

from knowledge_storm.rm import on_topic

QUERIES = {
    "ความคืบหน้าล่าสุด โครงการรถไฟความเร็วสูงไทย-จีน 2569": ("รถไฟ", "ไฮสปีด", "high speed"),
    "ปัญหาและอุปสรรค โครงการรถไฟความเร็วสูง กรุงเทพ-หนองคาย": ("รถไฟ", "ไฮสปีด", "high speed"),
    "ความคืบหน้าล่าสุด โครงการรถไฟความเร็วสูงไทย-จีน": ("รถไฟ", "ไฮสปีด", "high speed"),
    "ประเพณีสงกรานต์": ("สงกรานต์",),
    "Thailand China high-speed railway progress 2026": ("rail",),
    "CRISPR off-target effects": ("crispr",),
}
MODES = {"all engines": {}, "all engines, language=th": {"language": "th"}, "bing": {"engines": "bing"},
         "yahoo": {"engines": "yahoo"}}

for query, keys in QUERIES.items():
    for mode, extra in MODES.items():
        url = "http://searxng:8080/search?" + urllib.parse.urlencode({"q": query, "format": "json", **extra})
        try:
            body = json.load(urllib.request.urlopen(url, timeout=40))
        except Exception as error:  # noqa: BLE001 - a probe; say so and go on
            print(f"{query[:30]:30} | {mode:24} | {error}")
            continue
        results = [r for r in body.get("results", []) if (r.get("content") or "").strip()]
        text = [f"{r.get('title') or ''} {r.get('content') or ''}" for r in results]
        relevant = [any(k in t.lower() for k in keys) for t in text]
        kept = [on_topic(query, t) for t in text]
        print(f"{query[:30]:30} | {mode:24} | n={len(results):2} | relevant in top 5: {sum(relevant[:5])} | "
              f"kept: {sum(kept)} ({sum(k and not r for k, r in zip(kept, relevant))} not relevant), "
              f"left out: {len(kept) - sum(kept)} ({sum(r and not k for k, r in zip(kept, relevant))} relevant)")
        time.sleep(1.5)
