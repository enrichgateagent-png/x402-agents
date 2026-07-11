#!/usr/bin/env bash
# Export the remote Turso database to data_backup.sql before decommissioning.
# Run on any machine with Turso CLI access:  bash scripts/export_turso_backup.sh
set -euo pipefail

DB_NAME="${TURSO_DB_NAME:-}"
OUT="${1:-data_backup.sql}"

if ! command -v turso >/dev/null 2>&1; then
  echo "Installing Turso CLI..."
  curl -sSfL https://get.tur.so/install.sh | bash
  export PATH="$HOME/.turso:$PATH"
fi

if [[ -z "$DB_NAME" ]]; then
  echo "Available Turso databases:"
  turso db list
  echo ""
  read -r -p "Enter Turso database name: " DB_NAME
fi

echo "==> Dumping Turso database '$DB_NAME' to $OUT"
turso db shell "$DB_NAME" ".dump" \
  | grep -v '^PRAGMA foreign_keys' \
  | grep -v '^BEGIN TRANSACTION' \
  | grep -v '^COMMIT' \
  > "$OUT"

ROWS=$(grep -c '^INSERT INTO' "$OUT" || true)
echo "==> Done. INSERT statements: $ROWS"
echo "==> Upload to GCP VM:"
echo "    scp $OUT gcp_user@YOUR_GCP_VM_IP:~/"
