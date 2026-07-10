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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import turso

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
    online = False
    try:
        seen_dt = datetime.fromisoformat(last_seen)
        if seen_dt.tzinfo is None:
            seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        online = (_utcnow() - seen_dt).total_seconds() <= ONLINE_WINDOW_SECONDS
    except (TypeError, ValueError):
        online = False
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
        "online": online,
    }


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
    job_status: str = Field(..., min_length=1, max_length=32)

    @field_validator("job_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v in {"success", "succeeded", "ok", "pass", "passed", "true", "1"}:
            return "success"
        if v in {"fail", "failed", "failure", "error", "false", "0"}:
            return "fail"
        raise ValueError("job_status must indicate success or failure")


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
def register(req: RegisterRequest) -> dict:
    """Self-Discovery hook. Atomic UPSERT: insert new, or refresh existing."""
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
    """Heartbeat + job monitor. Atomic counter update recomputes success_rate."""
    _ensure_ready()
    now = _utcnow().isoformat()
    is_success = 1 if req.job_status == "success" else 0

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
    row = turso.execute("SELECT * FROM agents WHERE agent_id = ?", [req.agent_id])
    if not row:
        raise HTTPException(status_code=404, detail="agent_id not registered")
    return {"ok": True, "recorded": req.job_status, "agent": _row_to_public(row[0])}


@app.get("/api/v1/leaderboard")
def leaderboard(limit: int = 50) -> dict:
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
    return {"ok": True, "total_count": total_count, "leaderboard": [_row_to_public(r) for r in rows]}


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
