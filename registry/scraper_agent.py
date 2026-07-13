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
  SQLITE_DB_PATH optional — when set (or turso.py is importable), the indexer
                 preloads all known agent_id / mcp_endpoint values into
                 scraped_nodes_cache (in-memory set) on startup so already-indexed
                 repos skip the register API entirely (zero per-repo DB writes).
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
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://registry-ruby.vercel.app").rstrip("/")
# One-off backlog backfill: re-register already-indexed repos so their
# crawl-time stars/pushed_at land immediately (bypasses the idempotency skip).
BACKFILL = os.environ.get("BACKFILL", "0") == "1"
REGISTER_ENDPOINT = f"{REGISTRY_URL}/api/v1/register"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
MAX_PER_QUERY = int(os.environ.get("MAX_PER_QUERY", "1000"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "10"))  # deep sweep to page=10 (GitHub's 1000-result cap)
THROTTLE_SECS = float(os.environ.get("THROTTLE_SECS", "2"))
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
PER_PAGE = 100
REQUEST_TIMEOUT = 30

# Favor actively-maintained agents: only index repos pushed within this window.
# Dead/abandoned repos are skipped at crawl time (existing ones stay, re-marked
# inactive by enrich_github.py). Set PUSHED_SINCE_DAYS=0 to index regardless.
PUSHED_SINCE_DAYS = int(os.environ.get("PUSHED_SINCE_DAYS", "365"))
_PUSHED_QUALIFIER = ""
if PUSHED_SINCE_DAYS > 0:
    _since = (datetime.now(timezone.utc) - timedelta(days=PUSHED_SINCE_DAYS)).strftime("%Y-%m-%d")
    _PUSHED_QUALIFIER = f" pushed:>{_since}"

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
    # --- expanded horizon: 15 heavy-traffic ecosystem keywords ---
    "langgraph",
    "llamaindex-agent",
    "openagents",
    "babyagi",
    "swarm-agent",
    "ai-agent-framework",
    "crypto-bot",
    "solana-agent",
    "web-scraper-agent",
    "mcp-tool",
    "topic:autonomous-agent",
    "topic:rag-agent",
    "trading-bot agent",
    "topic:ai-assistant",
    "topic:llm-agent",
    # --- canonical ecosystem tags (deep sweep) ---
    "topic:open-mcp",
    "topic:autogen-agent",
    "semantic-kernel",
    "topic:crewai-tool",
    "topic:langgraph-agent",
    "topic:agentops",
    "topic:ai-agent-template",
    "topic:llm-workflow",
    "custom-gpt-agent",
    "topic:voice-agent",
    "autonomous-bot",
    "topic:semantic-kernel",
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
    ("langgraph", ["langgraph", "ai-agent", "graph", "stateful-agent"]),
    ("llamaindex", ["llamaindex", "rag", "ai-agent", "retrieval"]),
    ("autogen", ["autogen", "ai-agent", "multi-agent", "llm"]),
    ("babyagi", ["babyagi", "autonomous-agent", "task-agent", "ai-agent"]),
    ("swarm", ["swarm", "multi-agent", "orchestration", "ai-agent"]),
    ("openagents", ["openagents", "ai-agent", "platform", "llm"]),
    ("solana", ["solana", "crypto", "onchain-agent", "web3"]),
    ("crypto-bot", ["crypto", "trading-bot", "automation", "web3"]),
    ("trading-bot", ["trading-bot", "crypto", "automation", "finance"]),
    ("web-scraper", ["web-scraper", "scraping", "data-extraction", "automation"]),
    ("mcp-tool", ["mcp", "model-context-protocol", "tools", "ai-agent"]),
    ("rag", ["rag", "retrieval", "ai-agent", "llm"]),
    ("ai-assistant", ["ai-assistant", "ai-agent", "llm", "chatbot"]),
    ("autonomous", ["autonomous-agent", "ai-agent", "automation", "llm"]),
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
# In-memory idempotency cache — one DB read on startup, zero per-repo DB hits.
# Keys: normalized owner/repo slugs + github URLs (all lowercase).
# --------------------------------------------------------------------------- #

scraped_nodes_cache: set[str] = set()
_cache_ready = False

# Back-compat alias used elsewhere in docs/scripts.
scraped_repositories_cache = scraped_nodes_cache


