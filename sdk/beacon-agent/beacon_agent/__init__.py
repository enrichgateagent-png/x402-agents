"""
beacon-agent — one-line discovery, reputation & telemetry for AI agents.

Zero-config (auto-hooks CrewAI / LangChain / AutoGen):

    import beacon_agent; beacon_agent.enable()

Explicit (any framework or a bare loop):

    from beacon_agent import BeaconClient
    beacon = BeaconClient(
        agent_id="me/my-agent",
        name="My Agent",
        mcp_endpoint="https://my-agent.example.com/mcp",
        capabilities=["research", "web-search"],
    )

    @beacon.track_job
    def do_work(...): ...
"""

from .auto_inject import enable_beacon_auto_discovery
from .client import BeaconClient

# Friendly one-liner alias.
enable = enable_beacon_auto_discovery

__all__ = ["enable", "enable_beacon_auto_discovery", "BeaconClient"]
__version__ = "0.1.0"
