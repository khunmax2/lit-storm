#!/usr/bin/env bash
# ============================================
# Rehearse stack/host/apply-nginx.sh against a copy of host 203's layout,
# off the host (docs/deploy/HOST-203.md §0: "measure, don't guess" — this is
# the part that can be measured here).
#
#   bash stack/host/rehearse-nginx.sh <web-container>
#
# Runs an nginx container inside <web-container>'s network namespace, so
# 127.0.0.1:80 is the lit-storm web image as the host's nginx would reach it
# on its published port. Inside it: a :443 server (here 8443, self-signed)
# holding another app's /deepwitya, a :80 server (here 8080), and the script
# run through every mode, including an `nginx -t` that fails. Changes
# nothing outside the throwaway container.
# ============================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
WEB="${1:?usage: rehearse-nginx.sh <web-container>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"

docker run --rm -i --network "container:$WEB" -v "$HERE:/lit:ro" nginx:1.29-alpine sh -s <<'REHEARSAL'
set -eu
apk add -q --no-cache bash python3 curl iproute2 openssl >/dev/null
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/snippets /etc/ssl/rehearsal
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=203.185.144.41 \
  -keyout /etc/ssl/rehearsal/key.pem -out /etc/ssl/rehearsal/cert.pem 2>/dev/null
rm -f /etc/nginx/conf.d/default.conf
echo 'include /etc/nginx/sites-enabled/*;' > /etc/nginx/conf.d/sites.conf
cat > /etc/nginx/sites-available/sansarnnews-ssl <<'CONF'
server {
    listen 8443 ssl;
    server_name 203.185.144.41;
    ssl_certificate /etc/ssl/rehearsal/cert.pem;
    ssl_certificate_key /etc/ssl/rehearsal/key.pem;

    location /deepwitya {
        return 200 "deepwitya\n";
    }
}
CONF
cat > /etc/nginx/sites-available/ade <<'CONF'
server {
    listen 8080;
    server_name _;
    location /deepwitya {
        return 301 https://$host$request_uri;
    }
}
CONF
ln -s /etc/nginx/sites-available/sansarnnews-ssl /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/ade /etc/nginx/sites-enabled/
cp /etc/nginx/sites-available/sansarnnews-ssl /tmp/ssl.orig
cp /etc/nginx/sites-available/ade /tmp/http.orig
nginx

export ALLOW_NON_ROOT=1 NGINX_RELOAD="nginx -s reload"
S="bash /lit/apply-nginx.sh"
fails=0
check() { if eval "$2"; then echo "  ✓ $1"; else echo "  ✗ $1"; fails=$((fails+1)); fi; }
code() { curl -sk -o /dev/null -w '%{http_code}' "$1"; }

echo "== --check before anything =="; $S --check 80
echo "== --preview on a taken port (8443, the :443 server here) =="
check "refused" "! $S --preview 80 8443 >/tmp/out 2>&1"
check "no preview file left" "[ ! -e /etc/nginx/sites-available/litstorm-preview ]"
echo "== --preview 80 9443 =="; $S --preview 80 9443 >/tmp/out 2>&1 || cat /tmp/out
sleep 1
check "preview serves the app: /litstorm/api/health 200" "[ \$(code https://127.0.0.1:9443/litstorm/api/health) = 200 ]"
check "preview redirects /litstorm → /litstorm/" "[ \$(code https://127.0.0.1:9443/litstorm) = 301 ]"
check ":443 untouched: /litstorm 404 there" "[ \$(code https://127.0.0.1:8443/litstorm/api/health) = 404 ]"

echo "== --install with nginx -t failing =="
check "refused and restored" "! NGINX_TEST=false $S --install 80 >/tmp/out 2>&1"
check ":443 file byte-for-byte as before" "cmp -s /tmp/ssl.orig /etc/nginx/sites-available/sansarnnews-ssl"
check ":80 file byte-for-byte as before" "cmp -s /tmp/http.orig /etc/nginx/sites-available/ade"

echo "== --install 80 =="; $S --install 80 >/tmp/out 2>&1 || cat /tmp/out
sleep 1
check ":443 /litstorm/api/health 200" "[ \$(code https://127.0.0.1:8443/litstorm/api/health) = 200 ]"
check ":443 /litstorm/ serves the page" "curl -sk https://127.0.0.1:8443/litstorm/ | grep -q '<!doctype html>'"
# $host carries no port: on the host both servers are on the default ports.
check ":80 /litstorm → 301 https" "curl -sI http://127.0.0.1:8080/litstorm/ | grep -qiE '^location: https://127\.0\.0\.1/litstorm/'"
check "the other app still answers" "[ \"\$(curl -sk https://127.0.0.1:8443/deepwitya)\" = deepwitya ]"
check "one include line each" "[ \$(grep -c 'include /etc/nginx/snippets/litstorm' /etc/nginx/sites-available/sansarnnews-ssl) = 1 ] && [ \$(grep -c 'include /etc/nginx/snippets/litstorm' /etc/nginx/sites-available/ade) = 1 ]"
check "a second --install adds nothing" "$S --install 80 >/tmp/out 2>&1 && [ \$(grep -c 'include /etc/nginx/snippets/litstorm' /etc/nginx/sites-available/sansarnnews-ssl) = 1 ]"
echo "== --check installed =="; $S --check 80

echo "== --uninstall =="; $S --uninstall >/tmp/out 2>&1 || cat /tmp/out
sleep 1
check ":443 file back as it was" "cmp -s /tmp/ssl.orig /etc/nginx/sites-available/sansarnnews-ssl"
check ":80 file back as it was" "cmp -s /tmp/http.orig /etc/nginx/sites-available/ade"
check "/litstorm served by nobody" "[ \$(code https://127.0.0.1:8443/litstorm/api/health) = 404 ]"
echo "== --remove-preview =="; $S --remove-preview >/tmp/out 2>&1
sleep 1
check "preview gone" "! ss -ltn | grep -q ':9443 '"

[ "$fails" = 0 ] && echo "REHEARSAL PASSED" || { echo "REHEARSAL FAILED: $fails"; exit 1; }
REHEARSAL
