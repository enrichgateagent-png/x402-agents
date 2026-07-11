#!/usr/bin/env bash
# Full migration orchestrator — run locally before Turso access is lost.
# Prerequisites: turso auth login
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

GCP_VM_IP="${GCP_VM_IP:-}"
GCP_USER="${GCP_USER:-gcp_user}"
SSH_KEY="${SSH_KEY:-}"

if ! command -v turso >/dev/null 2>&1; then
  export PATH="$HOME/.turso:$PATH"
fi

if [[ -f "/mnt/c/Users/Falcon/Downloads/beacon.db" ]] || [[ -f "$REPO_DIR/registry/beacon_prod.db" ]]; then
  echo "=== Step 1: Skipping Turso export (beacon.db already available) ==="
else
  echo "=== Step 1: Export Turso database ==="
  bash "$SCRIPT_DIR/export_turso_backup.sh" "$REPO_DIR/data_backup.sql"
fi

if [[ -z "$GCP_VM_IP" ]]; then
  read -r -p "GCP VM external IP: " GCP_VM_IP
fi

echo "=== Step 2: Upload database to VM ==="
SCP_CMD=(scp)
[[ -n "$SSH_KEY" ]] && SCP_CMD+=(-i "$SSH_KEY")

if [[ -f "/mnt/c/Users/Falcon/Downloads/beacon.db" ]]; then
  echo "Using Windows download: beacon.db"
  "${SCP_CMD[@]}" "/mnt/c/Users/Falcon/Downloads/beacon.db" "${GCP_USER}@${GCP_VM_IP}:~/beacon.db"
elif [[ -f "$REPO_DIR/registry/beacon_prod.db" ]]; then
  echo "Using project copy: registry/beacon_prod.db"
  "${SCP_CMD[@]}" "$REPO_DIR/registry/beacon_prod.db" "${GCP_USER}@${GCP_VM_IP}:~/beacon.db"
elif [[ -f "$REPO_DIR/data_backup.sql" ]]; then
  "${SCP_CMD[@]}" "$REPO_DIR/data_backup.sql" "${GCP_USER}@${GCP_VM_IP}:~/"
else
  echo "No beacon.db or data_backup.sql found — export Turso first or place beacon.db in Downloads."
  exit 1
fi

echo ""
echo "=== Step 3: Deploy on VM ==="
SSH_CMD=(ssh)
[[ -n "$SSH_KEY" ]] && SSH_CMD+=(-i "$SSH_KEY")
SSH_CMD+=("${GCP_USER}@${GCP_VM_IP}" "GCP_VM_IP=$GCP_VM_IP bash -s")
"${SSH_CMD[@]}" < "$SCRIPT_DIR/gcp_deploy.sh"

echo ""
echo "=== Migration complete ==="
echo "Registry: http://$GCP_VM_IP:8000/healthz"
echo "Glama SSE: http://$GCP_VM_IP:8001/sse"