def _normalize_slug(slug: str) -> str:
    """Canonical owner/repo key — lowercase, no .git suffix."""
    return (slug or "").strip().lower().removesuffix(".git")


def _github_url_variants(url: str) -> set[str]:
    """All cache keys derivable from a GitHub html_url or mcp_endpoint."""
    keys: set[str] = set()
    u = (url or "").strip()
    if not u:
        return keys
    keys.add(u.lower().rstrip("/"))
    m = re.search(r"github\.com/([^/#?]+/[^/#?]+)", u, re.I)
    if m:
        keys.add(_normalize_slug(m.group(1)))
    return keys


def _repo_cache_keys(slug: str, html_url: str) -> set[str]:
    """Every identifier we treat as 'already indexed' for one repository."""
    keys: set[str] = set()
    if slug:
        keys.add(_normalize_slug(slug))
    keys |= _github_url_variants(html_url)
    return keys


def _load_cache_from_sqlite() -> set[str]:
    """Single query: load all known agent_id + mcp_endpoint values into memory."""
    import turso

    turso.ensure_schema()
    rows = turso.execute("SELECT agent_id, mcp_endpoint FROM agents")
    cache: set[str] = set()
    for row in rows:
        slug = row.get("agent_id") or ""
        endpoint = (row.get("mcp_endpoint") or "").strip()
        cache |= _repo_cache_keys(slug, endpoint)
    return cache


