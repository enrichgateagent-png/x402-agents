#!/usr/bin/env python3
"""
enrich_github.py — retrofit existing Beacon rows with REAL GitHub traction.

For every agent whose mcp_endpoint is a github.com repo, fetch the repository's
genuine metadata in a single GET /repos/{owner}/{repo} call and store it in
honestly-named columns:

  * stars       <- stargazers_count   (real popularity)
  * pushed_at   <- pushed_at          (real last native activity -> drives 'active')
  * open_issues <- open_issues_count  (real open work)

Also records trending milestones (star thresholds, surges, recent pushes) for the
portal growth feed — internal only, no outbound GitHub spam.

Writes go straight to the local SQLite database via the shared turso module.
Respects GitHub limits with a fixed sleep and Retry-After back-off.

Env:
  GITHUB_TOKEN     PAT (5000/hr). Without it you're limited to 60/hr.
  SQLITE_DB_PATH   Path to local SQLite database
  SLEEP_SECS       per-repo pacing (default 1.5)
  ENRICH_LIMIT     max rows to process this run (default 100000)
  ONLY_MISSING     '1' to only enrich rows without pushed_at (default '0')
  STALE_DAYS       re-enrich rows older than N days (default 7)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import trending
import turso

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("beacon-enrich")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
SLEEP_SECS = float(os.environ.get("SLEEP_SECS", "1.5"))
ENRICH_LIMIT = int(os.environ.get("ENRICH_LIMIT", "100000"))
ONLY_MISSING = os.environ.get("ONLY_MISSING", "0") == "1"
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
REQUEST_TIMEOUT = 30

_SLUG_RE = re.compile(r"github\.com/([^/]+/[^/#?]+)", re.IGNORECASE)


def gh_headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "beacon-enrich/1.0",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def fetch_repo(session: requests.Session, slug: str) -> dict | None:
    """GET /repos/{slug}. Handles 403 rate limits and 404s. One call per repo."""
    while True:
        try:
            r = session.get(f"https://api.github.com/repos/{slug}", timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            log.warning("network error for %s: %s", slug, exc)
            return None
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        if r.status_code in (403, 429):
            reset = r.headers.get("Retry-After")
            if reset is not None:
                wait = int(reset) + 1
            elif r.headers.get("X-RateLimit-Remaining") == "0":
                wait = max(0, int(r.headers.get("X-RateLimit-Reset", "0")) - int(time.time())) + 2
            else:
                wait = 30
            log.warning("rate limited on %s — sleeping %ds", slug, min(wait, 300))
            time.sleep(min(wait, 300))
            continue
        log.warning("unexpected HTTP %s for %s", r.status_code, slug)
        return None


def _select_rows() -> list[dict]:
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)).isoformat()
    if ONLY_MISSING:
        where = "WHERE mcp_endpoint LIKE '%github.com%' AND pushed_at IS NULL"
        return turso.execute(
            f"SELECT agent_id, mcp_endpoint, stars FROM agents {where} LIMIT ?",
            [ENRICH_LIMIT],
        )
    return turso.execute(
        """
        SELECT agent_id, mcp_endpoint, stars FROM agents
         WHERE mcp_endpoint LIKE '%github.com%'
           AND (
                pushed_at IS NULL
             OR enriched_at IS NULL
             OR enriched_at < ?
           )
         ORDER BY (enriched_at IS NULL) DESC, enriched_at ASC
         LIMIT ?
        """,
        [stale_cutoff, ENRICH_LIMIT],
    )


def main() -> None:
    log.info("beacon-enrich starting — database: %s", turso.DB_PATH)
    if not GITHUB_TOKEN:
        log.warning("No GITHUB_TOKEN — throttled to ~60/hr. Set it to enrich at scale.")

    turso.ensure_schema()
    trending.ensure_trending_schema()

    rows = _select_rows()
    log.info("enriching %d github-sourced agents (stale_days=%d)", len(rows), STALE_DAYS)

    session = requests.Session()
    session.headers.update(gh_headers())
    done = updated = skipped = milestones = 0
    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        m = _SLUG_RE.search(row["mcp_endpoint"] or "")
        if not m:
            skipped += 1
            continue
        slug = m.group(1).rstrip(".git")
        old_stars = int(row.get("stars") or 0)
        data = fetch_repo(session, slug)
        done += 1
        if data:
            try:
                new_stars = int(data.get("stargazers_count", 0))
                pushed_at = data.get("pushed_at")
                turso.execute(
                    """
                    UPDATE agents
                       SET stars = ?, stars_prev = ?, pushed_at = ?, open_issues = ?,
                           enriched_at = ?
                     WHERE agent_id = ?
                    """,
                    [
                        new_stars,
                        old_stars,
                        pushed_at,
                        int(data.get("open_issues_count", 0)),
                        now,
                        row["agent_id"],
                    ],
                )
                trending.record_enrich_update(row["agent_id"], old_stars, new_stars, pushed_at)
                updated += 1
                if _milestone_logged(old_stars, new_stars):
                    milestones += 1
                if updated % 25 == 0:
                    log.info(
                        "... %d updated (%d★ latest: %s, %d milestones)",
                        updated,
                        new_stars,
                        slug,
                        milestones,
                    )
            except Exception as exc:
                log.error("db write failed for %s: %s", slug, exc)
        else:
            skipped += 1
        time.sleep(SLEEP_SECS)

    log.info("DONE — processed=%d updated=%d skipped=%d milestones=%d", done, updated, skipped, milestones)


def _milestone_logged(old_stars: int, new_stars: int) -> bool:
    for m in trending.STAR_MILESTONES:
        if old_stars < m <= new_stars:
            return True
    return new_stars - old_stars >= trending.STAR_SURGE_MIN_DELTA


if __name__ == "__main__":
    main()
