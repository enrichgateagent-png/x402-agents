# beacon-mcp

**The search engine for AI agents — inside your agent.**

Beacon indexes thousands of open-source AI agents from GitHub, ranked by real
traction (stars, activity), searchable by capability. This MCP server puts that
index inside Claude Desktop, Cursor, Cline, Windsurf, or any MCP client — so you
can ask "find me an agent that does X" and get real, linkable results.

No API key. No payment. Just discovery.

## Tools

| Tool | What it does |
|---|---|
| `find_agent` | Search agents by capability/task ("pdf extraction", "crypto trading", …) |
| `top_agents` | Most-starred / highest-reputation agents in the index |
| `agent_details` | Full detail for one agent by id (e.g. `elizaOS/eliza`) |

## Install

**Claude Desktop / Cline / Windsurf** — add to your MCP config:

```json
{
  "mcpServers": {
    "beacon": { "command": "npx", "args": ["-y", "beacon-mcp"] }
  }
}
```

**Cursor** — Settings → MCP → add a stdio server: `npx -y beacon-mcp`.

That's it. Ask your agent: *"Use beacon to find an agent that scrapes websites."*

## Config

- `BEACON_REGISTRY_URL` — override the registry base (default `https://registry-ruby.vercel.app`).

## Links

- Live portal: https://portal-five-phi-54.vercel.app
- Registry API: https://registry-ruby.vercel.app

MIT
