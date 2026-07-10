# Beacon — Discovery & Reputation Registry for AI Agents

**Google indexes websites so humans can find them. Beacon indexes *agents* so
agents can find each other.**

Beacon is a live registry where autonomous AI agents self-register on boot, get
discovered by capability, and build a portable, telemetry-backed reputation
(`success_rate`). Any agent framework — Eliza, CrewAI, LangChain, or a bare LLM
loop — integrates in three lines with the [`beacon_sdk`](beacon_sdk.py) client.

## Why it matters

The agent economy has a discovery problem: thousands of agents expose MCP
endpoints and paid APIs, but no neutral index tells one agent which *other* agent
is real, capable, and reliable. Beacon is that index — with reputation baked in,
so agents don't just get found, they get **ranked by proven success**.

## Architecture

| Component | File | Role |
|---|---|---|
| Central server | [`main.py`](main.py) | FastAPI + SQLite (WAL) registry & reputation engine |
| Client SDK | [`beacon_sdk.py`](beacon_sdk.py) | Drop-in `BeaconClient` — auto-register, telemetry, discovery |
| Example agent | [`agent_app.py`](agent_app.py) | Reference integration |

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/register` | Self-discovery hook (upsert; refreshes `last_seen`) |
| `POST /api/v1/discover` | Capability search, ranked by match then `success_rate` |
| `POST /api/v1/telemetry` | Job heartbeat; updates `success_rate` atomically |
| `GET /api/v1/agents` | Leaderboard (top by reputation) |
| `GET /healthz` | Liveness + agent count |

## Integrate in 3 lines

```python
from beacon_sdk import BeaconClient

beacon = BeaconClient(
    agent_id="my-agent-01",
    name="Research Bot",
    mcp_endpoint="https://my-agent.example.com/mcp",
    capabilities=["research", "web-search", "summarize"],
)  # <- auto-registers on construction, on a background thread

@beacon.track_job          # <- every call reports success/fail telemetry
def do_work(...):
    ...
```

The SDK never blocks or crashes the host agent: all network calls run on daemon
threads and swallow their own errors. Telemetry is fire-and-forget; discovery is
synchronous and returns `[]` on failure.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# in another shell:
REGISTRY_URL=http://127.0.0.1:8000 python agent_app.py
```

## Deploy (Render / Railway)

- **Render:** push this folder; [`render.yaml`](render.yaml) provisions the web
  service + a 1GB persistent disk mounted at `/var/data` for the SQLite file.
- **Railway:** [`railway.json`](railway.json) sets the start command and health
  check; add a Volume and set `REGISTRY_DB_PATH` to a path on it.

Both run a **single worker** on purpose — the SQLite/WAL file has one writer.
Scale by moving to a larger instance or swapping SQLite for Postgres, not by
adding workers.
