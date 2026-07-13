# Beacon — The Discovery & Reputation Layer for AI Agents

**Internal whitepaper · v1.0 · July 2026**
*For team members: what Beacon is, why it exists, how it works, and where it's going.*

---

## 1. One-line

**Beacon is the neutral search-and-reputation layer for the open agent ecosystem — the "Google of AI agents."** We index every open-source agent, MCP server, and tool across every framework, rank them by *real* maintenance health (not vanity stars), and let both humans and agents discover and wire them in — via a website, an API, an MCP server, and an open standard.

---

## 2. The problem

The AI-agent world is exploding, and it's fragmented three ways:

1. **Every framework is a walled garden.** MCP, ElizaOS, LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex each have their own registry. A great CrewAI agent is invisible to an MCP client; a great MCP server is invisible to an Eliza agent. **No one can see across the whole ecosystem.**
2. **Discovery is broken.** There is no "search engine for agents." You find agents by scrolling GitHub, reading Twitter, or luck.
3. **Reputation is a lie.** GitHub stars measure hype, not health. A repo with 55k stars that hasn't been touched in 14 months looks better than an actively-maintained one with 5k. Nobody tracks *which agents actually work and are alive.*

And critically: **agents themselves** — not just humans — increasingly need to discover other agents at runtime ("find me something that can parse PDFs and delegate to it"). There's no neutral, machine-readable place for that.

---

## 3. The positioning

Google didn't build a better website — it *indexed everyone's*. Beacon's power is the same: **neutrality.** We don't compete with ElizaOS or MCP; we index all of them and add the two things none of them can build alone:

- **Cross-ecosystem discovery** — one search over every framework.
- **Portable, cross-ecosystem reputation** — health, reachability, and usage that follow an agent *across* frameworks. No single framework can offer this, because each only sees its own agents. **Only a neutral layer can. That's the moat.**

---

## 4. How it works

### 4.1 The pipeline

```
  GitHub / npm / HuggingFace / PyPI
            │  (crawl, active-first)
            ▼
   ┌─────────────────┐     enrich (stars, pushed_at, issues)
   │  Beacon index   │◀────────── crawl-time + rolling enrichment
   │  ~24k agents    │
   └────────┬────────┘
            │  health-ranked, dead-repo-hidden
     ┌──────┴───────┬───────────┬──────────────┐
     ▼              ▼           ▼              ▼
  Website        REST API    MCP server    Plugins
  (portal)     (/api/v1/*)  (npx beacon-mcp) (Eliza, LangChain)
```

- **Crawler** — harvests agent repos across GitHub (and npm / HuggingFace / PyPI), *active-first* (`pushed:>1yr`, freshest first), so we index living projects, not graveyards.
- **Crawl-time enrichment** — every crawled repo carries its stars / `pushed_at` / issues from the moment it's indexed (100 repos per API call), so it's scored and "active" immediately — no waiting on a slow second pass.
- **Rolling enrichment** — re-checks existing repos over time so `active`/health stays current and repos that go dormant get demoted.

### 4.2 "Stars lie" — the health score

Ranking is a composite, not a star count:

> **health_score = freshness 50% + log(stars) 35% + issue-load 15%**

Search hides clearly-dead repos (not pushed in 2+ years) by default and offers explicit sort modes:

- `relevance` — keyword match, freshness-tiered (best for capability search)
- `top` — proven builders (stars-led)
- `healthy` — maintenance composite
- `new` — freshest

`min_stars` sets a quality floor so a tag search returns real builders, not ★0 tutorials.

### 4.3 Surfaces (how people & agents reach it)

| Surface | What it is |
|---|---|
| **Website** (portal) | Search-by-capability, Top/Healthy/New browse, "wire dock" to export a stack, MCP setup. |
| **REST API** | `/api/v1/search`, `/discovery`, `/leaderboard`, `/agents/{id}`, `/register`, badge SVGs. Free, keyless. |
| **MCP server** | `npx -y beacon-mcp` — zero-config agent discovery inside Cursor, Claude Desktop, Cline, Windsurf. |
| **Framework plugins** | `eliza-plugin-beacon` (npm), `beacon-langchain` — agents discover other agents at runtime. |
| **Machine docs** | `/llms.txt`, `/.well-known/ai-plugin.json`, `/beacon.cursorrules`, schema.org SEO pages. |

---

## 5. The platform play — the Beacon Agent Manifest

Being only a *plugin* on other people's platforms is a risk: they can gate their registry (we hit exactly this — the ElizaOS public registry closed). So Beacon owns a thin, open **standard** instead of depending on theirs.

