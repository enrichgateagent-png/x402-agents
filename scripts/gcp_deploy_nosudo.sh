#!/usr/bin/env bash
# User-space deploy — no sudo required. Run ON the GCP VM as areej.
set -euo pipefail

GCP_VM_IP="${GCP_VM_IP:-34.45.7.252}"
REPO_DIR="${REPO_DIR:-$HOME/x402-agents}"
REGISTRY_DIR="$REPO_DIR/registry"
MCP_DIR="$REPO_DIR/mcp/beacon-mcp"
VENV_DIR="$HOME/beacon-venv"
DB_PATH="$HOME/beacon_prod.db"

echo ">>> [1/7] Python venv via standalone virtualenv (no sudo)"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  curl -fsSL https://bootstrap.pypa.io/virtualenv.pyz -o /tmp/virtualenv.pyz
  python3 /tmp/virtualenv.pyz "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install -r "$REGISTRY_DIR/requirements.txt"

echo ">>> [2/7] Import beacon.db"
python3 <<PY
import shutil, sqlite3
from pathlib import Path
src = Path.home() / "beacon.db"
dst = Path("$DB_PATH")
shutil.copy2(src, dst)
conn = sqlite3.connect(dst)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
n = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
conn.close()
print(f"Imported {n:,} agents -> {dst}")
PY

echo ">>> [3/7] Write registry .env"
cat > "$REGISTRY_DIR/.env" <<EOF
SQLITE_DB_PATH=$DB_PATH
PORT=8000
PUBLIC_BASE_URL=https://registry-ruby.vercel.app
PORTAL_URL=https://portal-five-phi-54.vercel.app
VALIDATION_TIMEOUT=6
REGISTRY_ONLINE_WINDOW=300
REGISTRY_MAX_RESULTS=25
ACTIVE_WINDOW_DAYS=90
EOF

echo ">>> [4/7] Install Node via nvm (user space)"
export NVM_DIR="$HOME/.nvm"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck disable=SC1090
source "$NVM_DIR/nvm.sh"
nvm install 20
nvm use 20
cd "$MCP_DIR"
npm ci
npm run build
npm install -g pm2 2>/dev/null || npm install pm2 && export PATH="$MCP_DIR/node_modules/.bin:$HOME/.npm-global/bin:$PATH"

echo ">>> [5/7] PM2 ecosystem"
cat > "$REPO_DIR/ecosystem.config.cjs" <<EOF
module.exports = {
  apps: [
    {
      name: "beacon-registry",
      script: "$VENV_DIR/bin/uvicorn",
      args: "main:app --host 0.0.0.0 --port 8000 --workers 1",
      cwd: "$REGISTRY_DIR",
      env: {
        SQLITE_DB_PATH: "$DB_PATH",
        PORT: "8000",
        PUBLIC_BASE_URL: "https://registry-ruby.vercel.app",
      },
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
    },
  ],
};
EOF

echo ">>> [6/7] Start PM2"
export PATH="$HOME/.local/bin:$VENV_DIR/bin:$PATH"
command -v pm2 >/dev/null || npm install -g pm2
pm2 delete beacon-registry beacon-mcp-sse 2>/dev/null || true
pm2 start "$REPO_DIR/ecosystem.config.cjs"
pm2 save
pm2 startup 2>/dev/null || true

echo ""
echo "========================================"
echo " Beacon deployed (user-space)"
echo " Registry: http://$GCP_VM_IP:8000/healthz"
echo " MCP SSE:  http://$GCP_VM_IP:8001/sse"
echo "========================================"
