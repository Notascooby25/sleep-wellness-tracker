#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

# Load only needed keys from env file.
POSTGRES_USER=""
POSTGRES_PASSWORD=""
POSTGRES_DB=""
DATABASE_URL=""

while IFS='=' read -r key value; do
  [[ -z "$key" ]] && continue
  [[ "$key" =~ ^# ]] && continue
  case "$key" in
    POSTGRES_USER) POSTGRES_USER="$value" ;;
    POSTGRES_PASSWORD) POSTGRES_PASSWORD="$value" ;;
    POSTGRES_DB) POSTGRES_DB="$value" ;;
    DATABASE_URL) DATABASE_URL="$value" ;;
  esac
done < "$ENV_FILE"

if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL is missing in $ENV_FILE"
  exit 1
fi

# Parse DATABASE_URL: postgresql://user:pass@host:port/db
url_no_proto="${DATABASE_URL#*://}"
creds="${url_no_proto%%@*}"
rest="${url_no_proto#*@}"
url_user="${creds%%:*}"
url_pass="${creds#*:}"
url_db="${rest#*/}"
url_db="${url_db%%\?*}"

ok=true

if [[ "$POSTGRES_USER" != "$url_user" ]]; then
  echo "Mismatch: POSTGRES_USER and DATABASE_URL user differ"
  ok=false
fi

if [[ "$POSTGRES_PASSWORD" != "$url_pass" ]]; then
  echo "Mismatch: POSTGRES_PASSWORD and DATABASE_URL password differ"
  ok=false
fi

if [[ "$POSTGRES_DB" != "$url_db" ]]; then
  echo "Mismatch: POSTGRES_DB and DATABASE_URL db differ"
  ok=false
fi

if [[ "$ok" == true ]]; then
  echo "Credentials look consistent between POSTGRES_* and DATABASE_URL."
else
  cat <<'MSG'
If this is a local-only environment and DB auth still fails, your persisted postgres volume may contain older credentials.
Options:
1) Keep data: update postgres role password inside the running db to match .env.
2) Reset local DB volume (destructive):
   docker compose down
   docker volume rm sleep-wellness-tracker_db_data
   docker compose up -d db backend
MSG
  exit 2
fi
