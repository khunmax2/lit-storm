#!/usr/bin/env bash
# ============================================
# nginx for lit-storm at /litstorm on host 203 — run with sudo.
# Modelled on DeepWitya's deploy/apply-nginx-golive.sh, which runs on the
# same host and the same shared files (docs/deploy/HOST-203.md).
#
#   sudo bash stack/host/apply-nginx.sh --preview [app-port] [preview-port]
#       A loopback-only HTTPS server on 127.0.0.1:<preview-port> (default
#       9443) serving the stack at /litstorm with the host's certificate.
#       Nothing on :443 changes. From your machine:
#           ssh -L 18443:127.0.0.1:<preview-port> search@203.185.144.41
#           https://localhost:18443/litstorm/
#       Refuses a port something already listens on (8443 is a Kong gateway
#       of another application — measured by DeepWitya, 2026-09-11) and
#       checks nginx really listens after the reload: a taken port passes
#       `nginx -t`, fails at reload, and leaves nginx on its old config.
#
#   sudo bash stack/host/apply-nginx.sh --install [app-port]
#       Goes live. :443 gets one `include` of a snippet this project owns
#       (location /litstorm/ → 127.0.0.1:<app-port>); :80 gets one `include`
#       of a snippet that redirects /litstorm to HTTPS (the session cookie is
#       Secure, so a login over plain HTTP would never stick). Refuses if
#       either server already has a /litstorm location of someone else's.
#
#   sudo bash stack/host/apply-nginx.sh --uninstall
#       Takes both includes out again; the stack keeps running.
#
#   sudo bash stack/host/apply-nginx.sh --remove-preview
#
#   bash stack/host/apply-nginx.sh --check [app-port]      (no sudo)
#       Reports what is installed and whether the app answers.
#
# Every change: back up the shared files (timestamped, beside them), edit,
# `nginx -t`; on any failure put the backups back and exit WITHOUT reloading,
# so nginx keeps serving its current config. The shared files belong to other
# applications too; the only edit made to them is one include line each.
#
# Paths and commands can be overridden for a rehearsal off the host:
#   SSL HTTP SNIPPETS AVAILABLE ENABLED NGINX_TEST NGINX_RELOAD ALLOW_NON_ROOT
# ============================================
set -euo pipefail

SSL="${SSL:-/etc/nginx/sites-available/sansarnnews-ssl}"   # :443, server_name 203.185.144.41
HTTP="${HTTP:-/etc/nginx/sites-available/ade}"             # :80,  server_name _
SNIPPETS="${SNIPPETS:-/etc/nginx/snippets}"
AVAILABLE="${AVAILABLE:-/etc/nginx/sites-available}"
ENABLED="${ENABLED:-/etc/nginx/sites-enabled}"
NGINX_TEST="${NGINX_TEST:-nginx -t}"
NGINX_RELOAD="${NGINX_RELOAD:-systemctl reload nginx}"
SNIP_SSL="$SNIPPETS/litstorm.conf"
SNIP_HTTP="$SNIPPETS/litstorm-http.conf"
PREVIEW="$AVAILABLE/litstorm-preview"
PREVIEW_LINK="$ENABLED/litstorm-preview"
MARK="# lit-storm — see stack/host/apply-nginx.sh"
STAMP=$(date +%Y%m%d-%H%M%S)
CLEANUP_ON_FAIL=""

listening() { # is anything listening on <port>
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$1$"
  else
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$1$"
  fi
}

has_include() { grep -qF "include $2;" "$1"; }

# A /litstorm location in a shared file that is not ours: someone else's.
foreign_location() { grep -nE '^[[:space:]]*location[[:space:]]+(=[[:space:]]*)?/litstorm' "$1" || true; }

location_block() { # app-port
  cat <<CONF
location = /litstorm { return 301 /litstorm/; }

# The app is built for /litstorm and serves under it: the path is passed on
# as it is (no URI on proxy_pass).
location /litstorm/ {
    proxy_pass http://127.0.0.1:$1;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 120s;
    # Nothing is uploaded; forms and settings are small.
    client_max_body_size 1m;
}
CONF
}