def _load_cache_from_registry(session: requests.Session) -> set[str]:
    """Fallback: paginate registry HTTP API once (no per-repo DB calls)."""
    cache: set[str] = set()
    offset = 0
    page_size = 500
    while True:
        try:
            resp = session.get(
                f"{REGISTRY_URL}/api/v1/leaderboard",
                params={"limit": page_size, "offset": offset},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            log.warning("cache preload from registry failed at offset %d: %s", offset, exc)
            break
        if resp.status_code != 200:
            log.warning("cache preload HTTP %d at offset %d", resp.status_code, offset)
            break
        body = resp.json()
        board = body.get("leaderboard") or []
        if not board:
            break
        for row in board:
            cache |= _repo_cache_keys(row.get("agent_id") or "", row.get("mcp_endpoint") or "")
        offset += len(board)
        total = int(body.get("total_count") or 0)
        if offset >= total or len(board) < page_size:
            break
    return cache


def _sqlite_available() -> bool:
    if os.environ.get("SQLITE_DB_PATH"):
        return True
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("beacon_prod.db", "beacon.db"):
        if os.path.isfile(os.path.join(here, name)):
            return True
    return False


def init_scraped_nodes_cache(session: requests.Session, *, force: bool = False) -> None:
    """
    Warm scraped_nodes_cache — exactly one bulk read from SQLite or registry API.
    Call once at process startup; optional refresh at loop boundaries (still one read).
    """
    global _cache_ready
    if _cache_ready and not force:
        return
    log.info("Initializing scraped_nodes_cache from database (single bulk read)...")
    try:
        if _sqlite_available():
            loaded = _load_cache_from_sqlite()
            source = "SQLite"
        else:
            loaded = _load_cache_from_registry(session)
            source = "registry API"
        scraped_nodes_cache.clear()
        scraped_nodes_cache.update(loaded)
        log.info(
            "scraped_nodes_cache ready — %d keys from %s",
            len(scraped_nodes_cache),
            source,
        )
    except Exception as exc:
        log.warning("Could not warm scraped_nodes_cache (%s) — starting empty", exc)
        scraped_nodes_cache.clear()
    _cache_ready = True


def ensure_scraped_cache(session: requests.Session) -> None:
    """Backward-compatible entry point."""
    init_scraped_nodes_cache(session)


def _already_indexed(slug: str, html_url: str) -> bool:
    """O(1) memory check — skip before any register API / DB write."""
    return bool(_repo_cache_keys(slug, html_url) & scraped_nodes_cache)


def _remember_indexed(slug: str, html_url: str) -> None:
    """Update cache immediately after a successful register (new or updated)."""
    scraped_nodes_cache.update(_repo_cache_keys(slug, html_url))


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
    while harvested < MAX_PER_QUERY and page <= MAX_PAGES:
        params = {
            "q": query + _PUSHED_QUALIFIER,
            "sort": "updated",  # freshest first — active agents lead the harvest
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
        "source": "scraper",         # analytics: mark harvested vs organic SDK
        # Enrich at crawl time — these are already in the GitHub search response,
        # so the repo is scored/active immediately instead of waiting for the
        # separate enrichment pass to backfill it.
        "stars": int(repo.get("stargazers_count", 0) or 0),
        "open_issues": int(repo.get("open_issues_count", 0) or 0),
        "pushed_at": repo.get("pushed_at"),
    }

    try:
        resp = requests.post(REGISTER_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.error("register FAILED (network) %s: %s", slug, exc)
        return False

    if resp.status_code == 200:
        try:
            body = resp.json()
            status = body.get("status", "ok")
        except ValueError:
            status = "ok"
        # Always update cache on success — including "updated" (idempotent re-register).
        _remember_indexed(slug, html_url)
        log.info("indexed %-45s [%s] tags=%s", slug, status, tags)
        return True

    log.error("register FAILED %s -> HTTP %d: %s", slug, resp.status_code, resp.text[:150])
    return False


# --------------------------------------------------------------------------- #
# Main harvest loop
# --------------------------------------------------------------------------- #

def run_once(*, refresh_cache: bool = False) -> dict:
    session = build_session()
    init_scraped_nodes_cache(session, force=refresh_cache)
    stats = {
        "discovered": 0,
        "indexed": 0,
        "skipped": 0,
        "memory_skipped": 0,
        "failed": 0,
        "cache_keys": len(scraped_nodes_cache),
    }

    log.info("Beacon indexer starting -> %s (cache: %d keys)", REGISTER_ENDPOINT, len(scraped_nodes_cache))
    for query in SEARCH_QUERIES:
        log.info("=== searching GitHub: '%s' ===", query)
        query_new = 0
        query_skipped = 0
        try:
            for repo in search_repositories(session, query):
                slug = repo.get("full_name") or ""
                html_url = repo.get("html_url") or ""
                if not slug:
                    continue

                # Idempotency gate — no register API, no DB read/write beyond memory.
                # BACKFILL=1 bypasses it for a one-off pass that re-registers found
                # repos WITH crawl-time stars/pushed_at, scoring the existing
                # backlog at 100 repos/API-call instead of enrichment's 1/call.
                if not BACKFILL and _already_indexed(slug, html_url):
                    stats["memory_skipped"] += 1
                    query_skipped += 1
                    if stats["memory_skipped"] <= 3 or stats["memory_skipped"] % 1000 == 0:
                        log.debug("skip %s — in scraped_nodes_cache", slug)
                    continue

                stats["discovered"] += 1
                query_new += 1
                repo["_source_query"] = query
                try:
                    if register_agent(session, repo):
                        stats["indexed"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    log.error("unexpected error indexing %s: %s", slug, exc)
                time.sleep(0.08)
        except Exception as exc:
            log.error("query '%s' aborted: %s", query, exc)
            continue

        if query_new == 0 and query_skipped > 0:
            log.info("query '%s' — all %d results already cached, no DB writes", query, query_skipped)

    log.info(
        "DONE — discovered=%d indexed=%d failed=%d memory_skipped=%d cache_keys=%d",
        stats["discovered"],
        stats["indexed"],
        stats["failed"],
        stats["memory_skipped"],
        len(scraped_nodes_cache),
    )
    if stats["discovered"] == 0 and stats["memory_skipped"] > 100:
        log.info(
            "Harvest fully idempotent this run (%d cache hits). "
            "Increase LOOP_INTERVAL_SECS to reduce GitHub API usage.",
            stats["memory_skipped"],
        )
    return stats


def main() -> None:
    loop = os.environ.get("LOOP", "").lower() in {"1", "true", "yes"}
    interval = int(os.environ.get("LOOP_INTERVAL_SECS", "21600"))  # default 6h
    refresh_each_loop = os.environ.get("CACHE_REFRESH_ON_LOOP", "1").lower() in {"1", "true", "yes"}
    if not loop:
        run_once()
        return
    log.info("LOOP mode — interval=%ds cache_refresh_each_loop=%s", interval, refresh_each_loop)
    first = True
    while True:
        try:
            run_once(refresh_cache=refresh_each_loop and not first)
            first = False
        except Exception as exc:
            log.error("run_once crashed, continuing loop: %s", exc)
        log.info("sleeping %ds until next harvest...", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
