# beacon-mcp — Directory Submission Kit

Accurate as of the live package (`npx -y beacon-mcp`) and registry
(https://registry-ruby.vercel.app). Tool behavior below matches what the code
actually returns — no license/language claims (we don't expose those).

Verified fields per agent: `agent_id, name, mcp_endpoint, capabilities_tags,
stars, pushed_at, active, open_issues, success_rate, fraud_status`.

---

## SECTION 1 — Smithery.ai

**App Name:** beacon-mcp

**Short Description (≤80 chars):**
Search & discover 3,800+ open-source AI agents from inside your LLM.

**Detailed Description (Markdown):**

Beacon MCP turns your coding assistant into a live search layer over the
open-source AI agent ecosystem. Instead of tab-switching to GitHub and
awesome-lists, Claude, Cursor, Cline, and Windsurf can query a searchable index
of 3,800+ agents mid-conversation via three tools:

- **`find_agent`** — Search the index by capability, framework, or use case
  (e.g. "browser automation" or "crewai research"). Returns matching repos with
  their capability tags, GitHub star count, maintenance status, and repo link.
- **`top_agents`** — The highest-signal agents, ranked by reputation and GitHub
  stars, so you can surface popular, well-starred options in a category fast.
- **`agent_details`** — A trust snapshot for one agent: stars, last-push
  activity (active vs dormant), open issues, capability tags, a reputation
  score, fraud status, and a live README badge.

Data is fetched live from the Beacon registry (crawled from GitHub and refreshed
continuously), so results reflect current stars and activity rather than a stale
hand-maintained list. No API key, no paid tier. Aimed at developers building on
ElizaOS, CrewAI, AutoGen, LangGraph, and MCP who want to evaluate or reuse
existing components.

**Config JSON (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "beacon-mcp": { "command": "npx", "args": ["-y", "beacon-mcp"] }
  }
}
```

---

## SECTION 2 — Glama.ai

**Title:** Beacon MCP — AI Agent Search & Directory

**Tagline:**
Search and vet 3,800+ open-source AI agents, ElizaOS plugins, and CrewAI tools
without leaving your workspace.

**Long Text:**

Finding a reliable open-source agent to reuse is normally a manual chore:
search GitHub, cross-check stars, guess whether a repo is still maintained.
Beacon MCP removes that friction by exposing a searchable index of the agent
ecosystem through the Model Context Protocol.

No API keys, no paid tier — install it, point your MCP client at it, and query.
Results are backed by GitHub repository data (star counts and last-push
activity) pulled into the Beacon registry, so you can do fast due diligence:
confirm a framework is active, compare alternatives, and pull a repo's details
without leaving your editor. Beacon also validates endpoint reachability and
flags fraudulent nodes, so low-quality or malicious entries are filtered out of
discovery.

**Categories/Tags:** Development, AI Agents, Search, Developer Tools, Utilities

**Install:** `npx -y beacon-mcp`

---

## SECTION 3 — mcp.so

**Project Name:** Beacon — AI Agent Search Engine

**One-liner:**
Search 3,800+ open-source AI agents by capability, ranked by real GitHub
traction — from inside Claude / Cursor / Cline / Windsurf.

**Description:**

Beacon indexes open-source AI agents from GitHub (ElizaOS, CrewAI, AutoGen,
LangGraph, LangChain, MCP servers), normalizes their capabilities into
searchable tags, and ranks them by stars and activity. This MCP server exposes
that index with three tools — `find_agent`, `top_agents`, `agent_details` — so
your assistant can find and vet agents mid-task. Free, keyless.

**Install:** `npx -y beacon-mcp`

**Links:**
- Portal: https://portal-five-phi-54.vercel.app
- Registry API: https://registry-ruby.vercel.app
- Repo: https://github.com/enrichgateagent-png/x402-agents
- npm: https://www.npmjs.com/package/beacon-mcp

---

## Corrections I made vs. the original draft (so you know why)
- **Removed "license" and "primary language"** from `agent_details` — we don't
  store or return those fields. Replaced with what it actually returns (stars,
  last-push activity, open issues, tags, reputation, fraud status, badge).
- **`find_agent`**: changed "returns descriptions" → returns capability tags +
  stars + status + link (we derive tags from descriptions; we don't return raw
  descriptions).
- **`top_agents`**: ranking is reputation + stars (activity is shown per result,
  not the primary sort key) — softened "ranked by recent commit activity."
- **Count**: 3,809 live → "3,800+" (only grows, so safe).
- Dropped "100% genuine" absolute phrasing; enrichment (stars/pushed_at) is
  ongoing across the index, so not every single row is enriched yet.
