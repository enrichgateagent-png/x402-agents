#!/usr/bin/env bash
# Start Beacon registry on GCP — use 1 worker on small VMs (1GB RAM).
set -euo pipefail
cd "$(dirname "$0")/../registry" 2>/dev/null || cd ~/x402-agents/registry
source ~/beacon-venv/bin/activate
export SQLITE_DB_PATH="${SQLITE_DB_PATH:-/home/areej/beacon_prod.db}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://registry-ruby.vercel.app}"
export PORTAL_URL="${PORTAL_URL:-https://portal-five-phi-54.vercel.app}"
export TAG_CACHE_TTL_SECS="${TAG_CACHE_TTL_SECS:-3600}"
export ACTIVE_COUNT_CACHE_TTL="${ACTIVE_COUNT_CACHE_TTL:-300}"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
