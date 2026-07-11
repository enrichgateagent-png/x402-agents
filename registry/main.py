"""
Beacon — Central Discovery & Reputation Server for autonomous AI agents.

Google indexes websites so humans can find them; Beacon indexes agents so agents
can find each other. FastAPI service backed by Turso (managed libSQL/SQLite) over
its HTTP API, so it runs anywhere — including serverless (Vercel) — with durable
storage and no local disk.

Agents self-register on boot, are discovered by capability, and report job
telemetry that continuously updates their reputation (success_rate).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

import html

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import AliasChoices, BaseModel, Field, field_validator

import turso

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://registry-ruby.vercel.app").rstrip("/")
VALIDATION_TIMEOUT = float(os.environ.get("VALIDATION_TIMEOUT", "6"))
# Endpoint schemes that are process-local (not HTTP) and can't be pinged.
_NON_HTTP_PREFIXES = ("framework://", "eliza://", "local://", "mcp://")

ONLINE_WINDOW_SECONDS = int(os.environ.get("REGISTRY_ONLINE_WINDOW", "300"))
MAX_DISCOVER_RESULTS = int(os.environ.get("REGISTRY_MAX_RESULTS", "25"))

_TAG_SPLIT = re.compile(r"[,\s]+")
_schema_ready = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_ready() -> None:
    global _schema_ready
    if not _schema_ready:
        turso.ensure_schema()
        _schema_ready = True


def _normalize_tags(raw: str) -> str:
    seen: list[str] = []
    for tok in _TAG_SPLIT.split(raw or ""):
        tok = tok.strip().lower()
        if tok and tok not in seen:
            seen.append(tok)
    return ",".join(seen)


ACTIVE_WINDOW_DAYS = int(os.environ.get("ACTIVE_WINDOW_DAYS", "90"))


def _pushed_recently(pushed_at: Optional[str]) -> bool:
    """True if the repo saw native activity within ACTIVE_WINDOW_DAYS."""
    if not pushed_at:
        return False
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (_utcnow() - dt).days <= ACTIVE_WINDOW_DAYS
    except (TypeError, ValueError):
        return False


def _row_to_public(row: dict) -> dict:
    last_seen = row["last_seen"]
    recent = False
    try:
        seen_dt = datetime.fromisoformat(last_seen)
        if seen_dt.tzinfo is None:
            seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        recent = (_utcnow() - seen_dt).total_seconds() <= ONLINE_WINDOW_SECONDS
    except (TypeError, ValueError):
        recent = False
    # An agent is "online" only if it was seen recently AND its endpoint last
    # validated as reachable. `reachable` defaults to 1 for rows predating the
    # validator column.
    reachable = bool(int(row.get("reachable", 1) or 0))
    online = recent and reachable
    return {
        "agent_id": row["agent_id"],
        "name": row["name"],
        "mcp_endpoint": row["mcp_endpoint"],
        "capabilities_tags": [t for t in (row["capabilities_tags"] or "").split(",") if t],
        "success_rate": round(float(row["success_rate"]), 4),
        "total_transactions": int(row["total_transactions"]),
        "successful_transactions": int(row["successful_transactions"]),
        "last_seen": last_seen,
        "created_at": row["created_at"],
        "reachable": reachable,
        "last_validated": row.get("last_validated"),
        "registration_source": row.get("registration_source", "sdk"),
        "online": online,
        # Real GitHub traction (populated by enrich_github.py for scraped repos).
        "stars": int(row.get("stars", 0) or 0),
        "pushed_at": row.get("pushed_at"),
        "open_issues": int(row.get("open_issues", 0) or 0),
        "active": _pushed_recently(row.get("pushed_at")),
        "fraud_status": {
            "is_flagged": bool(int(row.get("is_fraudulent", 0) or 0)),
            "strikes": int(row.get("fraud_strikes", 0) or 0),
            "reason": row.get("fraud_reason"),
        },
    }


# --------------------------------------------------------------------------- #
# Endpoint validator
# --------------------------------------------------------------------------- #

def _probe(endpoint: str) -> bool:
    """Lightweight reachability check. HEAD first, GET fallback. <400 or 405 = up."""
    if not endpoint or endpoint.startswith(_NON_HTTP_PREFIXES):
        # Process-local endpoints can't be HTTP-pinged; treat as reachable so we
        # don't falsely mark in-framework agents offline.
        return endpoint.startswith(_NON_HTTP_PREFIXES)
    if not endpoint.startswith(("http://", "https://")):
        return False
    headers = {"User-Agent": "beacon-validator/1.0"}
    try:
        r = requests.head(endpoint, timeout=VALIDATION_TIMEOUT, allow_redirects=True, headers=headers)
        if r.status_code < 400 or r.status_code in (403, 405):
            return True
        # Some hosts reject HEAD; confirm with a ranged GET.
        r = requests.get(endpoint, timeout=VALIDATION_TIMEOUT, allow_redirects=True,
                         headers={**headers, "Range": "bytes=0-0"}, stream=True)
        r.close()
        return r.status_code < 400 or r.status_code == 403
    except requests.RequestException:
        return False


def validate_agent_endpoint(agent_id: str, endpoint: str) -> bool:
    """
    Background worker: ping an agent's endpoint and persist the result.
    Sets reachable=1/0 and last_validated so discovery/leaderboard can surface
    only live agents. Never raises — validation must not disturb the API.
    """
    now = _utcnow().isoformat()
    try:
        reachable = _probe(endpoint)
        turso.execute(
            "UPDATE agents SET reachable = ?, last_validated = ? WHERE agent_id = ?",
            [1 if reachable else 0, now, agent_id],
        )
        return reachable
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

_KNOWN_SOURCES = {"sdk", "scraper", "auto-inject", "eliza", "manual"}


class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=256)
    name: str = Field(..., min_length=1, max_length=256)
    mcp_endpoint: str = Field(..., min_length=1, max_length=2048)
    capabilities: str = Field("", max_length=4096)
    # Analytics: distinguish organic SDK/plugin registrations from the scraper.
    source: str = Field("sdk", max_length=32)

    @field_validator("agent_id", "name", "mcp_endpoint")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must not be blank")
        return v

    @field_validator("source")
    @classmethod
    def _norm_source(cls, v: str) -> str:
        v = (v or "sdk").strip().lower()
        return v if v in _KNOWN_SOURCES else "sdk"


class DiscoverRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1024)
    limit: int = Field(MAX_DISCOVER_RESULTS, ge=1, le=100)
    online_only: bool = False


class TelemetryRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=256)
    # Accept the canonical `status` key and the legacy `job_status` alias so
    # every SDK/monkey-patch version keeps working.
    status: str = Field(
        ...,
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("status", "job_status"),
    )

    reason: Optional[str] = Field(None, max_length=500)

    model_config = {"populate_by_name": True}

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v in {"success", "succeeded", "ok", "pass", "passed", "true", "1"}:
            return "success"
        if v in {"fail", "failed", "failure", "error", "false", "0"}:
            return "fail"
        if v in {"fraud", "fraudulent", "malicious", "abuse", "spam"}:
            return "fraud"
        raise ValueError("status must be success, fail, or fraud")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Beacon Agent Registry",
    description="Beacon — Autonomous AI Agent Discovery & Reputation Registry.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(turso.TursoError)
async def _turso_err(request: Request, exc: turso.TursoError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"ok": False, "error": "storage_unavailable", "detail": str(exc)})


@app.get("/")
def root() -> dict:
    return {
        "service": "beacon-agent-registry",
        "tagline": "Google indexes websites for humans; Beacon indexes agents for agents.",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/v1/register",
            "POST /api/v1/discover",
            "POST /api/v1/telemetry",
            "GET  /api/v1/agents",
            "GET  /healthz",
        ],
    }


@app.get("/healthz")
def healthz() -> dict:
    _ensure_ready()
    rows = turso.execute("SELECT COUNT(*) AS c FROM agents")
    return {"ok": True, "agents": int(rows[0]["c"]) if rows else 0, "time": _utcnow().isoformat()}


@app.post("/api/v1/register")
def register(req: RegisterRequest, background_tasks: BackgroundTasks) -> dict:
    """Self-Discovery hook. Atomic UPSERT: insert new, or refresh existing.

    Schedules an endpoint validation to run after the response is returned.
    """
    _ensure_ready()
    now = _utcnow().isoformat()
    tags = _normalize_tags(req.capabilities)

    # Integrity guard: a bare github.com repo URL can only originate from the
    # harvester, never from a real self-registering agent. Force 'scraper' so the
    # organic-vs-scraped analytics can't be polluted by a mislabeled source.
    source = req.source
    if "github.com" in req.mcp_endpoint.lower():
        source = "scraper"

    existing = turso.execute("SELECT agent_id FROM agents WHERE agent_id = ?", [req.agent_id])
    status = "updated" if existing else "registered"

    turso.execute(
        """
        INSERT INTO agents (
            agent_id, name, mcp_endpoint, capabilities_tags,
            success_rate, total_transactions, successful_transactions,
            created_at, last_seen, registration_source
        ) VALUES (?, ?, ?, ?, 1.0, 0, 0, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            name = excluded.name,
            mcp_endpoint = excluded.mcp_endpoint,
            capabilities_tags = excluded.capabilities_tags,
            last_seen = excluded.last_seen,
            -- 'sdk' (organic) is sticky: a later scraper pass must not
            -- overwrite an agent that once registered itself organically.
            registration_source = CASE
                -- a scraper/github signal always wins (fixes prior mislabeling)
                WHEN excluded.registration_source = 'scraper' THEN 'scraper'
                WHEN excluded.registration_source = 'sdk'
                     AND agents.registration_source = 'scraper' THEN 'scraper'
                WHEN excluded.registration_source = 'sdk' THEN 'sdk'
                ELSE excluded.registration_source
            END
        """,
        [req.agent_id, req.name, req.mcp_endpoint, tags, now, now, source],
    )
    row = turso.execute("SELECT * FROM agents WHERE agent_id = ?", [req.agent_id])[0]
    # Fire the endpoint validation after the response is sent.
    background_tasks.add_task(validate_agent_endpoint, req.agent_id, req.mcp_endpoint)

    # Copy-paste-ready badge for the developer's README (drives the growth loop).
    from urllib.parse import quote
    badge_url = f"{PUBLIC_BASE_URL}/api/v1/agents/{quote(req.agent_id)}/badge.svg"
    badge_markdown = f"![Beacon Verified]({badge_url})"

    return {
        "ok": True,
        "status": status,
        "agent": _row_to_public(row),
        "badge_url": badge_url,
        "badge_markdown": badge_markdown,
    }


# Lightweight semantic map: each concept -> related capability tokens. Used only
# as a fallback when literal keyword matching is sparse, so precise queries stay
# precise while vague/cross-cutting ones still surface relevant agents.
SEMANTIC_SYNONYMS: dict[str, list[str]] = {
    "audit": ["compliance", "solana-agent", "verification", "security", "kyb"],
    "auditing": ["compliance", "solana-agent", "verification", "security"],
    "security": ["compliance", "solana-agent", "verification", "audit", "guardrail"],
    "compliance": ["kyb", "vat", "lei", "verification", "legal"],
    "trading": ["crypto", "defi", "finance", "trading-bot", "market", "solana"],
    "trade": ["crypto", "defi", "trading-bot", "market"],
    "crypto": ["defi", "web3", "solana", "onchain", "wallet", "trading"],
    "payment": ["x402", "usdc", "wallet", "crypto", "billing"],
    "scrape": ["scraping", "crawler", "web-scraper", "extraction", "data"],
    "scraping": ["crawler", "web-scraper", "extraction", "harvest"],
    "search": ["retrieval", "discovery", "web-search", "neural-search", "index"],
    "pdf": ["document", "extraction", "ocr", "structured-json", "invoice"],
    "document": ["pdf", "ocr", "extraction", "parsing"],
    "chat": ["conversation", "assistant", "chatbot", "llm"],
    "voice": ["speech", "audio", "tts", "stt"],
    "image": ["vision", "multimodal", "generation", "diffusion"],
    "memory": ["rag", "retrieval", "storage", "long-term-memory", "embeddings"],
    "rag": ["retrieval", "memory", "embeddings", "vector", "knowledge"],
    "research": ["analysis", "synthesis", "summarize", "report", "brief"],
    "news": ["headlines", "feed", "media", "sentiment"],
    "data": ["scraper", "mcp-tool", "analytics", "dataset", "extraction"],
    "automation": ["workflow", "orchestration", "agent", "pipeline"],
    "multi-agent": ["orchestration", "swarm", "crew", "collaboration"],
    "mcp": ["model-context-protocol", "tools", "server", "mcp-server"],
    "monitor": ["observability", "telemetry", "analytics", "tracking"],
}


def _score_rows(
    rows: list[dict],
    tokens: list[str],
    online_only: bool,
    w_exact: int,
    w_sub: int,
) -> dict[str, tuple[int, dict]]:
    """Score every agent against a token set. Returns {agent_id: (score, public)}."""
    out: dict[str, tuple[int, dict]] = {}
    for row in rows:
        # Defense: fraudulent nodes are never surfaced through discovery.
        if int(row.get("is_fraudulent", 0) or 0):
            continue
        pub = _row_to_public(row)
        if online_only and not pub["online"]:
            continue
        tags = set(pub["capabilities_tags"])
        haystack = (row["name"] + " " + (row["capabilities_tags"] or "")).lower()
        score = 0
        for tok in tokens:
            if tok in tags:
                score += w_exact
            elif tok in haystack:
                score += w_sub
        if score > 0:
            out[pub["agent_id"]] = (score, pub)
    return out


def _expand_tokens(tokens: list[str]) -> list[str]:
    expanded: list[str] = []
    for tok in tokens:
        for syn in SEMANTIC_SYNONYMS.get(tok, []):
            if syn not in expanded and syn not in tokens:
                expanded.append(syn)
    return expanded


@app.post("/api/v1/discover")
def discover(req: DiscoverRequest) -> dict:
    """
    Capability search ranked by match score, then success_rate, then volume.

    Two-stage: literal keyword scoring first. If that yields few results, expand
    the query through a semantic synonym map and re-score with a lower weight, so
    cross-cutting matches surface even when word-for-word matching is zero —
    without diluting precise queries that already match well.
    """
    _ensure_ready()
    query_tokens = [t for t in _TAG_SPLIT.split(req.query.lower()) if t]
    rows = turso.execute("SELECT * FROM agents")

    # Stage 1 — literal match (exact tag = 2, substring = 1).
    combined = _score_rows(rows, query_tokens, req.online_only, 2, 1)

    # Stage 2 — semantic fallback when literal results are sparse.
    semantic_expanded = False
    SEMANTIC_MIN = 3
    if len(combined) < SEMANTIC_MIN:
        expanded = _expand_tokens(query_tokens)
        if expanded:
            semantic_expanded = True
            for agent_id, (score, pub) in _score_rows(rows, expanded, req.online_only, 1, 1).items():
                if agent_id in combined:
                    # keep the stronger (literal) score if already matched
                    if score > combined[agent_id][0]:
                        combined[agent_id] = (score, pub)
                else:
                    combined[agent_id] = (score, pub)

    scored = sorted(
        combined.values(),
        key=lambda x: (x[0], x[1]["success_rate"], x[1]["total_transactions"]),
        reverse=True,
    )
    results = [pub for _, pub in scored[: req.limit]]
    return {
        "ok": True,
        "count": len(results),
        "query": req.query,
        "semantic_expanded": semantic_expanded,
        "results": results,
    }


@app.post("/api/v1/telemetry")
def telemetry(req: TelemetryRequest) -> dict:
    """
    Reputation engine. Accepts {"agent_id", "status": "success"|"fail"} and
    atomically recomputes the agent's counters and success_rate in Turso:

        total_transactions       += 1
        successful_transactions  += (1 if success else 0)
        success_rate              = successful_transactions / total_transactions

    Rogue-metric guard: only a currently-registered agent_id can submit. The
    UPDATE ... WHERE agent_id = ? is a no-op for unknown ids, which we detect and
    reject with 404 — an unregistered/fake agent cannot move any ranking.
    """
    _ensure_ready()

    # Reject unknown agents up front so fabricated ids can't touch the table.
    exists = turso.execute("SELECT 1 AS x FROM agents WHERE agent_id = ?", [req.agent_id])
    if not exists:
        raise HTTPException(status_code=404, detail="agent_id not registered")

    now = _utcnow().isoformat()
    s = 1 if req.status == "success" else 0            # successful_transactions delta
    f = 1 if req.status == "fraud" else 0              # fraud_strikes delta
    t = 1                                              # every event counts as a transaction
    reason = req.reason.strip() if req.reason else None

    # One atomic statement handles counters, auto-flagging at >=3 strikes, and the
    # penalized success_rate. All CASE expressions read pre-increment column values,
    # so the (fraud_strikes + f) lookahead computes the post-event strike count.
    #   success_rate = successful / (total + fraud_strikes*2)
    # Fraud strikes weigh 2x a plain failure in the denominator — a heavier penalty.
    turso.execute(
        """
        UPDATE agents
           SET successful_transactions = successful_transactions + ?,
               total_transactions      = total_transactions + ?,
               fraud_strikes           = fraud_strikes + ?,
               is_fraudulent = CASE WHEN (fraud_strikes + ?) >= 3 THEN 1 ELSE is_fraudulent END,
               fraud_reason  = CASE WHEN (fraud_strikes + ?) >= 3
                                    THEN COALESCE(?, fraud_reason, 'auto-flagged: 3+ fraud strikes')
                                    ELSE fraud_reason END,
               success_rate = CAST(successful_transactions + ? AS REAL)
                              / (total_transactions + ? + (fraud_strikes + ?) * 2),
               last_seen = ?
         WHERE agent_id = ?
        """,
        [s, t, f, f, f, reason, s, t, f, now, req.agent_id],
    )
    row = turso.execute("SELECT * FROM agents WHERE agent_id = ?", [req.agent_id])[0]
    return {"ok": True, "recorded": req.status, "agent": _row_to_public(row)}


def _badge_char_width(s: str) -> int:
    """Approximate rendered width (px) of a string at font-size 11, Verdana-ish."""
    narrow = set("ijl.,:'|! ")
    wide = set("mwMW@")
    w = 0.0
    for ch in s:
        if ch in narrow:
            w += 3.5
        elif ch in wide:
            w += 9.5
        else:
            w += 6.6
    return int(w)


def _render_badge(label: str, message: str, color: str) -> str:
    """Flat 'shields'-style two-segment SVG badge, self-contained."""
    pad = 10
    lw = _badge_char_width(label) + pad * 2
    mw = _badge_char_width(message) + pad * 2
    total = lw + mw
    label_e = html.escape(label)
    message_e = html.escape(message)
    # x positions are in the 10x-scaled text space shields uses for crisp text.
    lx = lw * 5
    mx = (lw + mw / 2) * 10
    ltl = (_badge_char_width(label)) * 10
    mtl = (_badge_char_width(message)) * 10
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total}" height="20" role="img" aria-label="{label_e}: {message_e}">
  <title>{label_e}: {message_e}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{lw}" height="20" fill="#414141"/>
    <rect x="{lw}" width="{mw}" height="20" fill="{color}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110" text-rendering="geometricPrecision">
    <text aria-hidden="true" x="{lx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{ltl}">{label_e}</text>
    <text x="{lx}" y="140" transform="scale(.1)" textLength="{ltl}">{label_e}</text>
    <text aria-hidden="true" x="{mx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{mtl}">{message_e}</text>
    <text x="{mx}" y="140" transform="scale(.1)" textLength="{mtl}">{message_e}</text>
  </g>
</svg>"""


@app.get("/api/v1/agents/{agent_id:path}/badge.svg")
def agent_badge(agent_id: str) -> Response:
    """
    Live SVG reputation badge for a developer's README. Regenerated per request so
    it reflects current telemetry. States: unknown (gray), flagged (crimson),
    verified (emerald with success %).
    """
    _ensure_ready()
    rows = turso.execute(
        "SELECT success_rate, is_fraudulent FROM agents WHERE agent_id = ?", [agent_id]
    )
    if not rows:
        label, message, color = "Beacon", "Unknown", "#9f9f9f"
    elif int(rows[0].get("is_fraudulent", 0) or 0):
        label, message, color = "Beacon", "Flagged Threat", "#a01212"
    else:
        pct = round(float(rows[0]["success_rate"]) * 100)
        label, message, color = "Beacon Verified", f"{pct}% Success", "#2ea043"

    svg = _render_badge(label, message, color)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            # Always-fresh so the badge tracks telemetry in real time.
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/v1/growth/trending")
def growth_trending(limit: int = 20) -> dict:
    """
    Growth showcase: newly onboarded organic (SDK/plugin) nodes, newest first —
    the agents that adopted Beacon directly rather than being harvested. Returns
    a clean feed for a launch page / 'who's building on Beacon' widget.
    """
    _ensure_ready()
    limit = max(1, min(limit, 100))
    rows = turso.execute(
        "SELECT * FROM agents WHERE registration_source = 'sdk' "
        "ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    agents = [_row_to_public(r) for r in rows]
    total = turso.execute(
        "SELECT COUNT(*) AS c FROM agents WHERE registration_source = 'sdk'"
    )
    return {
        "ok": True,
        "organic_total": int(total[0]["c"]) if total else 0,
        "count": len(agents),
        "trending": agents,
    }


@app.get("/api/v1/radar")
def radar(limit: int = 100) -> dict:
    """
    Organic-adoption radar: the newest agents that registered via the SDK /
    auto-inject / Eliza plugins (registration_source = 'sdk'), newest first.
    Lets us watch outside developers hit the platform in real time.
    """
    _ensure_ready()
    limit = max(1, min(limit, 500))
    rows = turso.execute(
        "SELECT agent_id, name, mcp_endpoint, capabilities_tags, created_at "
        "FROM agents WHERE registration_source = 'sdk' "
        "ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    agents = [
        {
            "agent_id": r["agent_id"],
            "name": r["name"],
            "mcp_endpoint": r["mcp_endpoint"],
            "capabilities_tags": [t for t in (r["capabilities_tags"] or "").split(",") if t],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {"ok": True, "count": len(agents), "agents": agents}


@app.post("/api/v1/validate")
def validate_batch(limit: int = 25) -> dict:
    """
    Batch validator — the serverless-reliable path (call from cron). Re-checks the
    least-recently-validated agents and persists reachability. On Vercel, the
    per-register BackgroundTask may be frozen after the response, so this endpoint
    guarantees validation coverage when hit on a schedule.
    """
    _ensure_ready()
    limit = max(1, min(limit, 100))
    rows = turso.execute(
        "SELECT agent_id, mcp_endpoint FROM agents "
        "ORDER BY (last_validated IS NULL) DESC, last_validated ASC LIMIT ?",
        [limit],
    )
    checked, online, offline = 0, 0, 0
    for r in rows:
        ok = validate_agent_endpoint(r["agent_id"], r["mcp_endpoint"])
        checked += 1
        online += 1 if ok else 0
        offline += 0 if ok else 1
    return {"ok": True, "checked": checked, "online": online, "offline": offline}


@app.get("/api/v1/leaderboard")
def leaderboard(limit: int = 50, offset: int = 0, online_only: bool = False) -> dict:
    """
    Public leaderboard: top agents ranked by reputation (success_rate DESC, then
    volume). Returns a flat JSON array plus a top-level total_count of every
    registered agent.
    """
    _ensure_ready()
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    # Split-metrics summary: total + organic (sdk) vs scraped registrations.
    src_rows = turso.execute(
        "SELECT registration_source AS s, COUNT(*) AS c FROM agents GROUP BY registration_source"
    )
    by_source = {r["s"] or "sdk": int(r["c"]) for r in src_rows}
    total_count = sum(by_source.values())
    summary = {
        "total_agents": total_count,
        "organic_sdk_registrations": by_source.get("sdk", 0),
        "scraped_registrations": by_source.get("scraper", 0),
        "by_source": by_source,
    }

    # Defense: flagged agents are drastically demoted (is_fraudulent ASC sinks
    # them to the bottom) but still returned so the portal can render a red
    # "FRAUD WARNING" badge via each row's fraud_status.
    rows = turso.execute(
        "SELECT * FROM agents "
        "ORDER BY is_fraudulent ASC, success_rate DESC, stars DESC, total_transactions DESC "
        "LIMIT ? OFFSET ?",
        [limit, offset],
    )
    board = [_row_to_public(r) for r in rows]
    if online_only:
        board = [a for a in board if a["online"]]

    # Flagged agents are demoted out of the main board at scale, so surface them
    # in a dedicated array — the portal renders these as red "FRAUD WARNING"
    # cards regardless of their rank.
    flagged_rows = turso.execute(
        "SELECT * FROM agents WHERE is_fraudulent = 1 ORDER BY fraud_strikes DESC LIMIT 100"
    )
    flagged = [_row_to_public(r) for r in flagged_rows]

    # Split-metrics promoted to top level per the analytics contract; `summary`
    # retained for the richer by_source breakdown.
    return {
        "ok": True,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "returned": len(board),
        "organic_sdk_registrations": by_source.get("sdk", 0),
        "scraped_registrations": by_source.get("scraper", 0),
        "flagged_count": len(flagged),
        "summary": summary,
        "leaderboard": board,
        "flagged_agents": flagged,
    }


@app.get("/api/v1/agents")
def list_agents(limit: int = 100, online_only: bool = False, sort: str = "top") -> dict:
    """sort=top (reputation/stars) or sort=recent (newest indexed first)."""
    _ensure_ready()
    limit = max(1, min(limit, 500))
    order = (
        "created_at DESC"
        if sort == "recent"
        else "is_fraudulent ASC, success_rate DESC, stars DESC, total_transactions DESC"
    )
    rows = turso.execute(f"SELECT * FROM agents ORDER BY {order} LIMIT ?", [limit])
    agents = [_row_to_public(r) for r in rows]
    if online_only:
        agents = [a for a in agents if a["online"]]
    return {"ok": True, "count": len(agents), "agents": agents}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
