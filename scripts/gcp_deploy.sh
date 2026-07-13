#!/usr/bin/env bash
# One-shot GCP Ubuntu VM deployment for Beacon registry + MCP SSE.
# Usage (on the VM):
#   export GCP_VM_IP=34.x.x.x
#   export GITHUB_TOKEN=ghp_...
#   bash scripts/gcp_deploy.sh
set -euo pipefail

GCP_VM_IP="${GCP_VM_IP:-YOUR_GCP_VM_IP}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO_DIR="${REPO_DIR:-$HOME/x402-agents}"
REGISTRY_DIR="$REPO_DIR/registry"
MCP_DIR="$REPO_DIR/mcp/beacon-mcp"
VENV_DIR="${VENV_DIR:-$HOME/beacon-venv}"
DB_PATH="${SQLITE_DB_PATH:-$HOME/beacon_prod.db}"
USER_NAME="$(whoami)"

echo ">>> [1/9] System packages"
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git sqlite3 curl build-essential

echo ">>> [2/9] Node.js 20 + npm"
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
node -v && npm -v

echo ">>> [3/9] PM2"
sudo npm install -g pm2
pm2 -v

echo ">>> [4/9] Repository"
if [[ -d "$REPO_DIR/.git" ]]; then
  git -C "$REPO_DIR" pull --ff-only
else
  git clone https://github.com/enrichgateagent-png/x402-agents.git "$REPO_DIR"
fi

echo ">>> [5/9] Python venv + FastAPI deps"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$REGISTRY_DIR/requirements.txt" -q

echo ">>> [6/9] MCP SSE server (Node)"
cd "$MCP_DIR"
npm ci
npm run build

echo ">>> [7/9] .env + PM2 ecosystem"
cat > "$REGISTRY_DIR/.env" <<EOF
SQLITE_DB_PATH=$DB_PATH
PORT=8000
PUBLIC_BASE_URL=https://registry-ruby.vercel.app
PORTAL_URL=https://portal-five-phi-54.vercel.app
GITHUB_TOKEN=$GITHUB_TOKEN
VALIDATION_TIMEOUT=6
REGISTRY_ONLINE_WINDOW=300
REGISTRY_MAX_RESULTS=25
ACTIVE_WINDOW_DAYS=90
EOF

cat > "$REPO_DIR/ecosystem.config.cjs" <<EOF
module.exports = {
  apps: [
    {
      name: "beacon-registry",
      script: "$VENV_DIR/bin/uvicorn",
      args: "main:app --host 0.0.0.0 --port 8000 --workers 2",
      cwd: "$REGISTRY_DIR",
      env: {
        SQLITE_DB_PATH: "$DB_PATH",
        PORT: "8000",
        PUBLIC_BASE_URL: "https://registry-ruby.vercel.app",
        PORTAL_URL: "https://portal-five-phi-54.vercel.app",
        GITHUB_TOKEN: "$GITHUB_TOKEN",
      },
      restart_delay: 3000,
      max_restarts: 10,
    },
    {
      name: "beacon-mcp-sse",
      script: "node",
      args: "dist/sse.js",
      cwd: "$MCP_DIR",
      env: {
        BEACON_REGISTRY_URL: "http://127.0.0.1:8000",
        MCP_SSE_PORT: "8001",
      },
      restart_delay: 3000,
      max_restarts: 10,
    },
  ],
};
EOF

echo ">>> [8/9] Import database (if present)"
if [[ -f "$HOME/beacon.db" ]]; then
  SQLITE_DB_PATH="$DB_PATH" bash "$REPO_DIR/scripts/import_db_file.sh" "$HOME/beacon.db"
elif [[ -f "$HOME/data_backup.sql" ]]; then
  SQLITE_DB_PATH="$DB_PATH" bash "$REPO_DIR/scripts/import_sqlite.sh" "$HOME/data_backup.sql"
else
  echo "  No ~/beacon.db or ~/data_backup.sql — skipping import"
  echo "  Upload with:  scp beacon.db gcp_user@$GCP_VM_IP:~/"
fi

echo ">>> [9/9] Start PM2 processes"
pm2 delete beacon-registry beacon-mcp-sse 2>/dev/null || true
pm2 start "$REPO_DIR/ecosystem.config.cjs"
pm2 save
sudo env PATH="$PATH:/usr/bin" pm2 startup systemd -u "$USER_NAME" --hp "$HOME" | tail -1 | bash || true

# Daily GitHub enrichment cron on the VM (replaces GitHub Actions Turso job).
CRON_LINE="0 3 * * * cd $REGISTRY_DIR && SQLITE_DB_PATH=$DB_PATH $VENV_DIR/bin/python enrich_github.py >> $HOME/beacon-enrich.log 2>&1"
( crontab -l 2>/dev/null | grep -v "enrich_github.py" || true; echo "$CRON_LINE" ) | crontab -

echo ""
echo "========================================"
echo " Beacon deployed"
echo " Registry:   http://$GCP_VM_IP:8000/healthz"
echo " MCP SSE:    http://$GCP_VM_IP:8001/sse"
echo " Glama URL:  http://$GCP_VM_IP:8001/sse"
echo " Logs:       pm2 logs"
echo " DB:         $DB_PATH"
echo "========================================"
echo ""
echo "Open GCP firewall for TCP 8000 and 8001 if not already:"
echo "  gcloud compute firewall-rules create allow-beacon \\"
echo "    --allow tcp:8000,tcp:8001 --source-ranges 0.0.0.0/0"