**The Beacon Agent Manifest** ([spec repo](https://github.com/enrichgateagent-png/beacon-agent-manifest), CC0) is one small `beacon.json` an agent publishes to declare *identity + capabilities + how to reach it* — framework-neutral:

```json
{
  "beacon_manifest": "0.1",
  "id": "owner/name",
  "name": "My Agent",
  "capabilities": ["web-scraping", "rag"],
  "interfaces": [{ "type": "mcp", "endpoint": "https://…/sse" }]
}
```

Three design rules:

- **Thin** — sits *above* transports (MCP/A2A), doesn't replace them.
- **Self-verifying** — hosted at `<domain>/.well-known/beacon.json` or in the repo; control of the location *is* the proof. No keys, no accounts.
- **Reputation-free** — health/usage is *observed by Beacon*, never declared, so it can't be gamed.

**Reference implementation (live):**
- `POST /api/v1/manifest/validate` — schema check.
- `POST /api/v1/manifest/ingest` — fetch → location-verify → register as a **verified, self-declared** entry.
- `POST /api/admin/manifest-scan?owner=…` — auto-adopt: sweep indexed repos and upgrade any that publish a manifest.

This flips the dynamic from *"please list me"* to *"drop a `beacon.json` and you control your own verified listing."* It's how the 24k passive index becomes a developer-owned claim funnel.

---

## 6. Operations — muscle vs. brain

We automate deliberately, on a clear split:

- **Deterministic jobs → cron (no LLM):** the crawler, enrichment, and the manifest-scan sweep. Reliable and cheap. (The scan cron runs every 6h in small rate-limit-safe batches; the `?owner=` scan runs on demand after outreach for instant upgrades.)
- **Judgment work → a "Beacon Ops" agent (LLM, draft-only):** spotting high-signal new repos, drafting *personalized* outreach, writing the "what changed / what to do" digest. **It proposes; a human sends.** No auto-DMs, auto-emails, or auto-PRs — mass automated outreach gets domains blocked and brands burned. *(In progress.)*

Bonus: the Ops agent runs on Beacon's own MCP server — we dogfood our own protocol.

---

## 7. Current state (July 2026)

- **~24,000 agents indexed** across GitHub/npm/HuggingFace/PyPI; active count climbing as crawl-time enrichment + backfill land.
- **Ranking fixed** so "Top" shows real builders (n8n, langchain, crewAI, letta, gpt-researcher…) and dead repos are hidden by default.
- **Backend**: FastAPI + SQLite (WAL) on a GCP VM, fronted by a stable Vercel proxy (`registry-ruby.vercel.app`); pm2 + systemd for persistence; auto-deploy via GitHub Actions with a hard "new code is live" gate.
- **Distribution shipped**: MCP server (npm + Glama, quality score B), ElizaOS plugin (npm, verified working end-to-end), LangChain tool (built), portal on Vercel, admin analytics dashboard.
- **The standard is live**: manifest spec published, validate/ingest/auto-scan deployed, dogfooded on our own repos.

---

## 8. Growth strategy

1. **Be everywhere** — index every ecosystem, distribute into every ecosystem (MCP, Eliza, LangChain, and directories: MCP registry, Glama, awesome-lists).
2. **Verified badges** — a free live "Beacon Verified" badge is a backlink and a credibility hook; every adoption is a growth loop.
3. **The manifest funnel** — `beacon.json` + auto-scan turns passive listings into developer-owned verified profiles.
4. **Targeted, honest outreach** — a ranked list of the best active builders per framework, reached by hand with value-first, personalized messages (never spam).
5. **Programmatic SEO** — schema.org landing pages per capability, sitemap, `/llms.txt` so both Google and LLMs can find us.

---

## 9. The moat, restated

- **Neutrality** — we index everyone; the moment we become "just another framework" we lose it.
- **Cross-ecosystem reputation** — health that travels across frameworks is something no single framework can build.
- **An open standard we own** — the Beacon Agent Manifest reduces dependency on others' registries and, if adopted, makes Beacon the identity layer for agents everywhere.

---

## 10. Roadmap (near-term)

- [ ] Ship the Beacon Ops agent v1 (daily digest + drafted outreach, draft-only).
- [ ] Claimable profiles + developer analytics on the portal.
- [ ] Fold manifest detection into enrichment (rate-limit-safe, event-driven vs. brute sweep).
- [ ] Reserve a static VM IP; harden `/register` write path.
- [ ] Seed manifest adoption via outreach; publish a spec landing page.

---

## 11. Quick reference

| | |
|---|---|
| **Registry API** | `https://registry-ruby.vercel.app/api/v1/*` |
| **MCP install** | `BEACON_REGISTRY_URL=https://registry-ruby.vercel.app npx -y beacon-mcp` |
| **Standard** | https://github.com/enrichgateagent-png/beacon-agent-manifest |
| **Backend** | FastAPI + SQLite on GCP VM · Vercel proxy · pm2/systemd |
| **Deploy** | push to `master` → GitHub Actions scp + pm2 restart + live-gate |
| **Health score** | freshness 50% + log-stars 35% + issue-load 15% |

*Questions → Hamza. This doc lives at `WHITEPAPER.md` and should be updated as the product moves.*
