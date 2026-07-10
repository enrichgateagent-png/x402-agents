#!/usr/bin/env python3
"""
Beacon Indexer — autonomous GitHub harvester for the Beacon agent registry.

Scrapes real, live AI-agent repositories and framework modules from GitHub,
normalizes their metadata into clean capability tags, and pipes each one into
the live Beacon registry via POST /api/v1/register.

Purpose: solve the registry's cold-start problem by seeding it with thousands of
genuine open-source agents/tools that developers can already discover.

Env:
  REGISTRY_URL   Beacon base URL (default: https://registry-ruby.vercel.app)
  GITHUB_TOKEN   optional GitHub PAT — raises rate limit 60/hr -> 5000/hr
  MAX_PER_QUERY  optional cap on repos harvested per search query (default 60)
  THROTTLE_SECS  optional min seconds between GitHub calls (default 2)

Contract note: Beacon's register endpoint reads the `capabilities` field. We send
both `capabilities` and `capabilities_tags` so the payload is self-documenting
and works regardless of which the server reads.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Iterable

import requests

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://registry-ruby.vercel.app").rstrip("/")
REGISTER_ENDPOINT = f"{REGISTRY_URL}/api/v1/register"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
MAX_PER_QUERY = int(os.environ.get("MAX_PER_QUERY", "60"))
THROTTLE_SECS = float(os.environ.get("THROTTLE_SECS", "2"))
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
PER_PAGE = 100
REQUEST_TIMEOUT = 30

# Exact agent-ecosystem targets requested. `topic:` queries hit curated tags;
# bare keyword queries catch repos that describe themselves but forgot the topic.
SEARCH_QUERIES: list[str] = [
    "topic:eliza-plugin",
    "topic:elizaos",
    "elizaos plugin",
    "topic:crewai-agent",
    "crewai agent",
    "topic:mcp-server",
    "mcp-server",
    "topic:model-context-protocol",
    "model context protocol server",
    "topic:langchain-agent",
    "langchain agent",
    "topic:autogen",
    "autogen agent",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "by",
    "is", "are", "be", "this", "that", "it", "as", "at", "from", "your", "you",
    "we", "our", "using", "use", "used", "can", "will", "make", "built", "build",
    "building", "based", "via", "into", "out", "up", "get", "run", "running",
    "simple", "easy", "new", "project", "repo", "repository", "code", "example",
    "examples", "demo", "app", "application", "tool", "tools", "library", "lib",
    "framework", "official", "awesome", "list", "template", "boilerplate", "starter",
    "python", "typescript", "javascript", "js", "ts", "how", "what", "when", "why",
    "all", "any", "more", "most", "some", "not", "no", "yes", "one", "two", "free",
}

# Ecosystem-relevant fallback tags keyed by the query that produced the repo, so
# every agent still gets >=4 meaningful tags even with a sparse description.
QUERY_FALLBACK_TAGS: list[tuple[str, list[str]]] = [
    ("eliza", ["eliza", "ai-agent", "plugin", "autonomous-agent"]),
    ("crewai", ["crewai", "ai-agent", "multi-agent", "orchestration"]),
    ("mcp", ["mcp", "model-context-protocol", "tools", "ai-agent"]),
    ("model-context", ["mcp", "model-context-protocol", "tools", "ai-agent"]),
    ("langchain", ["langchain", "ai-agent", "llm", "chains"]),
    ("autogen", ["autogen", "ai-agent", "multi-agent", "llm"]),
]
DEFAULT_FALLBACK = ["ai-agent", "automation", "llm", "integration"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("beacon-indexer")


# --------------------------------------------------------------------------- #
# HTTP session
# --------------------------------------------------------------------------- #

def build_session() -> requests.Session:
    s = requests.Session()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "beacon-indexer/1.0",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        log.info("GitHub token detected — rate limit 5000/hr")
    else:
        log.warning("No GITHUB_TOKEN — limited to ~60/hr and 10 search req/min. "
                    "Set GITHUB_TOKEN to harvest at scale.")
    s.headers.update(headers)
    return s


# --------------------------------------------------------------------------- #
# Rate-limit aware GitHub search
# --------------------------------------------------------------------------- #

def _respect_rate_limit(resp: requests.Response) -> None:
    """Sleep if we're near the search rate-limit window, using response headers."""
    try:
        remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
        reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
    except ValueError:
        remaining, reset = 1, 0
    if remaining <= 1 and reset:
        wait = max(0, reset - int(time.time())) + 2
        log.warning("Rate limit reached — sleeping %ds until reset", wait)
        time.sleep(min(wait, 120))


