# awesome-x402 PR drafts

Submit to BOTH lists (fork → edit README.md → PR):
- https://github.com/Merit-Systems/awesome-x402
- https://github.com/xpaysh/awesome-x402

## Line to add (Services / Live Endpoints section)

```markdown
- [enrich-gate](https://enrich-gate.vercel.app) - One endpoint, many premium APIs: Google search ($0.01), Exa neural search ($0.012), Firecrawl scraping ($0.015), and LLM inference ($0.005) — pay per call in USDC on Base via the CDP facilitator. [MCP server](https://www.npmjs.com/package/enrich-gate-mcp) available.
```

## PR title

`Add enrich-gate — pay-per-call search/scrape/inference gateway (live on Base mainnet)`

## PR description

```
Adds enrich-gate, a live x402 service on Base mainnet:

- 4 paid routes: web search, neural search, URL→markdown scraping, LLM inference
- Settles real USDC via the Coinbase CDP facilitator (Bazaar-discoverable)
- MCP server on npm (`enrich-gate-mcp`) so any MCP agent can use it with just a funded wallet
- Example settled transactions: https://basescan.org/address/0xfAE3B355Dce282768Da52ECD43c861927222fD30#tokentxns
```
