#!/usr/bin/env bash
# ============================================
# Back up MedicalReviewerAgent's database on host 203, or restore it
# (docs/deploy/HOST-203.md, §M). Beside stack/backup.sh, which backs up
# lit-storm's; the same directory and the same 30 days.
#
#   bash stack/mra/backup-mra.sh [dest-dir]                  default ../_litstorm_backup
#   bash stack/mra/backup-mra.sh --restore <stamp> [dest-dir]
#
#   PROJECT=mra      the Compose project MRA runs as
#   KEEP_DAYS=30
#
# One file per stamp: mra-<stamp>.dump (pg_dump -Fc): reviews, cached
# results, the admin console's settings, and the LLM keys entered there,
# encrypted with LLM_KEYS_SECRET from MRA's .env. That secret is not in the
# backup, on purpose; keep a copy of MRA's .env off the host (§M).
# Redis is not backed up: a lost queue costs the reviews in flight, and the
# day's spend counter starts again.
#
# Restore stops MRA's api and worker, replaces the database, and starts them.
# ============================================
set -euo pipefail

PROJECT="${PROJECT:-mra}"
KEEP_DAYS="${KEEP_DAYS:-30}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

container() {
  docker ps -a --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$1" --format '{{.Names}}' | head -1
}
DB=$(container postgres)
[ -n "$DB" ] || { echo "!! no postgres container in Compose project '$PROJECT' (set PROJECT=...)" >&2; exit 1; }

tables_in() { docker exec -i "$DB" pg_restore --list < "$1" | grep -c 'TABLE DATA' || true; }

if [ "${1:-}" = "--restore" ]; then
  STAMP="${2:?usage: backup-mra.sh --restore <stamp> [dest-dir]}"
  DEST="${3:-$HERE/../../../_litstorm_backup}"
  DUMP="$DEST/mra-$STAMP.dump"
  [ -s "$DUMP" ] || { echo "!! $DUMP is missing or empty" >&2; exit 1; }
  echo "== restore $STAMP into '$PROJECT' (its current data is replaced) =="
  for s in api worker; do c=$(container "$s"); [ -z "$c" ] || docker stop "$c" >/dev/null; done
  docker exec -i "$DB" pg_restore -U mra -d mra --clean --if-exists --no-owner < "$DUMP"
  for s in worker api; do c=$(container "$s"); [ -z "$c" ] || docker start "$c" >/dev/null; done
  echo "restored: $(tables_in "$DUMP") tables"
  exit 0
fi

DEST="${1:-$HERE/../../../_litstorm_backup}"
mkdir -p "$DEST"
# The same stamp as stack/backup.sh (local time), so one night's two backups sort and read alike.
STAMP="$(date +%Y%m%d-%H%M%S)"
DUMP="$DEST/mra-$STAMP.dump"
echo "== MRA backup $STAMP ('$PROJECT') → $DEST =="
docker exec "$DB" pg_dump -U mra -d mra -Fc > "$DUMP"
n=$(tables_in "$DUMP")
# A dump with no tables in it is not a backup.
[ "$n" -gt 0 ] || { echo "!! $DUMP holds no tables; not kept" >&2; rm -f "$DUMP"; exit 1; }
echo "database: $(du -h "$DUMP" | cut -f1), $n tables"
find "$DEST" -name 'mra-*.dump' -mtime +"$KEEP_DAYS" -print -delete
