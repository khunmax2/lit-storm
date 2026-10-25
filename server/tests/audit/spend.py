"""Total OpenRouter spend of the keys in the given env files, for the audit's budget.

    python server/tests/audit/spend.py stack/.env ../MedicalReviewerAgent/.env

Reads the OPENROUTER_API_KEY= line of each file (a file without one is skipped),
asks GET https://openrouter.ai/api/v1/key for each distinct key and prints
{"keys": [{"id", "usage_usd", "limit_usd"}], "total_usd"}. The id is the first
8 hex characters of sha256(key); the key itself is never printed.

Known limits (left as is for the audit): if no file has the key it prints total 0.0 with no warning;
the env parsing does not handle a BOM, an `export ` prefix or a trailing comment; the first OPENROUTER_API_KEY=
line of a file wins; OpenRouter's usage figure lags about one Run behind.
"""

import hashlib
import json
import sys
import urllib.request

URL = "https://openrouter.ai/api/v1/key"


def read_key(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'").strip() or None
    return None


def fetch(key):
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


def main(paths):
    seen = {}
    for path in paths:
        key = read_key(path)
        if not key:
            continue
        kid = hashlib.sha256(key.encode()).hexdigest()[:8]
        if kid in seen:
            continue
        data = fetch(key)
        limit = data.get("limit")
        seen[kid] = {
            "id": kid,
            "usage_usd": float(data.get("usage") or 0),
            "limit_usd": None if limit is None else float(limit),
        }
    keys = list(seen.values())
    print(json.dumps({"keys": keys, "total_usd": round(sum(k["usage_usd"] for k in keys), 6)}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