def search_repositories(session: requests.Session, query: str) -> Iterable[dict]:
    """Yield repo dicts for a query, paginating and isolating per-request failures."""
    harvested = 0
    page = 1
    while harvested < MAX_PER_QUERY:
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": PER_PAGE,
            "page": page,
        }
        try:
            resp = session.get(GITHUB_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            log.error("[%s] network error on page %d: %s", query, page, exc)
            break

        # Secondary/abuse rate limiting -> honor Retry-After and retry same page.
        if resp.status_code in (403, 429):
            retry_after = int(resp.headers.get("Retry-After", "30"))
            if int(resp.headers.get("X-RateLimit-Remaining", "1")) == 0:
                _respect_rate_limit(resp)
                continue
            log.warning("[%s] throttled (HTTP %d) — sleeping %ds", query, resp.status_code, retry_after)
            time.sleep(min(retry_after, 120))
            continue

        if resp.status_code != 200:
            log.error("[%s] search failed HTTP %d: %s", query, resp.status_code, resp.text[:150])
            break

        try:
            items = resp.json().get("items", [])
        except ValueError:
            log.error("[%s] non-JSON search response", query)
            break

        if not items:
            break

        for item in items:
            yield item
            harvested += 1
            if harvested >= MAX_PER_QUERY:
                break

        _respect_rate_limit(resp)
        time.sleep(THROTTLE_SECS)  # base throttle between search pages
        if len(items) < PER_PAGE:
            break
        page += 1


# --------------------------------------------------------------------------- #
# Normalization engine
# --------------------------------------------------------------------------- #

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]{1,}")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def normalize_capabilities(topics: list[str], description: str, source_query: str) -> str:
    """
    Build a clean 4-10 tag comma-string from repo topics + description keywords.
    Topics rank first (curated signal), then high-value description words. Falls
    back to ecosystem tags so every agent is meaningfully searchable.
    """
    ordered: list[str] = []

    def add(tok: str) -> None:
        tok = tok.strip("-").strip()
        if (
            len(tok) >= 2
            and tok not in STOPWORDS
            and tok not in ordered
            and not tok.isdigit()
        ):
            ordered.append(tok)

    # 1) curated topics first
    for t in topics or []:
        add(str(t).lower())

    # 2) high-value description words
    for w in _tokenize(description):
        add(w)

    # 3) pad to >=4 with ecosystem fallbacks matched to the source query
    if len(ordered) < 4:
        fallback = DEFAULT_FALLBACK
        for key, tags in QUERY_FALLBACK_TAGS:
            if key in source_query.lower():
                fallback = tags
                break
        for t in fallback:
            add(t)
            if len(ordered) >= 4:
                break

    return ", ".join(ordered[:10])


def clean_name(raw_name: str) -> str:
    """Turn 'my_cool-agent.server' into 'My Cool Agent Server'."""
    words = re.split(r"[\s_\-.]+", (raw_name or "").strip())
    pretty = " ".join(w.capitalize() for w in words if w)
    return pretty[:256] or raw_name[:256]


# --------------------------------------------------------------------------- #
# Registry pipeline
# --------------------------------------------------------------------------- #

def register_agent(session: requests.Session, repo: dict) -> bool:
    """Compile the payload for one repo and POST it to Beacon. Returns success."""
    slug = repo.get("full_name")
    html_url = repo.get("html_url")
    if not slug or not html_url:
        return False

    tags = normalize_capabilities(
        repo.get("topics", []) or [],
        repo.get("description", "") or "",
        repo.get("_source_query", ""),
    )
    payload = {
        "agent_id": slug,
        "name": clean_name(repo.get("name", slug.split("/")[-1])),
        "mcp_endpoint": html_url,
        "capabilities": tags,        # field the server reads
        "capabilities_tags": tags,   # documented alias, ignored if unused
    }

    try:
        resp = requests.post(REGISTER_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.error("register FAILED (network) %s: %s", slug, exc)
        return False

    if resp.status_code == 200:
        try:
            status = resp.json().get("status", "ok")
        except ValueError:
            status = "ok"
        log.info("indexed %-45s [%s] tags=%s", slug, status, tags)
        return True

    log.error("register FAILED %s -> HTTP %d: %s", slug, resp.status_code, resp.text[:150])
    return False


# --------------------------------------------------------------------------- #
# Main harvest loop
# --------------------------------------------------------------------------- #

def run_once() -> dict:
    session = build_session()
    seen: set[str] = set()
    stats = {"discovered": 0, "indexed": 0, "skipped": 0, "failed": 0}

    log.info("Beacon indexer starting -> %s", REGISTER_ENDPOINT)
    for query in SEARCH_QUERIES:
        log.info("=== searching GitHub: '%s' ===", query)
        try:
            for repo in search_repositories(session, query):
                slug = repo.get("full_name")
                if not slug:
                    continue
                if slug in seen:
                    stats["skipped"] += 1
                    continue
                seen.add(slug)
                stats["discovered"] += 1
                repo["_source_query"] = query
                try:
                    if register_agent(session, repo):
                        stats["indexed"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as exc:  # bulletproof per-repo isolation
                    stats["failed"] += 1
                    log.error("unexpected error indexing %s: %s", slug, exc)
                time.sleep(0.3)  # be gentle on our own registry
        except Exception as exc:  # a bad query must never kill the whole run
            log.error("query '%s' aborted: %s", query, exc)
            continue

    log.info(
        "DONE — discovered=%d indexed=%d failed=%d duplicates_skipped=%d",
        stats["discovered"], stats["indexed"], stats["failed"], stats["skipped"],
    )
    return stats


def main() -> None:
    loop = os.environ.get("LOOP", "").lower() in {"1", "true", "yes"}
    interval = int(os.environ.get("LOOP_INTERVAL_SECS", "21600"))  # default 6h
    if not loop:
        run_once()
        return
    log.info("LOOP mode enabled — re-harvesting every %ds", interval)
    while True:
        try:
            run_once()
        except Exception as exc:
            log.error("run_once crashed, continuing loop: %s", exc)
        log.info("sleeping %ds until next harvest...", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
