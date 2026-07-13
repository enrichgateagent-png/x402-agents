# Directory submissions — copy-paste ready

Submit Beacon MCP + registry to these directories. All fields verified against live URLs.

## Live URLs

| Asset | URL |
|-------|-----|
| Portal | https://portal-five-phi-54.vercel.app |
| Registry API | https://registry-ruby.vercel.app |
| llms.txt | https://registry-ruby.vercel.app/llms.txt |
| MCP install | `BEACON_REGISTRY_URL=https://registry-ruby.vercel.app npx -y beacon-mcp` |
| Manifest spec | https://github.com/enrichgateagent-png/beacon-agent-manifest |
| npm | https://www.npmjs.com/package/beacon-mcp |

---

## 1. Glama (https://glama.ai/mcp/servers)

**Name:** Beacon MCP  
**Description:** Search engine for open-source AI agents. Find 33,000+ MCP servers and agents by capability inside Claude, Cursor, Cline, and Windsurf. No API key.  
**Install:** `npx -y beacon-mcp`  
**Repository:** https://github.com/enrichgateagent-png/x402-agents/tree/master/mcp/beacon-mcp  
**Registry:** https://registry-ruby.vercel.app  
**Tags:** agent-discovery, search, mcp, registry, langchain, crewai

---

## 2. PulseMCP (https://www.pulsemcp.com/submit)

**Server name:** beacon-mcp  
**One-liner:** Capability search over 33k+ open-source AI agents and MCP servers.  
**stdio command:** `npx -y beacon-mcp`  
**Env:** `BEACON_REGISTRY_URL=https://registry-ruby.vercel.app`  
**Tools:** find_agent, top_agents, agent_details  
**Docs:** https://github.com/enrichgateagent-png/x402-agents/blob/master/mcp/beacon-mcp/README.md

---

## 3. Smithery (https://smithery.ai)

**Package:** beacon-mcp  
**Type:** stdio MCP  
**Command:** npx  
**Args:** `-y`, `beacon-mcp`  
**Description:** The search engine for AI agents — discover open-source agents by capability from inside any MCP client.

---

## 4. Awesome MCP (PR to punkpeye/awesome-mcp-servers)

Add under **Search & Discovery**:

```markdown
- [Beacon](https://portal-five-phi-54.vercel.app) - Search 33k+ open-source AI agents by capability. MCP server for Claude/Cursor. `npx -y beacon-mcp`
```

---

## 5. Hacker News (post when first outreach PR merges)

**Title:** Show HN: Beacon – searchable index of 33k open-source AI agents (MCP + llms.txt)

**Body:** We index GitHub agents/MCP servers by capability. Search at portal-five-phi-54.vercel.app. Agents discover via llms.txt. MCP: npx -y beacon-mcp. Open manifest standard for self-verification (beacon.json). Would love feedback on what's missing from the index.

---

## 6. Google Search Console

1. Property: https://portal-five-phi-54.vercel.app  
2. Sitemaps → submit: `sitemap.xml?v=3`  
3. URL inspection → request indexing for `/` and `/discover/mcp-server`

---

## 7. Reddit (r/MCP, r/LocalLLaMA — after first external manifest merge)

**Title:** Open registry indexing 33k AI agents + MCP server for Cursor/Claude

Keep it short, link portal + llms.txt, no spammy cross-posts same day.
