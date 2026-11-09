#!/usr/bin/env bash
# ============================================
# Build the images a host runs, from this checkout, the Engine forks and
# MedicalReviewerAgent at the commits pinned in stack/engines.lock.json. The
# one place the build arguments live: the GHCR workflow runs this, and so
# can a laptop.
#
#   bash stack/build-images.sh <tag> [agents-dir] [deep-dir] [mra-dir]
#
#   <tag>        e.g. deploy-2026-10-01; the images are
#                  $REGISTRY/lit-storm-server:<tag>
#                  $REGISTRY/lit-storm-web:<tag>   (served under $BASE_PATH)
#                  $REGISTRY/mra-backend:<tag>     MedicalReviewerAgent's api, worker and migrations
#                  $REGISTRY/mra-web:<tag>         its web console (no build arguments: set where it runs)
#                  $REGISTRY/mra-searxng:<tag>     the academic SearXNG fork its compose builds
#   agents-dir   a checkout of lit_agents-deep-research (default ../agents-deep-research)
#   deep-dir     a checkout of lit_deep-research-web    (default ../deep-research-web-ui)
#   mra-dir      a checkout of MedicalReviewerAgent     (default ../MedicalReviewerAgent)
#
#   REGISTRY   default ghcr.io/khunmax2
#   BASE_PATH  default /litstorm — host 203 serves lit-storm there, and the
#              web image has it built in (docs/web-app-design.md, base path)
#
# Builds into the local daemon; pushing is the caller's step. Refuses a fork
# checkout that is not at its pinned commit, so what is built is what the
# lock file says.
# ============================================
set -euo pipefail
# Git Bash on Windows rewrites arguments that look like paths: "/litstorm"
# went into the build as "C:/Program Files/Git/litstorm" (caught by the
# check at the end). No effect elsewhere.
export MSYS_NO_PATHCONV=1

TAG="${1:?usage: build-images.sh <tag> [agents-dir] [deep-dir] [mra-dir]}"
# Native paths ("D:/..." under Git Bash, as `pwd -W` gives), which git,
# Python and docker on Windows all read; plain `pwd` everywhere else.
native() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }
HERE="$(native "$(dirname "${BASH_SOURCE[0]}")")"
ROOT="$(native "$HERE/..")"
AGENTS="$(native "${2:-$ROOT/../agents-deep-research}")"
DEEP="$(native "${3:-$ROOT/../deep-research-web-ui}")"
MRA="$(native "${4:-$ROOT/../MedicalReviewerAgent}")"
REGISTRY="${REGISTRY:-ghcr.io/khunmax2}"
BASE_PATH="${BASE_PATH:-/litstorm}"

# python3 on Linux; on Windows `python3` may be the Store's placeholder.
PY=""
for candidate in python3 python; do
  if "$candidate" -c "import json" >/dev/null 2>&1; then PY=$candidate; break; fi
done
[ -n "$PY" ] || { echo "!! no Python to read stack/engines.lock.json" >&2; exit 1; }
LOCK="$HERE/engines.lock.json"
pin() { "$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]['commit'])" "$LOCK" "$1"; }

for name in agents deep mra; do
  case $name in agents) dir=$AGENTS ;; deep) dir=$DEEP ;; mra) dir=$MRA ;; esac
  want=$(pin "$name")
  have=$(git -C "$dir" rev-parse HEAD)
  if [ "$have" != "$want" ]; then
    echo "!! $dir is at $have; stack/engines.lock.json pins $name at $want" >&2
    echo "   check it out there (git -C $dir checkout $want), or move the pin" >&2
    exit 1
  fi
  if [ -n "$(git -C "$dir" status --porcelain)" ]; then
    echo "!! $dir has uncommitted changes; they would go into the image but not into the pin" >&2
    exit 1
  fi
  echo "  $name  $want  ($dir)"
done

# The SearXNG fork MRA builds is pinned in MRA's own compose; the lock must
# name the same commit, or the image would not be the one MRA was tested with.
SEARXNG_PIN=$(pin mra_searxng)
grep -q "searxng-LDR-academic.git#$SEARXNG_PIN" "$MRA/docker-compose.yml" || {
  echo "!! $MRA/docker-compose.yml does not build searxng-LDR-academic at $SEARXNG_PIN (stack/engines.lock.json)" >&2
  exit 1
}

SERVER="$REGISTRY/lit-storm-server:$TAG"
WEB="$REGISTRY/lit-storm-web:$TAG"

echo "== $SERVER =="
docker build -f "$ROOT/server/Dockerfile" \
  --build-context "agents=$AGENTS" --build-context "deep=$DEEP" \
  --label "org.opencontainers.image.source=https://github.com/khunmax2/lit-storm" \
  --label "org.opencontainers.image.revision=$(git -C "$ROOT" rev-parse HEAD)" \
  --label "litstorm.engines.agents=$(pin agents)" --label "litstorm.engines.deep=$(pin deep)" \
  -t "$SERVER" "$ROOT"

echo "== $WEB (base path $BASE_PATH) =="
docker build --build-arg "LITSTORM_BASE_PATH=$BASE_PATH" \
  --label "org.opencontainers.image.source=https://github.com/khunmax2/lit-storm" \
  --label "org.opencontainers.image.revision=$(git -C "$ROOT" rev-parse HEAD)" \
  -t "$WEB" "$ROOT/web"

# What the web image serves under must be what the host's nginx forwards.
served=$(docker run --rm --entrypoint cat "$WEB" /etc/nginx/base-path)
[ "$served" = "$BASE_PATH" ] || { echo "!! $WEB serves under '$served', not $BASE_PATH" >&2; exit 1; }

MRA_LABELS=(--label "org.opencontainers.image.source=https://github.com/$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['mra']['repo'])" "$LOCK")"
            --label "org.opencontainers.image.revision=$(pin mra)")
echo "== $REGISTRY/mra-backend:$TAG =="
docker build "${MRA_LABELS[@]}" -t "$REGISTRY/mra-backend:$TAG" "$MRA/backend"
echo "== $REGISTRY/mra-web:$TAG =="
docker build "${MRA_LABELS[@]}" -t "$REGISTRY/mra-web:$TAG" "$MRA/frontend"
echo "== $REGISTRY/mra-searxng:$TAG =="
docker build --label "org.opencontainers.image.revision=$SEARXNG_PIN" -t "$REGISTRY/mra-searxng:$TAG"   "https://github.com/porespellar/searxng-LDR-academic.git#$SEARXNG_PIN"
echo "built: $SERVER, $WEB (serves $served), $REGISTRY/mra-{backend,web,searxng}:$TAG"
