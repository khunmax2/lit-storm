#!/bin/sh
# Refuses a .env that would deploy and then fail quietly: a key left empty or
# as the CHANGE_ME of deploy/aiforthai/env.example, or two lines run together.
# Checks shapes only and prints names, never a value (the job log is readable
# by every member of the project).
#
#   sh deploy/aiforthai/check-env.sh .env
set -eu
env_file="${1:-.env}"
[ -s "$env_file" ] || { echo "!! $env_file is missing or empty (is ENV_FILE set, Protected, for this branch?)"; exit 1; }

failed=0
for v in COMPOSE_PROJECT_NAME DATA_PATH APP_PORT PUBLIC_URL \
         LITSTORM_SECRET_KEY LITSTORM_BOOTSTRAP_CODE DEEPLIT_DB_PASSWORD SEARXNG_SECRET \
         MRA_DB_PASSWORD MRA_SEARXNG_SECRET MRA_IP_HASH_SALT MRA_OPENROUTER_API_KEY MRA_SERVICE_API_KEY; do
  value=$(sed -n "s/^$v=//p" "$env_file" | tail -n 1)
  case "$value" in
    "") echo "!! $v is empty or missing"; failed=1 ;;
    *CHANGE_ME*) echo "!! $v is still CHANGE_ME from env.example"; failed=1 ;;
    *LITSTORM_*=*|*DEEPLIT_*=*|*SEARXNG_*=*|*MRA_*=*|*DATA_PATH=*|*APP_PORT=*|*PUBLIC_URL=*|*COMPOSE_PROJECT_NAME=*)
      echo "!! $v has swallowed the line after it: add a newline between them"; failed=1 ;;
    \"*|\'*) echo "!! $v is quoted: write the value bare"; failed=1 ;;
  esac
done
case "$(sed -n 's/^MRA_SERVICE_API_KEY=//p' "$env_file")" in
  mra_*) ;;
  *) echo "!! MRA_SERVICE_API_KEY must start with mra_"; failed=1 ;;
esac
case "$(sed -n 's/^DATA_PATH=//p' "$env_file")" in
  /*|[A-Za-z]:/*) ;;  # the second: a Windows rehearsal of this stack
  *) echo "!! DATA_PATH must be an absolute path on the host"; failed=1 ;;
esac
[ "$failed" = 0 ] && echo "env: every required key is set"
exit "$failed"
