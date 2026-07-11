#!/usr/bin/env bash
# Fast deploy: sync registry Python files + restart PM2 (no full reinstall).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
GCP_VM_IP="${GCP_VM_IP:-34.45.7.252}"
GCP_USER="${GCP_USER:-areej}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/pumpfun_vps}"
SSH_OPTS=(-i "$SSH_KEY" -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

echo ">>> Upload registry hotfix"
scp "${SSH_OPTS[@]}" \
  "$REPO_DIR/registry/main.py" \
  "$REPO_DIR/registry/analytics.py" \
  "${GCP_USER}@${GCP_VM_IP}:~/x402-agents/registry/"
scp "${SSH_OPTS[@]}" \
  "$REPO_DIR/scripts/start-beacon.sh" \
  "${GCP_USER}@${GCP_VM_IP}:~/start-beacon.sh"

ssh "${SSH_OPTS[@]}" "${GCP_USER}@${GCP_VM_IP}" bash <<'REMOTE'
set -euo pipefail
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$HOME/beacon-venv/bin:$PATH"
cp -f ~/x402-agents/registry/start-beacon.sh ~/start-beacon.sh 2>/dev/null || \
  cp -f ~/x402-agents/scripts/start-beacon.sh ~/start-beacon.sh 2>/dev/null || true
chmod +x ~/start-beacon.sh 2>/dev/null || true

# Patch PM2 to 1 worker + HTTPS public URL if ecosystem exists
if [[ -f ~/x402-agents/ecosystem.config.cjs ]]; then
  sed -i 's/--workers 2/--workers 1/g' ~/x402-agents/ecosystem.config.cjs
  sed -i 's|PUBLIC_BASE_URL: "http://[^"]*"|PUBLIC_BASE_URL: "https://registry-ruby.vercel.app"|g' ~/x402-agents/ecosystem.config.cjs
fi

pm2 restart beacon-registry
sleep 2
curl -fsS "http://127.0.0.1:8000/healthz" | head -c 200
echo ""
REMOTE

echo ">>> Live check"
curl -fsS -o /dev/null -w "healthz: %{http_code} %{time_total}s\n" --max-time 15 "https://registry-ruby.vercel.app/healthz"
curl -fsS -o /dev/null -w "search: %{http_code} %{time_total}s\n" --max-time 20 \
  "https://registry-ruby.vercel.app/api/v1/search?q=web+scraping&limit=5"
