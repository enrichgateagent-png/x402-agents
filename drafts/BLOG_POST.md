# I indexed 3,800 open-source AI agents. Here's what the ecosystem actually looks like.

*Publish on dev.to / Hashnode / your blog. Also the canonical link to share on X,
Reddit, Discord, LinkedIn. Tags: ai, opensource, mcp, llm, agents.*

---

Every week there's a new "awesome AI agents" list, a new framework, a new MCP
server. And every week it gets harder to answer a simple question: **is there
already an open-source agent that does the thing I'm about to build — and is it
actually maintained?**

So I built [Beacon](https://portal-five-phi-54.vercel.app): a search engine for
open-source AI agents. It crawls GitHub, normalizes what each agent *does* into
searchable capabilities, and ranks them by real signals. It's indexed ~3,800
agents so far across CrewAI, LangChain, LangGraph, ElizaOS, AutoGen, and MCP
servers.

Here's how it works and a few things I learned building it.

## The core problem: discovery is broken for agents

GitHub search is keyword-matching over repo names and READMEs. That's fine if you
know what you're looking for, but agents are described inconsistently — one calls
itself a "browser automation agent," another an "autonomous web navigator," a
third just "my-crew." Searching "web scraping agent" misses most of them.

Beacon fixes this by extracting capabilities from each repo's topics + description,
normalizing them into tags, and searching over *those*. It also has a semantic
fallback: if "auditing" returns too few literal matches, it expands to related
concepts (compliance, security, verification) so you still get useful results.

## The interesting part: ranking, because "stars lie"

The obvious way to rank is GitHub stars. It's also wrong. A repo can have 50,000
stars and not have shipped a commit in two years. Stars measure *historical hype*,
not *current usefulness*.

So Beacon computes a **health score** that weights:
- **Freshness (50%)** — days since last push
- **Stars (35%)** — log-scaled, so 10k and 100k aren't wildly different
- **Issue load (15%)** — open issues relative to activity

The result: a well-maintained mid-size agent outranks a famous dead one. Sort by
"Healthy" vs "Top" on the portal and you can see the reordering — some 100k-star
repos drop below 15k-star ones that actually shipped this week.

## It works inside your editor (MCP)

The thing I use most is the MCP server. One line:

```bash
npx -y beacon-mcp
```

drops three tools — `find_agent`, `top_agents`, `agent_details` — into Claude,
Cursor, Cline, or Windsurf. So mid-build, I can ask "find me an agent that does X"
and get real, current results instead of whatever was in the model's training
data. No API key.

## Stack

- **FastAPI + Turso (libSQL)** on Vercel — serverless, but with durable managed
  SQLite so the index persists.
- **GitHub Actions crawler** — runs every few hours, harvests new repos, respects
  rate limits.
- **Endpoint validation + a lightweight fraud/reputation layer** — so dead or
  malicious entries get filtered from results.
- **A live SVG badge** any repo can embed to show its Beacon status.

## What I learned about the ecosystem

- **MCP servers are exploding.** A huge share of new agent repos in the last few
  months are MCP servers, not framework-specific agents.
- **The long tail is enormous and mostly undiscoverable.** Past the top few
  hundred starred repos, there are thousands of genuinely useful small agents that
  no "awesome" list will ever include.
- **Maintenance is the real signal.** Once you rank by freshness, the "top" of
  each category looks completely different from the star-sorted view.

## Honest status

The crawler-sourced index is real and useful today. The self-registration side
(where agent authors claim their entry and get a reputation) is early — I'm one of
a handful of registered nodes. If you maintain an agent, you can register it and
grab a badge, but the directory is useful right now whether anyone registers or
not, because it's built on repos that already exist.

## Try it

- **Portal:** https://portal-five-phi-54.vercel.app
- **MCP:** `npx -y beacon-mcp`
- **API:** https://registry-ruby.vercel.app (`POST /api/v1/discover`)

I'd genuinely love feedback on two things: is the health ranking useful, and what
agents do you expect to find that are missing? I'll add sources.
