# Directory submissions — hosted MCP ready

## Live URLs (after deploy)

| Asset | URL |
|-------|-----|
| **Remote MCP** | `https://beacon-mcp-taupe.vercel.app/mcp` |
| Health | `https://beacon-mcp-taupe.vercel.app/health` |
| Server card | `https://beacon-mcp-taupe.vercel.app/.well-known/mcp/server-card.json` |
| npm stdio | `npx beacon-mcp init` |
| Registry | `https://registry-ruby.vercel.app` |

---

## 1. Smithery (https://smithery.ai/new)

**Type:** Remote URL (Streamable HTTP)  
**URL:** `https://beacon-mcp.vercel.app/mcp`  
**Name:** `@enrichgateagent-png/beacon-mcp` or `enrichgateagent-png/beacon-mcp`

CLI (after `smithery auth login` + API key):
```bash
smithery mcp publish "https://beacon-mcp-taupe.vercel.app/mcp" -n enrichgateagent-png/beacon-mcp
```

---

## 2. Glama (https://glama.ai/mcp/servers)

**Add MCP Server** → GitHub: `https://github.com/enrichgateagent-png/x402-agents`  
**Or Remote connector:** `https://beacon-mcp-taupe.vercel.app/mcp`  
`glama.json` is in repo root.

---

## 3. Official MCP Registry

```bash
cd mcp/beacon-mcp
mcp-publisher login github   # device code in browser
mcp-publisher publish
```

Requires `server.json` + npm `mcpName` (already set).

---

## 4. PulseMCP

Email **hello@pulsemcp.com** with remote URL `https://beacon-mcp-taupe.vercel.app/mcp`
