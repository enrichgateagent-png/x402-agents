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

Writes go straight to Turso over its HTTP API (same creds as the app). Respects
GitHub limits with a fixed sleep and Retry-After back-off.

Env:
  GITHUB_TOKEN          PAT (5000/hr). Without it you're limited to 60/hr.
  TURSO_DATABASE_URL    libsql://... (or https://...)
  TURSO_AUTH_TOKEN      database auth token
  SLEEP_SECS            per-repo pacing (default 1.5)
  ENRICH_LIMIT          max rows to process this run (default 100000)
  ONLY_MISSING          '1' to skip rows already enriched (default '1')
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
log = logging.getLogger("beacon-enrich")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
SLEEP_SECS = float(os.environ.get("SLEEP_SECS", "1.5"))
ENRICH_LIMIT = int(os.environ.get("ENRICH_LIMIT", "100000"))
ONLY_MISSING = os.environ.get("ONLY_MISSING", "1") == "1"
REQUEST_TIMEOUT = 30

_SLUG_RE = re.compile(r"github\.com/([^/]+/[^/#?]+)", re.IGNORECASE)


def _turso_http() -> str:
    u = TURSO_URL
    if u.startswith("libsql://"):
        u = "https://" + u[len("libsql://"):]
    return u.rstrip("/")


def turso_exec(sql: str, args: list) -> list:
    def arg(v):
        if v is None:
            return {"type": "null", "value": None}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        return {"type": "text", "value": str(v)}

    body = {"requests": [
        {"type": "execute", "stmt": {"sql": sql, "args": [arg(a) for a in args]}},
        {"type": "close"},
    ]}
    r = requests.post(f"{_turso_http()}/v2/pipeline",
                      json=body, headers={"Authorization": f"Bearer {TURSO_TOKEN}"}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    res = r.json()["results"][0]
    if res.get("type") == "error":
        raise RuntimeError(res.get("error", {}).get("message", "sql error"))
    result = res.get("response", {}).get("result", {})
    cols = [c["name"] for c in result.get("cols", [])]
    out = []
    for row in result.get("rows", []):
        out.append({cols[i]: cell.get("value") for i, cell in enumerate(row)})
    return out


def gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "beacon-enrich/1.0"}
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
    if not (TURSO_URL and TURSO_TOKEN):
        log.error("TURSO_DATABASE_URL / TURSO_AUTH_TOKEN required")
        sys.exit(1)
    if not GITHUB_TOKEN:
        log.warning("No GITHUB_TOKEN — throttled to ~60/hr. Set it to enrich at scale.")

    where = "WHERE mcp_endpoint LIKE '%github.com%'"
    if ONLY_MISSING:
        where += " AND pushed_at IS NULL"
    rows = turso_exec(f"SELECT agent_id, mcp_endpoint FROM agents {where} LIMIT ?", [ENRICH_LIMIT])
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
                turso_exec(
                    "UPDATE agents SET stars = ?, pushed_at = ?, open_issues = ? WHERE agent_id = ?",
                    [int(data.get("stargazers_count", 0)), data.get("pushed_at"),
                     int(data.get("open_issues_count", 0)), row["agent_id"]],
                )
                updated += 1
                if updated % 25 == 0:
                    log.info("... %d updated (%d★ latest: %s)", updated, int(data.get("stargazers_count", 0)), slug)
            except Exception as exc:
                log.error("db write failed for %s: %s", slug, exc)
        else:
            skipped += 1
        time.sleep(SLEEP_SECS)

    log.info("DONE — processed=%d updated=%d skipped=%d", done, updated, skipped)


if __name__ == "__main__":
    main()