if [ "${1:-}" = "--check" ]; then
  PORT="${2:-10340}"
  echo "== lit-storm nginx: check (no changes) =="
  for f in "$SSL:$SNIP_SSL" "$HTTP:$SNIP_HTTP"; do
    file=${f%%:*}; snip=${f#*:}
    if has_include "$file" "$snip"; then echo "  $file: includes $snip"; else echo "  $file: not installed"; fi
    foreign=$(foreign_location "$file"); [ -z "$foreign" ] || echo "  $file: has its own /litstorm location: $foreign"
  done
  [ -f "$PREVIEW" ] && echo "  preview: $(grep -oE 'listen 127\.0\.0\.1:[0-9]+' "$PREVIEW")" || echo "  preview: none"
  if listening "$PORT"; then echo "  app: something listens on $PORT"; else echo "  app: nothing listens on $PORT"; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/litstorm/api/health" || true)
  echo "  app: /litstorm/api/health → $code"
  exit 0
fi

[ "$(id -u)" -eq 0 ] || [ -n "${ALLOW_NON_ROOT:-}" ] || { echo "run with sudo" >&2; exit 1; }

backup() { cp -a "$1" "$1.bak-$STAMP"; echo "  backup: $1.bak-$STAMP"; }

restore() {
  echo "!! nginx -t failed — putting everything back" >&2
  [ -f "$SSL.bak-$STAMP" ] && mv -f "$SSL.bak-$STAMP" "$SSL"
  [ -f "$HTTP.bak-$STAMP" ] && mv -f "$HTTP.bak-$STAMP" "$HTTP"
  # shellcheck disable=SC2086
  [ -n "$CLEANUP_ON_FAIL" ] && rm -f $CLEANUP_ON_FAIL
  echo "   restored; nginx was never reloaded and serves its old config" >&2
  exit 1
}

test_and_reload() {
  echo "== nginx -t =="
  $NGINX_TEST || restore
  echo "== reload =="
  $NGINX_RELOAD
}

add_include() { # file snippet — one line before the file's last closing brace
  python3 - "$1" "$2" "$MARK" <<'PY'
import sys
path, snip, mark = sys.argv[1:]
s = open(path, encoding="utf-8").read()
if f"include {snip};" in s:
    print(f"  {path}: already includes {snip}")
    sys.exit(0)
i = s.rstrip().rfind("}")
assert i != -1, f"{path}: no closing brace"
open(path, "w", encoding="utf-8").write(s[:i] + f"\n    {mark}\n    include {snip};\n" + s[i:])
print(f"  {path}: + include {snip}")
PY
}

remove_include() { # file snippet
  python3 - "$1" "$2" "$MARK" <<'PY'
import re, sys
path, snip, mark = sys.argv[1:]
s = open(path, encoding="utf-8").read()
# Exactly what add_include put in, so the file comes back byte for byte.
s2 = re.sub(r"\n *" + re.escape(mark) + r"\n *include " + re.escape(snip) + r";\n", "", s)
open(path, "w", encoding="utf-8").write(s2)
print(f"  {path}: {'include removed' if s2 != s else 'no include to remove'}")
PY
}

case "${1:-}" in
  --preview)
    PORT="${2:-10340}"
    PP="${3:-9443}"
    echo "== preview: https://127.0.0.1:$PP/litstorm/ → 127.0.0.1:$PORT =="
    if [ -f "$PREVIEW" ] && grep -q "listen 127.0.0.1:$PP " "$PREVIEW"; then
      echo "  our preview already on $PP — rewriting it"
    elif listening "$PP"; then
      echo "!! port $PP is taken on this host — choose another: --preview $PORT <port>" >&2
      exit 1
    fi
    listening "$PORT" || echo "  !! nothing listens on $PORT yet — start the stack first (HOST-203.md §3)"
    CERT=$(grep -E '^[[:space:]]*ssl_certificate(_key)?[[:space:]]' "$SSL" | head -2)
    [ -n "$CERT" ] || { echo "no ssl_certificate in $SSL" >&2; exit 1; }
    {
      echo "# lit-storm PREVIEW — loopback only, reached through an SSH tunnel."
      echo "# Remove after going live: stack/host/apply-nginx.sh --remove-preview"
      echo "server {"
      echo "    listen 127.0.0.1:$PP ssl;"
      echo "    server_name 203.185.144.41 localhost;"
      printf '%s\n' "$CERT" | sed 's/^[[:space:]]*/    /'
      location_block "$PORT" | sed 's/^/    /'
      echo "}"
    } > "$PREVIEW"
    ln -sf "$PREVIEW" "$PREVIEW_LINK"
    CLEANUP_ON_FAIL="$PREVIEW $PREVIEW_LINK"
    test_and_reload
    sleep 1
    listening "$PP" || { echo "!! reloaded, but nginx does not listen on $PP — remove it: --remove-preview" >&2; exit 1; }
    echo "done — from your machine: ssh -L 18443:127.0.0.1:$PP search@203.185.144.41"
    echo "       then https://localhost:18443/litstorm/ (the certificate is the IP's: accept the warning)"
    ;;

  --install)
    PORT="${2:-10340}"
    echo "== install: :443 /litstorm/ → 127.0.0.1:$PORT, :80 /litstorm → https =="
    for file in "$SSL" "$HTTP"; do
      foreign=$(foreign_location "$file")
      [ -z "$foreign" ] || { echo "!! $file already has a /litstorm location (line $foreign) — not ours, stopping" >&2; exit 1; }
    done
    listening "$PORT" || { echo "!! nothing listens on $PORT — start the stack first (HOST-203.md §3)" >&2; exit 1; }
    backup "$SSL"; backup "$HTTP"
    { echo "$MARK"; location_block "$PORT"; } > "$SNIP_SSL"
    cat > "$SNIP_HTTP" <<CONF
$MARK
# The session cookie is Secure: over plain HTTP a login would never stick.
location /litstorm { return 301 https://\$host\$request_uri; }
CONF
    echo "  wrote $SNIP_SSL, $SNIP_HTTP"
    add_include "$SSL" "$SNIP_SSL"
    add_include "$HTTP" "$SNIP_HTTP"
    test_and_reload
    echo "done — https://203.185.144.41/litstorm/ ; back out: --uninstall"
    ;;

  --uninstall)
    echo "== uninstall: both includes out; the stack keeps running =="
    backup "$SSL"; backup "$HTTP"
    remove_include "$SSL" "$SNIP_SSL"
    remove_include "$HTTP" "$SNIP_HTTP"
    test_and_reload
    rm -f "$SNIP_SSL" "$SNIP_HTTP"
    echo "done — /litstorm is served by nobody again"
    ;;

  --remove-preview)
    rm -f "$PREVIEW_LINK" "$PREVIEW"
    $NGINX_TEST && $NGINX_RELOAD && echo "preview removed"
    ;;

  *)
    sed -n '2,/^# Every change:/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
