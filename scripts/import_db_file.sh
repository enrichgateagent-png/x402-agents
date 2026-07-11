#!/usr/bin/env bash
# Copy a downloaded Turso SQLite file (.db) into the production database path.
# Usage:
#   bash scripts/import_db_file.sh /path/to/beacon.db
#   bash scripts/import_db_file.sh "/mnt/c/Users/Falcon/Downloads/beacon.db"
set -euo pipefail

SRC="${1:-/mnt/c/Users/Falcon/Downloads/beacon.db}"
DEST="${SQLITE_DB_PATH:-/home/gcp_user/beacon_prod.db}"

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: source database not found: $SRC"
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
cp "$SRC" "$DEST"

python3 <<PY
import sqlite3
conn = sqlite3.connect("$DEST")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
conn.close()
print(f"==> Imported {count:,} agents into $DEST")
PY
