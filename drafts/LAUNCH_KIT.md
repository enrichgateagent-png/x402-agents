# Beacon — Launch & Publishing Kit

Everything below is copy-paste ready. Numbers are accurate as of writing
(3,800+ agents, growing). Before posting, glance at
https://registry-ruby.vercel.app/llms.txt for the current count — if it's well
past 4,000, bump "3,800+" to "4,000+".

## Canonical facts & links (use these exactly)
- **What it is:** Beacon — a search engine / directory for open-source AI agents.
- **Agents indexed:** 3,800+ (live, from GitHub)
- **Portal (main link):** https://portal-five-phi-54.vercel.app
- **MCP install (one line):** `npx -y beacon-mcp`
- **npm:** https://www.npmjs.com/package/beacon-mcp
- **Registry API:** https://registry-ruby.vercel.app
- **LLM discovery doc:** https://registry-ruby.vercel.app/llms.txt
- **GitHub:** https://github.com/enrichgateagent-png/x402-agents
- **X handle:** @Enrichagent
- **Frameworks covered:** ElizaOS, CrewAI, AutoGen, LangGraph, LangChain, MCP servers
- **Tagline:** "Search, discover & verify open-source AI agents."
- **One-liner:** Search 3,800+ open-source AI agents by capability, ranked by real
  GitHub traction — from your browser or inside your editor via MCP.

⚠️ Accuracy guardrails (do NOT overclaim — these have been checked):
- Do say: search by capability; ranked by stars + activity; free/keyless; MCP + SDK.
- Do NOT say: "license/primary language lookup" (not supported), "real-time GitHub"
  (index refreshes periodically), or a fixed exact count (it changes — use "3,800+").

---

## 1) Show HN (news.ycombinator.com — post Tue–Thu ~8–10am ET)

**Title:**
`Show HN: Beacon – a search engine for open-source AI agents (3,800+ indexed)`

**Body:**
```
I kept losing track of which open-source AI agents exist and which are actually
maintained, so I built Beacon: a searchable index of AI agents.

It crawls GitHub for agent repos (CrewAI, LangChain, LangGraph, ElizaOS, AutoGen,
MCP servers), normalizes their capabilities into tags, and lets you search by what
you actually want — "pdf extraction", "web scraping", "browser automation" —
ranked by GitHub stars and whether the repo is still active. ~3,800 indexed.

Two things I cared about:
- It's useful at zero adoption — it's a directory of repos that already exist,
  not a walled garden waiting for signups.
- There's an MCP server (`npx -y beacon-mcp`), so you can search the index from
  inside Claude/Cursor/Cline while you build.

Stack: FastAPI + Turso (libSQL) on Vercel; a GitHub Actions crawler; a semantic
fallback so vague queries still return something; endpoint reachability checks;
and a lightweight reputation/fraud layer with a live SVG badge for READMEs.

Honest status: the crawler-sourced index is real and useful now; the
self-registration/reputation side is early. Would love feedback on whether the
directory is actually useful and what agents you'd expect to find that are missing.

Portal: https://portal-five-phi-54.vercel.app
```
Tips: reply to every comment in the first 2 hours; the honest framing plays well on HN.

---

## 2) Reddit

**Subreddits:** r/LocalLLaMA, r/AI_Agents, r/LLMDevs, r/ArtificialInteligence

**Title:**
`I built a searchable directory of 3,800+ open-source AI agents (with an MCP server)`

**Body:**
```
Finding good open-source agents is a mess — they're scattered across GitHub with
inconsistent naming. So I made Beacon: search agents by capability, see real stars
+ whether they're still maintained, and pull it up from inside your editor via MCP
(`npx -y beacon-mcp`).

It indexes CrewAI / LangChain / LangGraph / ElizaOS / AutoGen / MCP-server repos
(~3,800 so far). Free, no signup to search.

Portal: https://portal-five-phi-54.vercel.app

Curious what agents you'd expect to find that are missing — I'll add sources.
```
Tips: lead with utility, end with a question, no hard CTA. Subs dislike promo.

---

## 3) X / Twitter thread (post from @Enrichagent)

```
1/ Introducing Beacon — the search engine for AI agents.

Google indexes websites so humans can find them. Beacon indexes agents so builders
can find each other.

3,800+ open-source AI agents indexed and searchable by capability. 🧵
```
```
2/ Search "pdf extraction", "web scraping", "browser automation" — get real repos
ranked by GitHub stars and whether they're still maintained.

Not a walled garden. Useful today, no signup to search.
```
```
3/ Building an agent? `npx -y beacon-mcp` drops the whole index inside
Claude / Cursor / Cline / Windsurf.

Ask your agent to find another agent. There's a LangChain tool + a one-line
auto-register SDK too.
```
```
4/ Browse it live 👇
https://portal-five-phi-54.vercel.app
```

---

## 4) LinkedIn / longer post

```
Finding a reliable open-source AI agent to reuse is a manual chore — search GitHub,
cross-check stars, guess if it's still maintained.

So I built Beacon: a search engine for open-source AI agents. It indexes 3,800+
repos across CrewAI, LangChain, LangGraph, ElizaOS, AutoGen and MCP servers, lets
you search by capability, and ranks by real GitHub traction and activity.

It also works inside your editor — `npx -y beacon-mcp` gives Claude/Cursor a
find_agent tool, so your assistant can discover and vet agents mid-task.

Free, no API key. Try it: https://portal-five-phi-54.vercel.app
```

