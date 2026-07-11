#!/usr/bin/env bash
# Deploy Beacon from THIS machine's local repo copy (includes SQLite migration).
# Usage:
#   export GCP_VM_IP=34.45.7.252
#   export GCP_USER=aareej
#   export SSH_KEY=~/.ssh/pumpfun_vps
#   bash scripts/deploy_from_local.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

GCP_VM_IP="${GCP_VM_IP:?set GCP_VM_IP}"
GCP_USER="${GCP_USER:-areej}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/pumpfun_vps}"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new)

echo ">>> [1/4] Upload beacon.db"
scp "${SSH_OPTS[@]}" "/mnt/c/Users/Falcon/Downloads/beacon.db" "${GCP_USER}@${GCP_VM_IP}:~/beacon.db"

echo ">>> [2/4] Sync local repo to VM (registry + mcp + scripts)"
ssh "${SSH_OPTS[@]}" "${GCP_USER}@${GCP_VM_IP}" "mkdir -p ~/x402-agents"
tar czf - -C "$REPO_DIR" \
  --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='registry/beacon_prod.db' \
  . | ssh "${SSH_OPTS[@]}" "${GCP_USER}@${GCP_VM_IP}" "tar xzf - -C ~/x402-agents"

echo ">>> [3/4] Run GCP deploy on VM"
ssh "${SSH_OPTS[@]}" "${GCP_USER}@${GCP_VM_IP}" \
  "GCP_VM_IP=$GCP_VM_IP REPO_DIR=\$HOME/x402-agents bash -s" < "$SCRIPT_DIR/gcp_deploy.sh"

echo ">>> [4/4] Verify"
curl -fsS "http://${GCP_VM_IP}:8000/healthz" || echo "(open firewall for 8000/8001 if curl fails)"
echo ""
echo "Registry: http://${GCP_VM_IP}:8000/healthz"
echo "Glama SSE: http://${GCP_VM_IP}:8001/sse"
