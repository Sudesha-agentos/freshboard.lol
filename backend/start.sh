#!/usr/bin/env bash
# Render start command: bash start.sh
set -euo pipefail
cd "$(dirname "$0")"

load_kv() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if [[ "$line" == *=* ]]; then
      key="${line%%=*}"
      val="${line#*=}"
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      export "$key=$val"
    fi
  done < "$f"
}

load_kv .env
load_kv atlas-credentials.env
load_kv /etc/secrets/.env
load_kv /etc/secrets/atlas-credentials.env

if [[ -d /etc/secrets ]]; then
  for name in MONGO_URL MONGODB_URI MONGODB_USERNAME MONGODB_PASSWORD DB_NAME; do
    if [[ -f "/etc/secrets/$name" && -z "${!name:-}" ]]; then
      export "$name=$(tr -d '\r\n' < "/etc/secrets/$name")"
    fi
  done
fi

export DB_NAME="${DB_NAME:-freshboard}"
export MONGO_URL="${MONGO_URL:-${MONGODB_URI:-}}"

exec gunicorn your_application.wsgi --bind "0.0.0.0:${PORT:-10000}"
