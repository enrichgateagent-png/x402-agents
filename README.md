# x402 Agents

A portfolio of independent, genuinely useful x402 seller agents. Each agent is a
standalone paid API that any wallet-equipped AI agent can discover (via Bazaar)
and pay per call in USDC. No closed loops: agents use free/public upstream data
or buy from *external* x402 services, and sell to *external* buyers.

Target: each agent earning $200–300/mo is a win; portfolio of 20–50 compounds.

## Research-backed roadmap

Categories ranked by proven x402 demand (x402scan leaderboard, July 2026:
data-for-agents and DeFi intelligence dominate; LLM gateways are saturated).

### Wave 0 — proven killer use cases (clone the leaderboard winners)
| # | Agent | Clones | Model | Status |
|---|-------|--------|-------|--------|
| 0 | **enrich-gate** | StableEnrich (#1, $3.1K/mo, 108K txns) | Resell gated APIs (Serper/Exa/Firecrawl) per-call with markup. Buyer pays for *access without subscription* | Built — needs provider keys |

Unit economics: search costs ~$0.001 upstream (Serper), sells at $0.01 → 10x.
Scrape ~$0.003 upstream (Firecrawl), sells at $0.015 → 5x. At StableEnrich's
volume (108K calls/mo) that's ~$1K/mo gross per gateway.

### Wave 1 — zero input cost, pure margin
| # | Agent | What it sells | Price | Upstream (free) |
|---|-------|--------------|-------|-----------------|
| 1 | **token-guard** | Token safety / rug-check score | $0.005/call | GoPlus, DexScreener, Honeypot.is |
| 2 | wallet-intel | Address risk + activity profile | $0.005/call | public RPCs, Etherscan free tier |
| 3 | liq-depth | DEX liquidity depth + slippage estimate | $0.003/call | DexScreener, GeckoTerminal |
| 4 | gas-oracle | Multi-chain gas + inclusion-time predictions | $0.001/call | public RPCs |
| 5 | pair-screener | New pair alerts w/ safety pre-filter | $0.01/call | DexScreener + token-guard logic |

### Wave 2 — data enrichment (small upstream cost, proven demand — StableEnrich pattern)
6. news-digest — crypto news summarized per query (RSS + local LLM)
7. sentiment-scan — token social sentiment score
8. site-extract — clean markdown extraction of any URL
9. sec-headlines — regulatory filings/alerts feed
10. price-feed — normalized OHLCV across CEX/DEX

### Wave 3 — compute/verification (AgentLISA pattern, higher price points)
11. contract-audit-lite — static analysis of a contract address ($0.05–0.25/call)
12. proof-verify — verify ZK proofs as a service
13. sim-tx — transaction simulation / revert prediction
14. agent-kya — "Know Your Agent" attestation checks (identified market gap)

### Skip (saturated / no money)
- Generic LLM gateways (BlockRun + 10 others, race to zero)
- Raw Twitter data resellers (twit.sh: $207/mo)

## Stack
- Node 24 + TypeScript + [Hono](https://hono.dev)
- `x402-hono` payment middleware, USDC on Base (`base-sepolia` for testing)
- Facilitator: x402.org (testnet, free) → Coinbase CDP (mainnet, enables Bazaar
  auto-discovery via `discoverable: true`)
- One directory per agent under `agents/`, deployable independently

## Running an agent
```bash
cd agents/token-guard
npm install
cp .env.example .env   # set PAY_TO to your receiving wallet
npm run dev
```
Without `PAY_TO` set, the agent runs in free mode (no paywall) for local testing.

## Automated distribution
Discovery in this ecosystem is mostly automatic — the only push needed is one-time:
- **Bazaar / agentic.market / Onyx Bazaar**: auto-indexed once you take payments
  through the CDP facilitator with `discoverable: true` (already in route configs)
- **x402scan**: indexes onchain payments automatically
- **MCP wrapper** (`mcp/enrich-gate-mcp`): npm-publishable stdio server exposing
  `web_search` / `neural_search` / `scrape_url`. Any agent user adds it to their
  MCP config with a funded wallet key and pays us per call via x402-fetch.
  This is distribution-as-code — publish once, every install is a paying client.
- One-time manual: PR to awesome-x402 lists, launch post on X

## Distribution checklist (per agent)
1. Mainnet via CDP facilitator with `discoverable: true` → auto-listed in x402 Bazaar
2. Clear input/output schemas in route config (this is your SEO for agent buyers)
3. Register on agentic.market / Onyx Bazaar; PR to awesome-x402 lists
4. Price low initially to climb x402scan leaderboard (visible social proof)
5. Ship an MCP wrapper so the tool is callable directly from Claude/agent runtimes

- [JMT x402 Agent Tools](https://jmt-x402-proxy.jmthomasofficial.workers.dev) — 25 paid x402 endpoints on Base mainnet: web search, AI analysis, crypto/stock data, SEC filings, company intel, news, sentiment, macro dashboard. $0.001-$0.15/call USDC. Local LLM-powered.