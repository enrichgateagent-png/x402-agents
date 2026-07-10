"""
agent_app.py — how a developer wires Beacon into a real agent.

This is the entire integration surface: import BeaconClient, construct it once,
and decorate the agent's unit of work. Discovery and reputation happen for free.

Run it against a local server:
    REGISTRY_URL=http://127.0.0.1:8000 python agent_app.py
Or against production (default):
    python agent_app.py
"""

from __future__ import annotations

import os
import random
import time

from beacon_sdk import BeaconClient

REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://beacon-registry.onrender.com")

# 1) Construct the client once. Auto-registration fires immediately on a
#    background thread — the agent is now discoverable without another line.
beacon = BeaconClient(
    agent_id="research-bot-001",
    name="Deep Research Bot",
    mcp_endpoint="https://my-research-bot.example.com/mcp",
    capabilities=["research", "web-search", "summarization", "reports"],
    registry_url=REGISTRY_URL,
)


# 2) Decorate any unit of work. Success/failure telemetry is reported
#    automatically; exceptions still propagate exactly as before.
@beacon.track_job
def run_research_task(topic: str) -> dict:
    """Pretend to do real agent work (call tools, an LLM, etc.)."""
    time.sleep(0.2)
    if random.random() < 0.2:
        raise RuntimeError(f"tool timeout while researching '{topic}'")
    return {"topic": topic, "findings": f"3 sources summarized for {topic}"}


def main() -> None:
    # Make sure the initial handshake landed before we start (optional).
    if beacon.wait_until_registered(timeout=10):
        print("[agent] beacon lit — agent is discoverable")
    else:
        print("[agent] registry unreachable; agent runs normally, telemetry self-heals")

    # 3) Do work. The decorator handles telemetry transparently.
    topics = ["x402 adoption", "agent payment rails", "MCP servers", "stablecoin flows"]
    for topic in topics:
        try:
            result = run_research_task(topic)
            print(f"[agent] OK  -> {result['findings']}")
        except Exception as exc:  # noqa: BLE001 — demo: keep the loop alive
            print(f"[agent] FAIL -> {exc}")

    # 4) Agents can also discover *other* agents to delegate to.
    print("\n[agent] discovering peers that can 'summarize research'...")
    peers = beacon.discover("summarize research reports", limit=5)
    for p in peers:
        print(f"   - {p['name']} (success_rate={p['success_rate']}, online={p['online']})")

    # Alternative manual style (context manager) if you don't want the decorator:
    with beacon.job():
        time.sleep(0.05)  # some risky step; success reported on clean exit

    beacon.close()


if __name__ == "__main__":
    main()
