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

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, Field, field_validator

import turso

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
        "online": online,
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

class RegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=256)
    name: str = Field(..., min_length=1, max_length=256)
    mcp_endpoint: str = Field(..., min_length=1, max_length=2048)
    capabilities: str = Field("", max_length=4096)

    @field_validator("agent_id", "name", "mcp_endpoint")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must not be blank")
        return v


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

    model_config = {"populate_by_name": True}

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v in {"success", "succeeded", "ok", "pass", "passed", "true", "1"}:
            return "success"
        if v in {"fail", "failed", "failure", "error", "false", "0"}:
            return "fail"
        raise ValueError("status must indicate success or failure")


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

    existing = turso.execute("SELECT agent_id FROM agents WHERE agent_id = ?", [req.agent_id])
    status = "updated" if existing else "registered"

    turso.execute(
        """
        INSERT INTO agents (
            agent_id, name, mcp_endpoint, capabilities_tags,
            success_rate, total_transactions, successful_transactions,
            created_at, last_seen
        ) VALUES (?, ?, ?, ?, 1.0, 0, 0, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            name = excluded.name,
            mcp_endpoint = excluded.mcp_endpoint,
            capabilities_tags = excluded.capabilities_tags,
            last_seen = excluded.last_seen
        """,
        [req.agent_id, req.name, req.mcp_endpoint, tags, now, now],
    )
    row = turso.execute("SELECT * FROM agents WHERE agent_id = ?", [req.agent_id])[0]
    # Fire the endpoint validation after the response is sent.
    background_tasks.add_task(validate_agent_endpoint, req.agent_id, req.mcp_endpoint)
    return {"ok": True, "status": status, "agent": _row_to_public(row)}


@app.post("/api/v1/discover")
def discover(req: DiscoverRequest) -> dict:
    """Capability search, ranked by tag-match score, then success_rate, then volume."""
    _ensure_ready()
    query_tokens = [t for t in _TAG_SPLIT.split(req.query.lower()) if t]
    rows = turso.execute("SELECT * FROM agents")

    scored: list[tuple[int, float, int, dict]] = []
    for row in rows:
        pub = _row_to_public(row)
        if req.online_only and not pub["online"]:
            continue
        tags = set(pub["capabilities_tags"])
        haystack = (row["name"] + " " + (row["capabilities_tags"] or "")).lower()
        score = 0
        for tok in query_tokens:
            if tok in tags:
                score += 2
            elif tok in haystack:
                score += 1
        if score > 0:
            scored.append((score, pub["success_rate"], pub["total_transactions"], pub))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    results = [item[3] for item in scored[: req.limit]]
    return {"ok": True, "count": len(results), "query": req.query, "results": results}


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
    is_success = 1 if req.status == "success" else 0

    # Single atomic statement: increment counters and recompute the ratio from
    # the pre-increment values so the math is exact under concurrency.
    turso.execute(
        """
        UPDATE agents
           SET total_transactions = total_transactions + 1,
               successful_transactions = successful_transactions + ?,
               success_rate = CAST(successful_transactions + ? AS REAL)
                              / (total_transactions + 1),
               last_seen = ?
         WHERE agent_id = ?
        """,
        [is_success, is_success, now, req.agent_id],
    )
    row = turso.execute("SELECT * FROM agents WHERE agent_id = ?", [req.agent_id])[0]
    return {"ok": True, "recorded": req.status, "agent": _row_to_public(row)}


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
def leaderboard(limit: int = 50, online_only: bool = False) -> dict:
    """
    Public leaderboard: top agents ranked by reputation (success_rate DESC, then
    volume). Returns a flat JSON array plus a top-level total_count of every
    registered agent.
    """
    _ensure_ready()
    limit = max(1, min(limit, 500))
    total = turso.execute("SELECT COUNT(*) AS c FROM agents")
    total_count = int(total[0]["c"]) if total else 0
    rows = turso.execute(
        "SELECT * FROM agents ORDER BY success_rate DESC, total_transactions DESC LIMIT ?",
        [limit],
    )
    board = [_row_to_public(r) for r in rows]
    if online_only:
        board = [a for a in board if a["online"]]
    return {"ok": True, "total_count": total_count, "leaderboard": board}


@app.get("/api/v1/agents")
def list_agents(limit: int = 100, online_only: bool = False) -> dict:
    _ensure_ready()
    limit = max(1, min(limit, 500))
    rows = turso.execute(
        "SELECT * FROM agents ORDER BY success_rate DESC, total_transactions DESC LIMIT ?",
        [limit],
    )
    agents = [_row_to_public(r) for r in rows]
    if online_only:
        agents = [a for a in agents if a["online"]]
    return {"ok": True, "count": len(agents), "agents": agents}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
