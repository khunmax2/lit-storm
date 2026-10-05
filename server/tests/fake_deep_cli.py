"""Stands in for the Deep Research CLI (cli/litstorm.ts) in tests: reads the
config line, then writes the events its topic asks for, as JSON lines.

    topic "[hang] ..." | "[fail] ..." | "[empty] ..." | "[search] ..."; anything else: ok

"[search]" asks the search address it was given, as the CLI asks a SearXNG,
and reports on the first result.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

line = json.loads(sys.stdin.readline())
out = sys.stdout
# Its script rides in the topic ("[hang] ..."): the Engine hands the CLI
# its keys and nothing else of the environment.
script = line["query"][1:line["query"].index("]")] if line["query"].startswith("[") else "ok"


def emit(**event):
    out.write(json.dumps(event, ensure_ascii=False) + "\n")
    out.flush()


if not os.environ.get("LITSTORM_AI_API_KEY"):
    emit(type="error", message="no key")
    sys.exit(2)
emit(type="stage", stage="research")
emit(type="usage", promptTokens=100, completionTokens=20)
emit(type="searched", urls=["https://a.test/x", "https://b.test/y"], titles=["A", "B"])
if script == "search":
    url = line["search"]["apiBase"] + "?" + urllib.parse.urlencode({"q": "Songkran", "format": "json"})
    found = json.loads(urllib.request.urlopen(url, timeout=10).read())["results"]
    first = found[0]
    emit(type="searched", urls=[r["url"] for r in found], titles=[r["title"] for r in found])
    emit(type="stage", stage="report")
    emit(type="report", markdown="# Songkran\n\nIt is the Thai New Year [1].",
         learnings=[{"url": first["url"], "title": first["title"], "learning": "New Year", "excerpt": first["content"]}])
    sys.exit(0)
if script == "hang":
    while True:
        time.sleep(1)
if script == "fail":
    emit(type="error", message="the model refused")
    sys.exit(2)
if script == "empty":
    emit(type="error", message="the research found nothing it could use")
    sys.exit(2)
emit(type="stage", stage="report")
emit(type="usage", promptTokens=300, completionTokens=200)
emit(type="report", markdown="# Songkran\n\nIt is the Thai New Year [1]. It falls in April [2][3].\n\n## Water\nSplashing [3].",
     learnings=[
         {"url": "https://a.test/x", "title": "A", "learning": "New Year", "excerpt": "Songkran marks the Thai New Year."},
         {"url": "https://b.test/y", "title": "B", "learning": "April", "excerpt": "It falls on 13-15 April."},
         {"url": "https://a.test/x", "title": "A", "learning": "Water", "excerpt": "People splash water."},
     ])
