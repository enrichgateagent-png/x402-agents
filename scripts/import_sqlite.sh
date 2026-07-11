#!/usr/bin/env bash
# Import data_backup.sql into the local SQLite database on the GCP VM.
set -euo pipefail

DB_PATH="${SQLITE_DB_PATH:-/home/gcp_user/beacon_prod.db}"
BACKUP="${1:-$HOME/data_backup.sql}"

if [[ ! -f "$BACKUP" ]]; then
  echo "ERROR: backup file not found: $BACKUP"
  exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"
echo "==> Importing $BACKUP into $DB_PATH"
sqlite3 "$DB_PATH" < "$BACKUP"

if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='agents';" | grep -q agents; then
  COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM agents;")
  echo "==> Import complete — $COUNT agent rows"
else
  echo "==> Import finished (agents table not found — schema will be created on first API start)"
fi
