"""
Local SQLite database backend — drop-in replacement for the remote Turso HTTP client.

Public API is identical (execute, ensure_schema, TursoError) so main.py and
enrich_github.py require no interface changes.  Uses Python's built-in sqlite3
module with WAL journaling and a per-thread connection cache for safe high-
concurrency use under uvicorn workers.

Configure via .env / shell:
  SQLITE_DB_PATH   Absolute path to the SQLite file on disk.
                   Default: /home/gcp_user/beacon_prod.db
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("SQLITE_DB_PATH", "/home/gcp_user/beacon_prod.db")

# Hard block: refuse any legacy Turso/libSQL remote credentials.
_FORBIDDEN_REMOTE = (
    "TURSO_DATABASE_URL",
    "TURSO_DB_URL",
    "TURSO_URL",
    "TURSO_AUTH_TOKEN",
    "TURSO_TOKEN",
    "LIBSQL_URL",
)
for _key in _FORBIDDEN_REMOTE:
    if os.environ.get(_key):
        raise RuntimeError(
            f"{_key} is set but Beacon no longer uses remote Turso/libSQL. "
            f"Unset it and use SQLITE_DB_PATH={DB_PATH} on the GCP VM only."
        )

_backend_logged = False

# One connection per OS thread; avoids the overhead of opening a new connection
# on every execute() call while remaining safe across uvicorn's thread pool.
_local = threading.local()


# ---------------------------------------------------------------------------
# Public exception (name kept for compatibility with main.py handler)
# ---------------------------------------------------------------------------

class TursoError(RuntimeError):
    """Storage error raised by execute().  Name kept for main.py compatibility."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return the per-thread SQLite connection, creating it on first access."""
    global _backend_logged
    conn: Optional[sqlite3.Connection] = getattr(_local, "conn", None)
    if conn is None:
        if not os.path.isfile(DB_PATH) and DB_PATH != ":memory:":
            import logging
            logging.getLogger("beacon.sqlite").warning(
                "SQLite file not found at %s — will be created on first write", DB_PATH
            )
        conn = sqlite3.connect(
            DB_PATH,
            check_same_thread=False,
            timeout=30,
            # autocommit: every statement is its own implicit transaction,
            # matching the one-shot behaviour of the old Turso HTTP client.
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row

        # High-concurrency PRAGMA optimizations:
        #   WAL  — concurrent readers never block the writer (and vice-versa).
        #   synchronous=NORMAL — crash-safe (survives OS crash) and ~3× faster
        #                        than FULL; data is never lost on power failure
        #                        because WAL frames are fsynced before commit.
        #   busy_timeout — writer threads queue instead of raising immediately
        #                  when another write holds the lock.
        #   cache_size   — 64 MB page cache per connection, reduces disk I/O.
        #   temp_store   — keep temp tables / sort buffers in RAM.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")

        _local.conn = conn
        if not _backend_logged:
            import logging
            logging.getLogger("beacon.sqlite").info(
                "Storage backend: local SQLite (WAL) — %s", DB_PATH
            )
            _backend_logged = True
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute(sql: str, args: Optional[Iterable[Any]] = None) -> list[dict]:
    """
    Run one SQL statement.  Returns a list of row dicts (empty for writes).
    Raises TursoError on any database error.
    """
    try:
        conn = _get_conn()
        cur = conn.execute(sql, list(args) if args is not None else [])
        if cur.description is None:
            # INSERT / UPDATE / DELETE / DDL — no rows to return.
            return []
        return [dict(row) for row in cur.fetchall()]
    except sqlite3.OperationalError as exc:
        raise TursoError(str(exc)) from exc
    except sqlite3.DatabaseError as exc:
        raise TursoError(str(exc)) from exc


def ensure_schema() -> None:
    """Idempotent DDL.  Cheap enough to call on every cold start."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            agent_id                TEXT PRIMARY KEY,
            name                    TEXT NOT NULL,
            mcp_endpoint            TEXT NOT NULL,
            capabilities_tags       TEXT NOT NULL DEFAULT '',
            success_rate            REAL NOT NULL DEFAULT 1.0,
            total_transactions      INTEGER NOT NULL DEFAULT 0,
            successful_transactions INTEGER NOT NULL DEFAULT 0,
            created_at              TEXT NOT NULL,
            last_seen               TEXT NOT NULL
        )
        """
    )
    execute("CREATE INDEX IF NOT EXISTS idx_agents_success  ON agents(success_rate DESC)")
    execute("CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen DESC)")

    # Additive columns added in subsequent deploys.  ALTER TABLE is not
    # idempotent in SQLite, so each is wrapped in try/except.
    for ddl in (
        "ALTER TABLE agents ADD COLUMN reachable INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE agents ADD COLUMN last_validated TEXT",
        "ALTER TABLE agents ADD COLUMN registration_source TEXT NOT NULL DEFAULT 'sdk'",
        "ALTER TABLE agents ADD COLUMN fraud_strikes INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE agents ADD COLUMN is_fraudulent INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE agents ADD COLUMN fraud_reason TEXT",
        # Real GitHub traction signals — kept separate from agent-telemetry columns.
        "ALTER TABLE agents ADD COLUMN stars INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE agents ADD COLUMN pushed_at TEXT",
        "ALTER TABLE agents ADD COLUMN open_issues INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            execute(ddl)
        except TursoError:
            pass  # column already exists — safe to ignore

    execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
    execute("CREATE INDEX IF NOT EXISTS idx_agents_stars ON agents(stars DESC)")
    execute("CREATE INDEX IF NOT EXISTS idx_agents_created ON agents(created_at DESC)")
    execute(
        "CREATE INDEX IF NOT EXISTS idx_agents_fraud_success "
        "ON agents(is_fraudulent, success_rate DESC, stars DESC)"
    )

    _ensure_fts()


def _trigger_exists(name: str) -> bool:
    rows = execute("SELECT 1 AS x FROM sqlite_master WHERE type='trigger' AND name=?", [name])
    return bool(rows)


def _ensure_fts() -> None:
    """
    FTS5 external-content index on agents — sub-20ms full-text search at 17k+ rows.
  Triggers keep the index in sync; one-time rebuild populates existing rows.
    """
    execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS agents_fts USING fts5(
            name,
            mcp_endpoint,
            capabilities_tags,
            agent_id UNINDEXED,
            content='agents',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )

    if not _trigger_exists("agents_fts_ai"):
        execute(
            """
            CREATE TRIGGER agents_fts_ai AFTER INSERT ON agents BEGIN
                INSERT INTO agents_fts(rowid, name, mcp_endpoint, capabilities_tags, agent_id)
                VALUES (new.rowid, new.name, new.mcp_endpoint, new.capabilities_tags, new.agent_id);
            END
            """
        )
    if not _trigger_exists("agents_fts_ad"):
        execute(
            """
            CREATE TRIGGER agents_fts_ad AFTER DELETE ON agents BEGIN
                INSERT INTO agents_fts(agents_fts, rowid, name, mcp_endpoint, capabilities_tags, agent_id)
                VALUES ('delete', old.rowid, old.name, old.mcp_endpoint, old.capabilities_tags, old.agent_id);
            END
            """
        )
    if not _trigger_exists("agents_fts_au"):
        execute(
            """
            CREATE TRIGGER agents_fts_au AFTER UPDATE ON agents BEGIN
                INSERT INTO agents_fts(agents_fts, rowid, name, mcp_endpoint, capabilities_tags, agent_id)
                VALUES ('delete', old.rowid, old.name, old.mcp_endpoint, old.capabilities_tags, old.agent_id);
                INSERT INTO agents_fts(rowid, name, mcp_endpoint, capabilities_tags, agent_id)
                VALUES (new.rowid, new.name, new.mcp_endpoint, new.capabilities_tags, new.agent_id);
            END
            """
        )

    # Populate / rebuild FTS from agents when empty or out of sync.
    try:
        agent_n = execute("SELECT COUNT(*) AS c FROM agents")[0]["c"]
        fts_n = execute("SELECT COUNT(*) AS c FROM agents_fts")[0]["c"]
        if agent_n and fts_n < max(1, agent_n // 2):
            execute("INSERT INTO agents_fts(agents_fts) VALUES('rebuild')")
    except TursoError:
        pass
