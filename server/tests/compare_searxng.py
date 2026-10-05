"""The same queries through lit-storm's SearXNG and searxng-LDR-academic's
settings (docs/benchmarks/2026-10-05-searxng-vs-ldr-academic.md).

    uv run python tests/compare_searxng.py <out.json>

Expects two throwaway instances of the stack's image: lit-storm's
stack/searxng/settings.yml on 127.0.0.1:8098, and the fork's
searx/settings.yml, with `json` added under search.formats, on 8097
(the fork changes no engine code, only settings, so this is the fork's
behaviour on the same engines).
"""
import json, sys, time
from collections import Counter
import requests

ACADEMIC = "arxiv,crossref,europepmc,google scholar,openairedatasets,openairepublications,openalex,pdbe,pubmed,semantic scholar"
MODES = {
    "ours: SearXNG (general)": ("http://127.0.0.1:8098/search", {}),
    "ours: LDR-academic provider": ("http://127.0.0.1:8098/search", {"engines": ACADEMIC}),
    "fork: default search": ("http://127.0.0.1:8097/search", {}),
    "fork: academic category": ("http://127.0.0.1:8097/search", {"categories": "academic"}),
}
QUERIES = [
    "retrieval augmented generation evaluation",
    "CRISPR off-target effects",
    "Thailand electric vehicle market 2025",
    "รถยนต์ไฟฟ้าในประเทศไทย",
    "โมเดลภาษาขนาดใหญ่ภาษาไทย",
    "ผลกระทบของฝุ่น PM2.5 ต่อสุขภาพ",
]
ACADEMIC_ENGINES = set(ACADEMIC.split(",")) | {"base", "wolframalpha", "library of congress"}
out = []
for q in QUERIES:
    for mode, (url, extra) in MODES.items():
        t = time.monotonic()
        try:
            r = requests.get(url, params={"q": q, "format": "json", **extra}, timeout=40)
            body = r.json()
        except Exception as e:
            out.append({"q": q, "mode": mode, "error": str(e)})
            continue
        took = round(time.monotonic() - t, 1)
        res = body.get("results", [])
        top5 = res[:5]
        out.append({
            "q": q, "mode": mode, "seconds": took, "n": len(res),
            "engines": Counter(e for r_ in res for e in r_.get("engines", [])).most_common(),
            "top5": [(r_.get("engines"), r_["url"][:90], r_.get("title", "")[:70]) for r_ in top5],
            "top5_academic": sum(1 for r_ in top5 if set(r_.get("engines", [])) & ACADEMIC_ENGINES),
            "top5_thai": sum(1 for r_ in top5 if any("\u0e00" <= ch <= "\u0e7f" for ch in r_.get("title", "") + r_.get("content", ""))),
            "unresponsive": body.get("unresponsive_engines", []),
        })
        time.sleep(1.5)
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for o in out:
    if "error" in o:
        print(o["q"][:30], "|", o["mode"], "| ERROR", o["error"][:80]); continue
    print(f'{o["q"][:34]:34} | {o["mode"]:27} | {o["seconds"]:4}s | n={o["n"]:3} | top5 acad={o["top5_academic"]} thai={o["top5_thai"]} | unresp={len(o["unresponsive"])}')
