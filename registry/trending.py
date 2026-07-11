"""
Trending / milestone detection — internal growth signals, no outbound spam.

Records star milestones and recent activity during GitHub enrichment.
Serves GET /api/v1/growth/trending for the portal strip.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import turso

TRENDING_WINDOW_DAYS = int(os.environ.get("TRENDING_WINDOW_DAYS", "7"))
STAR_MILESTONES = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
STAR_SURGE_MIN_DELTA = int(os.environ.get("STAR_SURGE_MIN_DELTA", "20"))
RECENT_PUSH_MIN_STARS = int(os.environ.get("RECENT_PUSH_MIN_STARS", "5"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_trending_schema() -> None:
    turso.execute(
        """
        CREATE TABLE IF NOT EXISTS trending_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT NOT NULL,
            stars INTEGER NOT NULL DEFAULT 0,
            stars_delta INTEGER NOT NULL DEFAULT 0,
            detected_at TEXT NOT NULL
        )
        """
    )
    turso.execute(
        "CREATE INDEX IF NOT EXISTS idx_trending_detected ON trending_events(detected_at DESC)"
    )
    turso.execute(
        "CREATE INDEX IF NOT EXISTS idx_trending_agent ON trending_events(agent_id, event_type)"
    )
    for ddl in (
        "ALTER TABLE agents ADD COLUMN enriched_at TEXT",
        "ALTER TABLE agents ADD COLUMN stars_prev INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            turso.execute(ddl)
        except turso.TursoError:
            pass


def _milestone_crossed(old_stars: int, new_stars: int) -> Optional[int]:
    for m in STAR_MILESTONES:
        if old_stars < m <= new_stars:
            return m
    return None


def _recent_push(pushed_at: Optional[str], days: int = TRENDING_WINDOW_DAYS) -> bool:
    if not pushed_at:
        return False
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days <= days
    except (TypeError, ValueError):
        return False


def _insert_event(
    agent_id: str,
    event_type: str,
    detail: str,
    stars: int,
    stars_delta: int,
) -> None:
    """Dedupe: one event of same type per agent per 7 days."""
    since = (datetime.now(timezone.utc) - timedelta(days=TRENDING_WINDOW_DAYS)).isoformat()
    existing = turso.execute(
        """
        SELECT id FROM trending_events
         WHERE agent_id = ? AND event_type = ? AND detected_at >= ?
         LIMIT 1
        """,
        [agent_id, event_type, since],
    )
    if existing:
        return
    turso.execute(
        """
        INSERT INTO trending_events (agent_id, event_type, detail, stars, stars_delta, detected_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [agent_id, event_type, detail, stars, stars_delta, _utcnow()],
    )


def record_enrich_update(
    agent_id: str,
    old_stars: int,
    new_stars: int,
    pushed_at: Optional[str],
) -> None:
    """Call after enrich_github writes new stars/pushed_at."""
    ensure_trending_schema()
    old_stars = int(old_stars or 0)
    new_stars = int(new_stars or 0)
    delta = new_stars - old_stars

    milestone = _milestone_crossed(old_stars, new_stars)
    if milestone is not None:
        _insert_event(
            agent_id,
            "star_milestone",
            f"Crossed {milestone:,} GitHub stars",
            new_stars,
            delta,
        )
    elif delta >= STAR_SURGE_MIN_DELTA and new_stars >= RECENT_PUSH_MIN_STARS:
        _insert_event(
            agent_id,
            "star_surge",
            f"+{delta:,} stars since last check",
            new_stars,
            delta,
        )

    if _recent_push(pushed_at) and new_stars >= RECENT_PUSH_MIN_STARS:
        _insert_event(
            agent_id,
            "recent_push",
            "Active development this week",
            new_stars,
            delta,
        )


def get_trending_feed(
    limit: int,
    row_to_public: Callable[[dict], dict],
    pushed_recently: Callable[[Optional[str]], bool],
) -> dict:
    ensure_trending_schema()
    limit = max(1, min(limit, 50))
    since = (datetime.now(timezone.utc) - timedelta(days=TRENDING_WINDOW_DAYS)).isoformat()

    rows = turso.execute(
        """
        SELECT a.*, e.event_type, e.detail, e.stars_delta, e.detected_at AS trending_at
          FROM trending_events e
          JOIN agents a ON a.agent_id = e.agent_id
         WHERE e.detected_at >= ?
           AND a.is_fraudulent = 0
         ORDER BY e.detected_at DESC, a.stars DESC
         LIMIT ?
        """,
        [since, limit * 3],
    )

    trending: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        aid = r["agent_id"]
        if aid in seen:
            continue
        seen.add(aid)
        pub = row_to_public(r)
        trending.append(
            {
                **pub,
                "trending": {
                    "event_type": r["event_type"],
                    "detail": r["detail"],
                    "stars_delta": int(r["stars_delta"] or 0),
                    "detected_at": r["trending_at"],
                },
            }
        )
        if len(trending) >= limit:
            break

    if len(trending) < limit:
        trending.extend(
            _fallback_trending(
                limit - len(trending),
                seen,
                row_to_public,
                pushed_recently,
            )
        )

    return {
        "ok": True,
        "window_days": TRENDING_WINDOW_DAYS,
        "count": len(trending),
        "trending": trending,
    }


def _fallback_trending(
    limit: int,
    exclude: set[str],
    row_to_public: Callable[[dict], dict],
    pushed_recently: Callable[[Optional[str]], bool],
) -> list[dict]:
    """When enrich hasn't run yet: active repos with traction, sorted by stars."""
    if limit <= 0:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=TRENDING_WINDOW_DAYS)).isoformat()
    rows = turso.execute(
        """
        SELECT * FROM agents
         WHERE is_fraudulent = 0
           AND stars >= ?
           AND pushed_at IS NOT NULL
           AND pushed_at >= ?
         ORDER BY stars DESC, pushed_at DESC
         LIMIT ?
        """,
        [RECENT_PUSH_MIN_STARS, cutoff, limit + len(exclude)],
    )
    out: list[dict] = []
    for r in rows:
        if r["agent_id"] in exclude:
            continue
        if not pushed_recently(r.get("pushed_at")):
            continue
        pub = row_to_public(r)
        pub["trending"] = {
            "event_type": "recent_push",
            "detail": "Recently maintained on GitHub",
            "stars_delta": 0,
            "detected_at": r.get("pushed_at"),
        }
        out.append(pub)
        if len(out) >= limit:
            break
    return out
