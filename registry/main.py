"""
Beacon — Central Discovery & Reputation Server for autonomous AI agents.

Google indexes websites so humans can find them; Beacon indexes agents so agents
can find each other. A production FastAPI service backing the Autonomous AI Agent
Discovery & Reputation Registry. Agents self-register on boot, are discovered by
capability, and report job telemetry that continuously updates their reputation
(success_rate).

Storage is SQLite in WAL mode for durable, concurrent-friendly file persistence.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DB_PATH = os.environ.get("REGISTRY_DB_PATH", "registry.db")
# An agent is considered "online" if it has been seen within this window.
ONLINE_WINDOW_SECONDS = int(os.environ.get("REGISTRY_ONLINE_WINDOW", "300"))
MAX_DISCOVER_RESULTS = int(os.environ.get("REGISTRY_MAX_RESULTS", "25"))

_TAG_SPLIT = re.compile(r"[,\s]+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_tags(raw: str) -> str:
    """Lower-case, de-duplicate, comma-join capability tags."""
    seen: list[str] = []
    for tok in _TAG_SPLIT.split(raw or ""):
        tok = tok.strip().lower()
        if tok and tok not in seen:
            seen.append(tok)
    return ",".join(seen)


# --------------------------------------------------------------------------- #
# Database layer
# --------------------------------------------------------------------------- #

def get_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection tuned for production file storage.

    check_same_thread=False lets FastAPI's threadpool reuse connections safely
    because every request opens and closes its own short-lived connection.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL: concurrent readers while a writer is active + crash-safe durability.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create the schema and indexes if they do not yet exist."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                agent_id          TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                mcp_endpoint      TEXT NOT NULL,
                capabilities_tags TEXT NOT NULL DEFAULT '',
                success_rate      REAL NOT NULL DEFAULT 1.0,
                total_transactions INTEGER NOT NULL DEFAULT 0,
                successful_transactions INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT NOT NULL,
                last_seen         TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agents_success ON agents(success_rate DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen DESC);"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_public(row: sqlite3.Row) -> dict:
    """Serialize a DB row into the public JSON shape returned by the API."""
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
        "success_rate": round(row["success_rate"], 4),
        "total_transactions": row["total_transactions"],
        "successful_transactions": row["successful_transactions"],
        "last_seen": last_seen,
        "created_at": row["created_at"],
        "online": online,
    }


# --------------------------------------------------------------------------- #
# Request / response models
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
        # Accept common spellings so heterogeneous agent frameworks all work.
        if v in {"success", "succeeded", "ok", "pass", "passed", "true", "1"}:
            return "success"
        if v in {"fail", "failed", "failure", "error", "false", "0"}:
            return "fail"
        raise ValueError("job_status must indicate success or failure")


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Beacon Agent Registry",
    description="Beacon — Autonomous AI Agent Discovery & Reputation Registry.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"ok": False, "error": "internal_error"})


def db_dep() -> sqlite3.Connection:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


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
def healthz(conn: sqlite3.Connection = Depends(db_dep)) -> dict:
    count = conn.execute("SELECT COUNT(*) AS c FROM agents").fetchone()["c"]
    return {"ok": True, "agents": count, "time": _utcnow().isoformat()}


@app.post("/api/v1/register")
def register(req: RegisterRequest, conn: sqlite3.Connection = Depends(db_dep)) -> dict:
    """
    Self-Discovery hook. Upsert semantics:
      - existing agent_id -> refresh last_seen, name, endpoint, capabilities
      - new agent_id      -> insert with a clean reputation
    """
    now = _utcnow().isoformat()
    tags = _normalize_tags(req.capabilities)
    existing = conn.execute(
        "SELECT agent_id FROM agents WHERE agent_id = ?", (req.agent_id,)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE agents
               SET name = ?, mcp_endpoint = ?, capabilities_tags = ?, last_seen = ?
             WHERE agent_id = ?
            """,
            (req.name, req.mcp_endpoint, tags, now, req.agent_id),
        )
        conn.commit()
        status = "updated"
    else:
        conn.execute(
            """
            INSERT INTO agents (
                agent_id, name, mcp_endpoint, capabilities_tags,
                success_rate, total_transactions, successful_transactions,
                created_at, last_seen
            ) VALUES (?, ?, ?, ?, 1.0, 0, 0, ?, ?)
            """,
            (req.agent_id, req.name, req.mcp_endpoint, tags, now, now),
        )
        conn.commit()
        status = "registered"

    row = conn.execute(
        "SELECT * FROM agents WHERE agent_id = ?", (req.agent_id,)
    ).fetchone()
    return {"ok": True, "status": status, "agent": _row_to_public(row)}


@app.post("/api/v1/discover")
def discover(req: DiscoverRequest, conn: sqlite3.Connection = Depends(db_dep)) -> dict:
    """
    Machine search. Tokenizes the query and scores each agent by how many of
    its capability tags match, then ranks by (match_score, success_rate,
    total_transactions). Falls back to substring matching on name/tags so
    natural-language queries still resolve.
    """
    query_tokens = [t for t in _TAG_SPLIT.split(req.query.lower()) if t]
    rows = conn.execute("SELECT * FROM agents").fetchall()

    scored: list[tuple[int, float, int, dict]] = []
    for row in rows:
        pub = _row_to_public(row)
        if req.online_only and not pub["online"]:
            continue
        tags = set(pub["capabilities_tags"])
        haystack = (row["name"] + " " + row["capabilities_tags"]).lower()

        score = 0
        for tok in query_tokens:
            if tok in tags:
                score += 2          # exact tag hit
            elif tok in haystack:
                score += 1          # substring hit on name/tags
        if score > 0:
            scored.append((score, pub["success_rate"], pub["total_transactions"], pub))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    results = [item[3] for item in scored[: req.limit]]
    return {"ok": True, "count": len(results), "query": req.query, "results": results}


@app.post("/api/v1/telemetry")
def telemetry(req: TelemetryRequest, conn: sqlite3.Connection = Depends(db_dep)) -> dict:
    """
    Mandatory heartbeat + job monitor. Atomically increments transaction
    counters and recomputes success_rate = successful / total. Also refreshes
    last_seen so telemetry doubles as a liveness ping.
    """
    now = _utcnow().isoformat()
    is_success = 1 if req.job_status == "success" else 0

    # Single atomic UPDATE keeps counters consistent under concurrency.
    cur = conn.execute(
        """
        UPDATE agents
           SET total_transactions = total_transactions + 1,
               successful_transactions = successful_transactions + ?,
               success_rate = CAST(successful_transactions + ? AS REAL)
                              / (total_transactions + 1),
               last_seen = ?
         WHERE agent_id = ?
        """,
        (is_success, is_success, now, req.agent_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="agent_id not registered")
    conn.commit()

    row = conn.execute(
        "SELECT * FROM agents WHERE agent_id = ?", (req.agent_id,)
    ).fetchone()
    return {"ok": True, "recorded": req.job_status, "agent": _row_to_public(row)}


@app.get("/api/v1/agents")
def list_agents(
    limit: int = 100,
    online_only: bool = False,
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict:
    limit = max(1, min(limit, 500))
    rows = conn.execute(
        "SELECT * FROM agents ORDER BY success_rate DESC, total_transactions DESC LIMIT ?",
        (limit,),
    ).fetchall()
    agents = [_row_to_public(r) for r in rows]
    if online_only:
        agents = [a for a in agents if a["online"]]
    return {"ok": True, "count": len(agents), "agents": agents}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        workers=int(os.environ.get("WEB_CONCURRENCY", "1")),
    )
