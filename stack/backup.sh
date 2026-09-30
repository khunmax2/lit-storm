#!/usr/bin/env bash
# ============================================
# Back up a lit-storm stack, or restore one (docs/web-app-design.md,
# รุ่นสอง: การติดตั้ง — สำรองข้อมูล; decided in docs/deploy/HOST-203.md §8).
#
#   bash stack/backup.sh [dest-dir]                 default ../_litstorm_backup
#   bash stack/backup.sh --verify <stamp> [dest-dir]
#   bash stack/backup.sh --restore <stamp> [dest-dir]
#
#   PROJECT=litstorm   the Compose project (containers are found by its labels)
#   KEEP_DAYS=30       backups older than this are deleted after a new one
#
# Needs docker only (no sudo). Safe while the stack serves: pg_dump takes a
# consistent snapshot, and the run files are read through a throwaway
# container that mounts the volume read-only.
#
# A backup is three files, one stamp:
#   litstorm-<stamp>.dump          the database (pg_dump -Fc): users, Runs,
#                                  settings, and API keys encrypted with
#                                  stack/secrets/secret_key
#   litstorm-runs-<stamp>.tar.gz   the run-data volume: each Run's files and
#                                  report, a Discussion's state. The search
#                                  cache is left out; it refills itself.
#   litstorm-<stamp>.manifest      what was backed up, and the fingerprint of
#                                  the secret_key the dump needs
#
# secret_key is NOT in the backup, on purpose: stored next to the database it
# would decrypt every API key in it. Keep a copy of stack/secrets/secret_key
# somewhere else (HOST-203.md §8). Restoring with a different key works, but
# every stored API key has to be entered again.
#
# Restore (a stack that is running, into it — its data is REPLACED):
#   api, worker and web are stopped, the volume and the database are put
#   back, and they are started again. Restore onto the image the dump was
#   taken under, or a newer one (the API migrates forward on start).
# ============================================
set -euo pipefail

PROJECT="${PROJECT:-litstorm}"
KEEP_DAYS="${KEEP_DAYS:-30}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

container() { # service — the project's container for it
  docker ps -a --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$1" --format '{{.Names}}' | head -1
}

dest_dir() {
  local d="${1:-$HERE/../../_litstorm_backup}"
  mkdir -p "$d"
  # `pwd -W` is Git Bash's Windows path, which docker on Windows wants.
  (cd "$d" && { pwd -W 2>/dev/null || pwd; })
}

volume_of() { # container path — the named volume mounted there
  docker inspect "$1" --format "{{range .Mounts}}{{if eq .Destination \"$2\"}}{{.Name}}{{end}}{{end}}"
}

fingerprint() { # the secret_key's, never the key itself
  local key="$HERE/secrets/secret_key"
  [ -s "$key" ] && sha256sum "$key" | cut -c1-16 || echo "none"
}

tables_in() { # dump — how many tables with data it holds
  docker exec -i "$DB" pg_restore --list < "$1" | grep -c 'TABLE DATA' || true
}

DB=$(container db)
[ -n "$DB" ] || { echo "!! no db container in Compose project '$PROJECT' (set PROJECT=...)" >&2; exit 1; }

