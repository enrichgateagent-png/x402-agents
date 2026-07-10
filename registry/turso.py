"""
Minimal Turso (libSQL) HTTP client using the /v2/pipeline JSON API.

No native driver, no wheels — just `requests`. This makes the registry fully
serverless-friendly (Vercel, etc.) while keeping durable managed-SQLite storage.
Values are passed/returned in Turso's typed-arg envelope and converted to/from
native Python here.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional

import requests

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
_TIMEOUT = float(os.environ.get("TURSO_TIMEOUT", "20"))


def _http_base(url: str) -> str:
    # Turso hands out libsql:// URLs; the HTTP pipeline endpoint is https://.
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    return url.rstrip("/")


class TursoError(RuntimeError):
    pass


def _to_arg(v: Any) -> dict:
    if v is None:
        return {"type": "null", "value": None}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def _from_val(cell: dict) -> Any:
    t = cell.get("type")
    val = cell.get("value")
    if t == "null":
        return None
    if t == "integer":
        try:
            return int(val)
        except (TypeError, ValueError):
            return val
    if t == "float":
        try:
            return float(val)
        except (TypeError, ValueError):
            return val
    return val


def execute(sql: str, args: Optional[Iterable[Any]] = None) -> list[dict]:
    """
    Run one statement. Returns a list of row dicts (empty for writes).
    Raises TursoError on any transport or SQL error.
    """
    if not TURSO_URL or not TURSO_TOKEN:
        raise TursoError("TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not configured")

    stmt: dict[str, Any] = {"sql": sql}
    if args is not None:
        stmt["args"] = [_to_arg(a) for a in args]

    body = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
    try:
        resp = requests.post(
            f"{_http_base(TURSO_URL)}/v2/pipeline",
            json=body,
            headers={"Authorization": f"Bearer {TURSO_TOKEN}"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise TursoError(f"transport error: {exc}") from exc

    if resp.status_code != 200:
        raise TursoError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    payload = resp.json()
    results = payload.get("results", [])
    if not results:
        return []
    first = results[0]
    if first.get("type") == "error":
        raise TursoError(first.get("error", {}).get("message", "unknown SQL error"))

    result = first.get("response", {}).get("result", {})
    cols = [c["name"] for c in result.get("cols", [])]
    rows = result.get("rows", [])
    return [{cols[i]: _from_val(cell) for i, cell in enumerate(row)} for row in rows]


def ensure_schema() -> None:
    """Idempotent DDL. Cheap enough to call on every cold start."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            agent_id          TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            mcp_endpoint      TEXT NOT NULL,
            capabilities_tags TEXT NOT NULL DEFAULT '',
            success_rate      REAL NOT NULL DEFAULT 1.0,
            total_transactions INTEGER NOT NULL DEFAULT 0,
            successful_transactions INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT NOT NULL,
            last_seen         TEXT NOT NULL
        )
        """
    )
    execute("CREATE INDEX IF NOT EXISTS idx_agents_success ON agents(success_rate DESC)")
    execute("CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen DESC)")
    # Additive columns for the endpoint validator. ADD COLUMN is idempotent-safe
    # via try/except since SQLite has no "ADD COLUMN IF NOT EXISTS".
    for ddl in (
        "ALTER TABLE agents ADD COLUMN reachable INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE agents ADD COLUMN last_validated TEXT",
        "ALTER TABLE agents ADD COLUMN registration_source TEXT NOT NULL DEFAULT 'sdk'",
    ):
        try:
            execute(ddl)
        except TursoError:
            pass  # column already exists
