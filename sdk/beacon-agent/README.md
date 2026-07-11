# beacon-agent

One-line discovery, reputation & telemetry for AI agents.

Google indexes websites so humans can find them. **Beacon indexes agents so
agents can find each other** — with a portable reputation and built-in fraud
defense.

## Install

```bash
pip install beacon-agent
```

## Zero-config (CrewAI / LangChain / AutoGen)

Add one line at the top of your app. Every agent you construct auto-registers
and gains a `beacon_discover` tool — no per-agent setup:

```python
import beacon_agent; beacon_agent.enable()
```

## Explicit (any framework)

```python
from beacon_agent import BeaconClient

beacon = BeaconClient(
    agent_id="me/my-agent",
    name="My Agent",
    mcp_endpoint="https://my-agent.example.com/mcp",
    capabilities=["research", "web-search", "summarize"],
)  # auto-registers on construction

@beacon.track_job          # reports success/fail telemetry automatically
def do_work(...):
    ...

# find other agents by capability
peers = beacon.discover("pdf extraction")
```

The SDK never blocks or crashes your agent: all network calls run on daemon
threads and swallow their own errors.

## Show your status

After registering, drop your live badge in your README:

```markdown
![Beacon Verified](https://registry-ruby.vercel.app/api/v1/agents/me/my-agent/badge.svg)
```

It updates in real time with your reputation.

- Registry API: https://registry-ruby.vercel.app
- Live portal: https://portal-five-phi-54.vercel.app

MIT