case "${1:-}" in
  --verify)
    STAMP="${2:?usage: --verify <stamp> [dest-dir]}"; DEST=$(dest_dir "${3:-}")
    echo "== verify $STAMP in $DEST =="
    cat "$DEST/litstorm-$STAMP.manifest"
    echo "  tables with data: $(tables_in "$DEST/litstorm-$STAMP.dump")"
    echo "  run files: $(MSYS_NO_PATHCONV=1 docker run --rm -v "$DEST:/in:ro" alpine tar -tzf "/in/litstorm-runs-$STAMP.tar.gz" | grep -c 'report.json$' || true) reports"
    ;;

  --restore)
    STAMP="${2:?usage: --restore <stamp> [dest-dir]}"; DEST=$(dest_dir "${3:-}")
    DUMP="$DEST/litstorm-$STAMP.dump"; TAR="$DEST/litstorm-runs-$STAMP.tar.gz"
    [ -s "$DUMP" ] && [ -s "$TAR" ] || { echo "!! no backup $STAMP in $DEST" >&2; exit 1; }
    WORKER=$(container worker)
    VOLUME=$(volume_of "$WORKER" /data)
    [ -n "$VOLUME" ] || { echo "!! the worker has no volume at /data" >&2; exit 1; }
    want=$(grep '^secret_key_fingerprint=' "$DEST/litstorm-$STAMP.manifest" | cut -d= -f2)
    have=$(fingerprint)
    if [ "$want" != "$have" ]; then
      echo "  !! the dump was taken with secret_key $want; this stack has $have —"
      echo "     stored API keys will not decrypt and must be entered again under Settings"
    fi
    echo "== restore $STAMP into '$PROJECT' (its current data is replaced) =="
    for svc in web worker api; do c=$(container "$svc"); [ -z "$c" ] || docker stop "$c" >/dev/null; done
    echo "  stopped api, worker, web"
    MSYS_NO_PATHCONV=1 docker run --rm -v "$VOLUME:/d" -v "$DEST:/in:ro" alpine \
      sh -c "find /d -mindepth 1 -delete && tar -C /d -xzf /in/$(basename "$TAR")"
    echo "  volume $VOLUME restored"
    docker exec -i "$DB" pg_restore -U litstorm -d litstorm --clean --if-exists --no-owner < "$DUMP"
    echo "  database restored ($(tables_in "$DUMP") tables with data)"
    for svc in api worker web; do c=$(container "$svc"); [ -z "$c" ] || docker start "$c" >/dev/null; done
    echo "  started api, worker, web — done"
    ;;

  *)
    DEST=$(dest_dir "${1:-}")
    STAMP="$(date +%Y%m%d-%H%M%S)"
    WORKER=$(container worker)
    VOLUME=$(volume_of "$WORKER" /data)
    [ -n "$VOLUME" ] || { echo "!! the worker has no volume at /data" >&2; exit 1; }
    echo "== lit-storm backup $STAMP ('$PROJECT') → $DEST =="

    DUMP="$DEST/litstorm-$STAMP.dump"
    docker exec "$DB" pg_dump -U litstorm -d litstorm -Fc > "$DUMP"
    echo "  database  $(du -h "$DUMP" | cut -f1)"

    TAR="$DEST/litstorm-runs-$STAMP.tar.gz"
    MSYS_NO_PATHCONV=1 docker run --rm -v "$VOLUME:/d:ro" -v "$DEST:/out" alpine \
      tar -C /d --exclude ./search-cache -czf "/out/$(basename "$TAR")" .
    [ -s "$TAR" ] || { echo "!! $TAR was not written" >&2; exit 1; }
    echo "  run files $(du -h "$TAR" | cut -f1)  (volume $VOLUME)"

    # A dump pg_restore cannot list is not a backup.
    TABLES=$(tables_in "$DUMP")
    [ "$TABLES" -gt 0 ] || { echo "!! $DUMP lists no table data — not counted as a backup" >&2; exit 1; }
    {
      echo "stamp=$STAMP"
      echo "project=$PROJECT"
      echo "image=$(docker inspect "$WORKER" --format '{{.Config.Image}}')"
      echo "tables=$TABLES"
      echo "runs=$(docker exec "$DB" psql -U litstorm -tAc 'select count(*) from runs')"
      echo "secret_key_fingerprint=$(fingerprint)"
    } > "$DEST/litstorm-$STAMP.manifest"
    echo "  verified  $TABLES tables with data"

    if [ "$KEEP_DAYS" -gt 0 ]; then
      pruned=$(find "$DEST" -maxdepth 1 -type f -name 'litstorm-*' -mtime +"$KEEP_DAYS" -print -delete | wc -l)
      echo "  pruned    $pruned file(s) older than $KEEP_DAYS days"
    fi
    echo "done: $STAMP"
    ;;
esac
