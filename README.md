<div align="center">

# 🔦 Beacon — The Search Engine for AI Agents

**Search, discover & verify 3,800+ open-source AI agents by capability — ranked by real GitHub traction.**

[**🌐 Live Portal**](https://portal-five-phi-54.vercel.app) · [**📦 npm**](https://www.npmjs.com/package/beacon-mcp) · [**🔌 MCP**](#-use-it-inside-your-editor-mcp) · [**🧠 llms.txt**](https://registry-ruby.vercel.app/llms.txt)

[![npm](https://img.shields.io/npm/v/beacon-mcp?color=6366f1&label=beacon-mcp)](https://www.npmjs.com/package/beacon-mcp)
![license](https://img.shields.io/badge/license-MIT-6366f1)
![agents indexed](https://img.shields.io/badge/agents%20indexed-3800%2B-10b981)

</div>

---

Google indexes websites so humans can find them. **Beacon indexes agents so agents (and their builders) can find each other.**

Finding a reliable open-source AI agent to reuse is a manual chore — search GitHub, cross-check stars, guess whether it's still maintained. Beacon fixes that: it crawls GitHub for agent repos across **ElizaOS, CrewAI, AutoGen, LangGraph, LangChain, and MCP servers**, normalizes their capabilities into searchable tags, and ranks them by real traction (stars + activity). Free, no API key.

## 🔍 Try it now

**[portal-five-phi-54.vercel.app](https://portal-five-phi-54.vercel.app)** — search by what an agent *does*: `pdf extraction`, `web scraping`, `browser automation`, `trading bot`…

## 🔌 Use it inside your editor (MCP)

Give Claude / Cursor / Cline / Windsurf a `find_agent` tool — one line, no key:

```json
{
  "mcpServers": {
    "beacon": { "command": "npx", "args": ["-y", "beacon-mcp"] }
  }
}
```

Then ask your assistant: *"Use beacon to find an agent that scrapes websites."*

Tools: `find_agent` (search by capability), `top_agents` (ranked by stars), `agent_details` (trust snapshot).

## 🐍 Register your agent (SDK)

```bash
pip install beacon-agent
```
```python
import beacon_agent; beacon_agent.enable()   # auto-registers CrewAI/LangChain/AutoGen agents
```

Registered agents get a live README badge that updates with their reputation:

```markdown
![Beacon Verified](https://registry-ruby.vercel.app/api/v1/agents/{owner}/{repo}/badge.svg)
```

## 🧩 What's inside

| Component | What it is |
|---|---|
| [`registry/`](registry) | FastAPI + Turso (libSQL) registry — discovery, reputation, fraud engine, badges |
| [`mcp/beacon-mcp/`](mcp/beacon-mcp) | The MCP server (`npx -y beacon-mcp`) |
| [`sdk/beacon-agent/`](sdk/beacon-agent) | `pip install` auto-register SDK (CrewAI/LangChain/AutoGen) |
| [`registry/beacon_langchain_plugin.py`](registry/beacon_langchain_plugin.py) | Native LangChain tool |
| [`registry/plugin_auto_loader.ts`](registry/plugin_auto_loader.ts) | ElizaOS auto-loader |
| [`portal/`](portal) | The search portal (single-file, Tailwind) |

## 🔗 API

`https://registry-ruby.vercel.app`

- `POST /api/v1/discover` — search by capability
- `GET /api/v1/leaderboard` — ranked by reputation + stars
- `GET /api/v1/agents?sort=recent` — newest indexed
- `GET /api/v1/agents/{owner}/{repo}/badge.svg` — live status badge
- `GET /llms.txt` — LLM discovery doc

## License

MIT
