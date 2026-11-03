#!/bin/sh
# Waits until every container of the stack is healthy (or running, where it has
# no health check; or exited 0, the one-shot ones), up to 15 minutes. On a
# failure prints that container's last log lines; they hold no secret (the
# services never log their environment).
#
#   sh deploy/aiforthai/wait-healthy.sh "docker compose -f deploy/aiforthai/compose.yml --env-file .env"
set -eu
compose="$1"
deadline=$(( $(date +%s) + 900 ))
while :; do
  pending=""
  failed=""
  for id in $($compose ps -a -q); do
    name=$(docker inspect --format '{{.Name}}' "$id" | sed 's#^/##')
    state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")
    code=$(docker inspect --format '{{.State.ExitCode}}' "$id")
    case "$state" in
      healthy|running) ;;
      exited) [ "$code" = 0 ] || failed="$failed $name" ;;
      unhealthy|dead) failed="$failed $name" ;;
      *) pending="$pending $name($state)" ;;
    esac
  done
  if [ -n "$failed" ]; then
    for name in $failed; do echo "!! $name failed"; docker logs --tail 60 "$name" 2>&1 || true; done
    exit 1
  fi
  [ -z "$pending" ] && { echo "every container is up"; exit 0; }
  [ "$(date +%s)" -ge "$deadline" ] && { echo "!! still not up after 15 minutes:$pending"; exit 1; }
  echo "waiting:$pending"
  sleep 10
done
