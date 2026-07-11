#!/usr/bin/env python3
"""
enrich_github.py — retrofit existing Beacon rows with REAL GitHub traction.

For every agent whose mcp_endpoint is a github.com repo, fetch the repository's
genuine metadata in a single GET /repos/{owner}/{repo} call and store it in
honestly-named columns:

  * stars       <- stargazers_count   (real popularity)
  * pushed_at   <- pushed_at          (real last native activity -> drives 'active')
  * open_issues <- open_issues_count  (real open work)

Deliberately does NOT touch total_transactions / successful_transactions /
success_rate — those belong to the agent-telemetry reputation & fraud engine and
must stay real agent telemetry. Repo activity is shown separately, labeled as
what it is.

Writes go straight to the local SQLite database via the shared turso module.
Respects GitHub limits with a fixed sleep and Retry-After back-off.

Env:
  GITHUB_TOKEN     PAT (5000/hr). Without it you're limited to 60/hr.
  SQLITE_DB_PATH   Path to local SQLite database (default: /home/gcp_user/beacon_prod.db)
  SLEEP_SECS       per-repo pacing (default 1.5)
  ENRICH_LIMIT     max rows to process this run (default 100000)
  ONLY_MISSING     '1' to skip rows already enriched (default '1')
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time

import requests

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
ONLY_MISSING = os.environ.get("ONLY_MISSING", "1") == "1"
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


def main() -> None:
    log.info("beacon-enrich starting — database: %s", turso.DB_PATH)
    if not GITHUB_TOKEN:
        log.warning("No GITHUB_TOKEN — throttled to ~60/hr. Set it to enrich at scale.")

    # Ensure schema is present (idempotent, fast on warm DB).
    turso.ensure_schema()

    where = "WHERE mcp_endpoint LIKE '%github.com%'"
    if ONLY_MISSING:
        where += " AND pushed_at IS NULL"
    rows = turso.execute(
        f"SELECT agent_id, mcp_endpoint FROM agents {where} LIMIT ?", [ENRICH_LIMIT]
    )
    log.info("enriching %d github-sourced agents", len(rows))

    session = requests.Session()
    session.headers.update(gh_headers())
    done = updated = skipped = 0

    for row in rows:
        m = _SLUG_RE.search(row["mcp_endpoint"] or "")
        if not m:
            skipped += 1
            continue
        slug = m.group(1).rstrip(".git")
        data = fetch_repo(session, slug)
        done += 1
        if data:
            try:
                turso.execute(
                    "UPDATE agents SET stars = ?, pushed_at = ?, open_issues = ? WHERE agent_id = ?",
                    [
                        int(data.get("stargazers_count", 0)),
                        data.get("pushed_at"),
                        int(data.get("open_issues_count", 0)),
                        row["agent_id"],
                    ],
                )
                updated += 1
                if updated % 25 == 0:
                    log.info(
                        "... %d updated (%d★ latest: %s)",
                        updated,
                        int(data.get("stargazers_count", 0)),
                        slug,
                    )
            except Exception as exc:
                log.error("db write failed for %s: %s", slug, exc)
        else:
            skipped += 1
        time.sleep(SLEEP_SECS)

    log.info("DONE — processed=%d updated=%d skipped=%d", done, updated, skipped)


if __name__ == "__main__":
    main()
