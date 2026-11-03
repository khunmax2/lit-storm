#!/bin/sh
# Asks whether the deployed system works end to end, which the health checks
# cannot: DeepLit's API through its web front, DeepLit reaching MRA through
# "mra", and MRA answering for DeepLit's key. Spends no LLM tokens.
#
#   sh deploy/aiforthai/smoke-test.sh "docker compose -f deploy/aiforthai/compose.yml --env-file .env"
set -eu
compose="$1"
py() { $compose exec -T api python -c "$1"; }

echo "-- DeepLit: the web front serves the app and forwards /api"
$compose exec -T web wget -qO- http://127.0.0.1/api/health >/dev/null
$compose exec -T web sh -c 'wget -qO- http://127.0.0.1/ | grep -q "<div id=\"root\""'

echo "-- DeepLit -> MRA: the proxy answers and MRA reports its status"
py "import urllib.request; urllib.request.urlopen('http://mra/api/v1/healthz', timeout=10)"

echo "-- MRA knows DeepLit's key, and DeepLit has it set"
py "
import httpx
from litstorm import db, medical
with db.sessions()() as s:
    assert medical.configured(s), 'Medical Review is not set up in DeepLit'
    url, key = medical.load(s).url, medical.key(s)
# MRA answers 401 to a key it does not know on any route that reads the caller.
r = httpx.get(url + '/api/v1/reviews', params={'limit': 1}, headers={'X-API-Key': key}, timeout=10)
assert r.status_code == 200, 'MRA answered %d to DeepLit key' % r.status_code
print('MRA', url, 'answered', r.status_code)
"
echo "smoke test passed"