---

## 5) MCP directory submissions

### Smithery.ai
- **App Name:** beacon-mcp
- **Short (≤80):** Search & discover 3,800+ open-source AI agents from inside your LLM.
- **Config:**
```json
{ "mcpServers": { "beacon-mcp": { "command": "npx", "args": ["-y", "beacon-mcp"] } } }
```
- **Description:**
```
Beacon MCP turns your coding assistant into a live search layer over the open-source
AI agent ecosystem. Instead of tab-switching to GitHub and awesome-lists, Claude,
Cursor, Cline, and Windsurf can query a searchable index of 3,800+ agents via three
tools:

- find_agent — search by capability, framework, or use case; returns matching repos
  with capability tags, GitHub stars, maintenance status, and repo link.
- top_agents — highest-signal agents, ranked by reputation and GitHub stars.
- agent_details — a trust snapshot: stars, last-push activity, open issues,
  capability tags, reputation score, fraud status, and a live README badge.

Data is fetched live from the Beacon registry (crawled from GitHub, refreshed
continuously). No API key, no paid tier. For developers building on ElizaOS,
CrewAI, AutoGen, LangGraph, and MCP.
```

### Glama.ai
- **Title:** Beacon MCP — AI Agent Search & Directory
- **Tagline:** Search and vet 3,800+ open-source AI agents, ElizaOS plugins, and CrewAI tools without leaving your workspace.
- **Categories:** Development, AI Agents, Search, Developer Tools, Utilities
- **Install:** `npx -y beacon-mcp`
- **Long text:**
```
Finding a reliable open-source agent to reuse is normally a manual chore: search
GitHub, cross-check stars, guess whether a repo is still maintained. Beacon MCP
removes that friction by exposing a searchable index of the agent ecosystem through
the Model Context Protocol.

No API keys, no paid tier — install it, point your MCP client at it, and query.
Results are backed by GitHub repository data (star counts and last-push activity),
so you can do fast due diligence: confirm a framework is active, compare
alternatives, and pull a repo's details without leaving your editor. Beacon also
validates endpoint reachability and flags fraudulent nodes.
```

### mcp.so
- **Name:** Beacon — AI Agent Search Engine
- **One-liner:** Search 3,800+ open-source AI agents by capability, ranked by real GitHub traction — from Claude / Cursor / Cline / Windsurf.
- **Install:** `npx -y beacon-mcp`
- **Links:** portal, npm, GitHub (above)

### Also submit to
- Glama, Smithery, mcp.so (above)
- PulseMCP (pulsemcp.com)
- awesome-mcp-servers (GitHub PR — see below)
- modelcontextprotocol/servers community list (GitHub PR)

---

## 6) awesome-list PR (one honest line each — NOT a mass firehose)

**Target repos:** punkpeye/awesome-mcp-servers, e2b-dev/awesome-ai-agents,
kyrolabs/awesome-agents, Merit-Systems/awesome-x402

**PR title:** `Add Beacon — search engine for open-source AI agents (MCP server)`

**Line to add:**
```markdown
- [Beacon](https://portal-five-phi-54.vercel.app) - Search engine for open-source AI agents. Indexes 3,800+ repos (CrewAI, LangChain, ElizaOS, AutoGen, MCP servers) searchable by capability and ranked by GitHub traction. MCP server: `npx -y beacon-mcp`.
```

**PR body:**
```
Adds Beacon, a search engine / directory for open-source AI agents.

- 3,800+ agents indexed from GitHub, searchable by capability
- Ranked by real GitHub stars + activity; endpoint validation + fraud filtering
- MCP server so you can search from inside Claude/Cursor: npx -y beacon-mcp
- Free, no API key

Portal: https://portal-five-phi-54.vercel.app
npm: https://www.npmjs.com/package/beacon-mcp
```

---

## 7) Discord / community drop (ElizaOS, CrewAI, MCP servers)

```
Built a search engine for open-source AI agents — indexes 3,800+ repos (incl. a
lot of ElizaOS/CrewAI/MCP servers), searchable by capability and ranked by GitHub
stars + activity. Also an MCP server so you can search from inside your editor:
npx -y beacon-mcp

Portal: https://portal-five-phi-54.vercel.app

Would love feedback + what's missing so I can add sources.
```

---

## 8) Short blurbs (for anywhere — Product Hunt tagline, bios, etc.)

- **6 words:** Search engine for AI agents.
- **Tagline:** Find, compare & verify 3,800+ open-source AI agents.
- **Product Hunt:** Beacon — the search engine for open-source AI agents. Search
  3,800+ repos by capability, ranked by GitHub traction, usable from your editor
  via MCP. Free, no key.

---

## Suggested order (for whoever publishes)
1. Submit beacon-mcp to Smithery, Glama, mcp.so, PulseMCP (sends steady traffic).
2. Post Show HN (Tue–Thu morning ET) — the big spike.
3. Same day: X thread (@Enrichagent) + Reddit (r/LocalLLaMA, r/AI_Agents).
4. awesome-list PRs (one each).
5. Discords + LinkedIn.
Reply to every comment/PR quickly — engagement in hour 1 drives the rest.
