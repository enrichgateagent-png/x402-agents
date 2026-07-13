"""
Usage signals — telemetry jobs + portal/MCP selection counts.

Agents that register and report telemetry climb the usage leaderboard and get
a discover-ranking boost. Selections credit agents when humans or orchestrators
wire them from the portal or MCP (even without running the SDK).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import turso

SELECTION_WEIGHT = 2  # each wire/pick counts like 2 telemetry jobs in proven score


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_usage_schema() -> None:
    turso.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_usage (
            agent_id TEXT PRIMARY KEY,
            selections INTEGER NOT NULL DEFAULT 0,
            last_selected_at TEXT
        )
        """
    )
    turso.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_usage_selections ON agent_usage(selections DESC)"
    )
    turso.execute(
        "CREATE INDEX IF NOT EXISTS idx_agents_transactions ON agents(total_transactions DESC)"
    )


def proven_score(total_transactions: int, selections: int) -> int:
    return int(total_transactions or 0) + int(selections or 0) * SELECTION_WEIGHT


def selection_map(agent_ids: list[str]) -> dict[str, int]:
    if not agent_ids:
        return {}
    placeholders = ",".join("?" * len(agent_ids))
    rows = turso.execute(
        f"SELECT agent_id, selections FROM agent_usage WHERE agent_id IN ({placeholders})",
        agent_ids,
    )
    return {r["agent_id"]: int(r["selections"] or 0) for r in rows}


def enrich_public(pub: dict, selections: Optional[int] = None) -> dict:
    """Attach usage fields to a public agent dict."""
    tx = int(pub.get("total_transactions") or 0)
    sel = int(selections if selections is not None else pub.get("selection_count") or 0)
    score = proven_score(tx, sel)
    out = dict(pub)
    out["selection_count"] = sel
    out["proven_score"] = score
    out["usage"] = {
        "total_jobs": tx,
        "selections": sel,
        "proven_score": score,
        "is_proven": score >= 10,
    }
    return out


def agent_benefits(pub: dict, selections: int = 0) -> dict:
    tx = int(pub.get("total_transactions") or 0)
    sel = int(selections or 0)
    score = proven_score(tx, sel)
    tips: list[str] = []
    if tx == 0:
        tips.append(
            "Wrap jobs with @beacon.track_job or POST /api/v1/telemetry — each success/fail "
            "updates your rank and README badge."
        )
    elif tx < 25:
        tips.append(f"{25 - tx} more telemetry jobs unlock the Proven badge tier on your README.")
    if sel == 0:
        tips.append("When users wire you from the portal, selection count boosts proven ranking.")
    return {
        "discover_boost_active": score > 0,
        "leaderboard_eligible": tx > 0 or sel > 0,
        "badge_tier": "proven" if tx >= 10 else ("active" if tx > 0 else "listed"),
        "proven_score": score,
        "tips": tips,
    }


def record_selection(agent_id: str, source: str = "portal") -> dict:
    """Increment selection count for a registered agent (portal wire, MCP pick, etc.)."""
    exists = turso.execute("SELECT 1 AS x FROM agents WHERE agent_id = ?", [agent_id])
    if not exists:
        return {"ok": False, "error": "agent_id not registered"}

    now = _utcnow()
    turso.execute(
        "INSERT INTO agent_usage (agent_id, selections, last_selected_at) VALUES (?, 0, ?) "
        "ON CONFLICT(agent_id) DO NOTHING",
        [agent_id, now],
    )
    turso.execute(
        "UPDATE agent_usage SET selections = selections + 1, last_selected_at = ? WHERE agent_id = ?",
        [now, agent_id],
    )
    row = turso.execute(
        "SELECT selections, last_selected_at FROM agent_usage WHERE agent_id = ?", [agent_id]
    )[0]
    return {
        "ok": True,
        "agent_id": agent_id,
        "source": source,
        "selections": int(row["selections"] or 0),
        "last_selected_at": row["last_selected_at"],
    }


def get_proven_feed(
    limit: int,
    offset: int,
    row_to_public: Callable[[dict], dict],
    live_clause: str,
    live_args: list,
) -> dict:
    """Top agents by proven score (telemetry jobs + weighted selections)."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    count_row = turso.execute(
        f"""
        SELECT COUNT(*) AS n FROM agents a
        LEFT JOIN agent_usage u ON u.agent_id = a.agent_id
        WHERE a.is_fraudulent = 0 {live_clause}
          AND (a.total_transactions > 0 OR COALESCE(u.selections, 0) > 0)
        """,
        live_args,
    )[0]
    total = int(count_row["n"] or 0)

    rows = turso.execute(
        f"""
        SELECT a.*, COALESCE(u.selections, 0) AS selection_count
        FROM agents a
        LEFT JOIN agent_usage u ON u.agent_id = a.agent_id
        WHERE a.is_fraudulent = 0 {live_clause}
          AND (a.total_transactions > 0 OR COALESCE(u.selections, 0) > 0)
        ORDER BY (a.total_transactions + COALESCE(u.selections, 0) * {SELECTION_WEIGHT}) DESC,
                 a.success_rate DESC,
                 a.stars DESC
        LIMIT ? OFFSET ?
        """,
        [*live_args, limit, offset],
    )
    agents = [
        enrich_public(row_to_public(r), int(r.get("selection_count") or 0)) for r in rows
    ]
    return {
        "ok": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "returned": len(agents),
        "selection_weight": SELECTION_WEIGHT,
        "agents": agents,
    }


def platform_usage_summary() -> dict:
    row = turso.execute(
        """
        SELECT
            COALESCE(SUM(selections), 0) AS total_selections,
            COUNT(*) AS agents_with_selections
        FROM agent_usage WHERE selections > 0
        """
    )[0]
    jobs = turso.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_transactions), 0) AS jobs "
        "FROM agents WHERE total_transactions > 0 AND is_fraudulent = 0"
    )[0]
    return {
        "agents_reporting_telemetry": int(jobs["n"] or 0),
        "total_telemetry_jobs": int(jobs["jobs"] or 0),
        "agents_with_selections": int(row["agents_with_selections"] or 0),
        "total_selections": int(row["total_selections"] or 0),
    }
