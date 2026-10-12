#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p backups
chmod 700 backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="nexora-postgres-${stamp}.nxb"
container_path="/var/nexora/backups/${archive}"

# The custom-format dump is streamed directly into the app container's
# AES-256-GCM encryptor. Plaintext is never written to the host filesystem.
# The encrypted archive is staged in an app-owned named volume, then copied out.
docker compose exec -T db sh -c 'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | docker compose exec -T app python -m app.backup encrypt --output "$container_path"

docker compose cp "app:${container_path}" "backups/${archive}"
chmod 600 "backups/${archive}"
printf 'Encrypted database backup created: backups/%s\n' "$archive"
printf 'Copy it off-site only with the decryption key stored separately.\n'
