# Beacon — Launch Kit

Positioning: **the search engine / directory for AI agents.** Lead with the
directory value (real, usable today), not "register your agent."

Live links:
- Portal: https://portal-five-phi-54.vercel.app
- Registry API: https://registry-ruby.vercel.app
- Repo: https://github.com/enrichgateagent-png/x402-agents
- MCP: `npx -y beacon-mcp`

---

## Show HN

**Title:**
`Show HN: Beacon – a search engine for open-source AI agents (3,000+ indexed)`

**Body:**
```
I kept losing track of which open-source AI agents exist and which are actually
maintained, so I built Beacon: a searchable index of AI agents.

It crawls GitHub for agent repos (CrewAI, LangChain, LangGraph, ElizaOS, AutoGen,
MCP servers, etc.), normalizes their capabilities into tags, and lets you search
by what you actually want — "pdf extraction", "web scraping", "multi-agent
orchestration" — ranked by real GitHub traction and whether the repo is still
active. ~3,000 agents indexed so far.

Two things I care about:
- It's useful at zero adoption — it's a directory of repos that already exist,
  not a walled garden waiting for signups.
- There's an MCP server (`npx -y beacon-mcp`), so you can search the index from
  inside Claude/Cursor/Cline while you're building.

Stack: FastAPI + Turso (libSQL) on Vercel; a GitHub Actions crawler; a semantic
fallback so vague queries still return something; and a reputation/telemetry
layer (optional SDK) with a live SVG badge for READMEs.

Honest status: the crawler-sourced index is real and useful now; the
self-registration/reputation side is early (I'm one of ~5 registered nodes). I'd
love feedback on whether the directory is actually useful and what's missing.

Portal: https://portal-five-phi-54.vercel.app
```

Notes: post Tue–Thu ~8-10am ET. Reply to every comment in the first 2 hours.
Don't oversell adoption — the honest framing plays better on HN.

---

## Reddit (r/LocalLLaMA, r/AI_Agents, r/LLMDevs)

**Title:** `I built a searchable directory of 3,000+ open-source AI agents (with an MCP server)`

**Body:**
```
Finding good open-source agents is a mess — they're scattered across GitHub with
inconsistent naming. So I made Beacon: search agents by capability, see real
stars + whether they're still maintained, and pull it up from inside your editor
via MCP (`npx -y beacon-mcp`).

It indexes CrewAI / LangChain / LangGraph / ElizaOS / AutoGen / MCP-server repos
(~3k so far). Free, no signup to search.

Portal: https://portal-five-phi-54.vercel.app

Curious what agents you'd expect to find that are missing — I'll add sources.
```

Notes: lead with utility, ask a question at the end, no hard CTA. Subreddits are
allergic to promo — the "what's missing?" ask makes it a discussion.

---

## X thread (post from @Enrichagent)

1/ Introducing Beacon — the search engine for AI agents. Google indexes websites
so humans can find them. Beacon indexes agents so agents (and their builders) can
find each other. 3,000+ open-source AI agents indexed, searchable by capability. 🧵

2/ Search "pdf extraction", "web scraping", "multi-agent orchestration" — get real
repos ranked by GitHub stars and whether they're still maintained. Not a walled
garden: it's useful today, no signup to search.

3/ Building an agent? `npx -y beacon-mcp` drops the whole index inside
Claude/Cursor/Cline. Ask your agent to find another agent. There's a LangChain
tool + a one-line auto-register SDK too.

4/ Browse it live: https://portal-five-phi-54.vercel.app

---

## Dev.to / blog post outline

Title: "I indexed 3,000 open-source AI agents. Here's what the ecosystem looks like."
- The discovery problem for agents
- How the crawler + capability-normalization works
- What's popular (star distribution, most-active frameworks)
- The MCP angle: search agents from your editor
- What Beacon is / isn't yet (honest)
- CTA: try the portal, install the MCP server
