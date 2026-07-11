"""
Request analytics — SQLite-backed access log and admin rollups for the GCP registry.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import turso

ADMIN_SECRET = os.environ.get("ADMIN_SECRET_PASSWORD", "")

# Paths we skip (noise / static)
_SKIP_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/favicon")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request) -> str:
    xf = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or ""
    ip = str(xf).split(",")[0].strip()
    if request.client and not ip:
        ip = request.client.host or ""
    return ip or "unknown"


def _traffic_bucket(ua: str) -> str:
    u = (ua or "").lower()
    if "glama" in u:
        return "Glama"
    if "claudebot" in u or "anthropic" in u:
        return "Claude/Anthropic"
    if "gptbot" in u or "oai-searchbot" in u or "chatgpt" in u:
        return "OpenAI"
    if "perplexity" in u:
        return "Perplexity"
    if "python-requests" in u or "httpx" in u or "aiohttp" in u or "urllib" in u:
        return "PythonScrapers"
    if "beacon-indexer" in u or "scraper" in u:
        return "BeaconScraper"
    if any(x in u for x in ("axios", "node", "undici", "curl", "wget", "go-http")):
        return "ScriptClients"
    if any(x in u for x in ("beacon", "mcp", "cursor", "cline", "windsurf")):
        return "AgentClients"
    if any(x in u for x in ("bot", "crawler", "spider", "bytespider", "bingbot")):
        return "UnknownBots"
    if any(x in u for x in ("mozilla", "chrome", "safari", "firefox", "edg/")):
        return "Human"
    return "Other"


def verify_admin(request) -> bool:
    if not ADMIN_SECRET:
        return False
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() == ADMIN_SECRET
    token = request.headers.get("x-admin-token")
    return isinstance(token, str) and token.strip() == ADMIN_SECRET


def ensure_analytics_schema() -> None:
    turso.execute(
        """
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            client_class TEXT NOT NULL,
            client_bucket TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT
        )
        """
    )
    turso.execute("CREATE INDEX IF NOT EXISTS idx_access_log_ts ON access_log(ts DESC)")
    turso.execute("CREATE INDEX IF NOT EXISTS idx_access_log_bucket ON access_log(client_bucket)")
    turso.execute(
        """
        CREATE TABLE IF NOT EXISTS access_totals (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def log_request(request, client_class: str) -> None:
    path = request.url.path
    if not path.startswith("/api/"):
        return
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return
    if path.startswith("/api/admin"):
        return

    ua = (request.headers.get("user-agent") or "unknown")[:512]
    bucket = _traffic_bucket(ua)
    ip = _client_ip(request)

    try:
        turso.execute(
            """
            INSERT INTO access_log (ts, method, path, client_class, client_bucket, ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [_utcnow(), request.method, path, client_class, bucket, ip, ua],
        )
        turso.execute(
            """
            INSERT INTO access_totals (key, value) VALUES (?, 1)
            ON CONFLICT(key) DO UPDATE SET value = value + 1
            """,
            [f"reads:{bucket}"],
        )
        turso.execute(
            """
            INSERT INTO access_totals (key, value) VALUES ('api_reads_total', 1)
            ON CONFLICT(key) DO UPDATE SET value = value + 1
            """
        )
    except turso.TursoError:
        pass


def count_active_agents(pushed_recently_fn) -> int:
    rows = turso.execute(
        "SELECT pushed_at FROM agents WHERE is_fraudulent = 0 AND pushed_at IS NOT NULL"
    )
    return sum(1 for r in rows if pushed_recently_fn(r.get("pushed_at")))


def get_admin_analytics(pushed_recently_fn) -> dict:
    ensure_analytics_schema()

    total = int(turso.execute("SELECT COUNT(*) AS c FROM agents")[0]["c"])
    scraped = int(
        turso.execute(
            "SELECT COUNT(*) AS c FROM agents WHERE registration_source = 'scraper'"
        )[0]["c"]
    )
    sdk = int(
        turso.execute(
            "SELECT COUNT(*) AS c FROM agents WHERE registration_source = 'sdk'"
        )[0]["c"]
    )
    flagged = int(
        turso.execute("SELECT COUNT(*) AS c FROM agents WHERE is_fraudulent = 1")[0]["c"]
    )
    active = count_active_agents(pushed_recently_fn)

    totals_rows = turso.execute("SELECT key, value FROM access_totals")
    totals_map = {r["key"]: int(r["value"]) for r in totals_rows}
    api_reads = totals_map.get("api_reads_total", 0)

    log_count = int(turso.execute("SELECT COUNT(*) AS c FROM access_log")[0]["c"])

    bucket_rows = turso.execute(
        """
        SELECT client_bucket AS bucket, COUNT(*) AS hits
          FROM access_log
         GROUP BY client_bucket
         ORDER BY hits DESC
         LIMIT 20
        """
    )
    bot_traffic_breakdown = {r["bucket"]: int(r["hits"]) for r in bucket_rows}

    ua_rows = turso.execute(
        """
        SELECT user_agent, client_bucket, COUNT(*) AS hits
          FROM access_log
         GROUP BY user_agent, client_bucket
         ORDER BY hits DESC
         LIMIT 25
        """
    )
    top_consumers = [
        {
            "user_agent": (r["user_agent"] or "")[:200],
            "category": r["client_bucket"],
            "hits": int(r["hits"]),
        }
        for r in ua_rows
    ]

    ip_rows = turso.execute(
        """
        SELECT ip, COUNT(*) AS hits
          FROM access_log
         GROUP BY ip
         ORDER BY hits DESC
         LIMIT 20
        """
    )
    top_ips = [{"ip": r["ip"], "hits": int(r["hits"])} for r in ip_rows]

    path_rows = turso.execute(
        """
        SELECT path, COUNT(*) AS hits
          FROM access_log
         GROUP BY path
         ORDER BY hits DESC
         LIMIT 15
        """
    )
    top_endpoints = [{"path": r["path"], "hits": int(r["hits"])} for r in path_rows]

    human_reads = sum(
        v for k, v in totals_map.items() if k.startswith("reads:") and "Human" in k
    ) or bot_traffic_breakdown.get("Human", 0)
    bot_reads = api_reads - human_reads if api_reads > human_reads else sum(
        v for b, v in bot_traffic_breakdown.items() if b != "Human"
    )

    return {
        "ok": True,
        "authenticated": True,
        "generated_at": _utcnow(),
        "storage": "sqlite",
        "storage_path": turso.DB_PATH,
        "summary": {
            "total_agents_indexed": total,
            "agents_harvested_by_scraper": scraped,
            "agents_registered_via_sdk": sdk,
            "active_agents_90d": active,
            "flagged_agents": flagged,
            "total_api_reads_logged": api_reads,
            "human_api_reads": human_reads,
            "bot_api_reads": bot_reads,
            "access_log_rows": log_count,
        },
        "bot_traffic_breakdown": bot_traffic_breakdown,
        "top_consumers": top_consumers,
        "top_ips": top_ips,
        "top_endpoints": top_endpoints,
    }
