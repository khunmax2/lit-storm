#!/bin/sh
# Create the stack's two secrets, once. Existing ones are kept: replacing
# secret_key would make every stored API key unreadable.
set -eu
cd "$(dirname "$0")"
mkdir -p secrets

if [ ! -s secrets/secret_key ]; then
  # A Fernet key: 32 random bytes, URL-safe base64.
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' > secrets/secret_key
  echo "created secrets/secret_key — back it up; without it stored API keys cannot be read"
fi

if [ ! -s secrets/bootstrap_code ]; then
  head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' > secrets/bootstrap_code
  echo "created secrets/bootstrap_code — enter it on the first-run setup page"
fi
