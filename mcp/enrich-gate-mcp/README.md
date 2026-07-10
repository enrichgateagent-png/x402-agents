# enrich-gate-mcp

MCP server that gives your AI agent **web search, neural search, URL scraping,
and LLM inference** — paid per call in USDC via [x402](https://x402.org).
No accounts, no API keys, no subscriptions. Just a funded wallet.

| Tool | Price/call | Backed by |
|---|---|---|
| `web_search` | $0.01 | Google results (Serper) |
| `neural_search` | $0.012 | Exa semantic search |
| `scrape_url` | $0.015 | Firecrawl → clean markdown |

Payments settle on Base as USDC using the x402 `exact` scheme — gasless for
the buyer (EIP-3009); you only need USDC, no ETH.

## Setup (Claude Desktop / Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "enrich-gate": {
      "command": "npx",
      "args": ["-y", "enrich-gate-mcp"],
      "env": {
        "EVM_PRIVATE_KEY": "0x...your agent wallet key (holds USDC on Base)"
      }
    }
  }
}
```

Fund the wallet with a few dollars of USDC on Base. Each tool call pays
automatically; unused funds stay in your wallet.

⚠️ Use a dedicated agent wallet with a small balance — never your main wallet.

## Env vars

- `EVM_PRIVATE_KEY` — buyer wallet private key (required for payments)
- `ENRICH_GATE_URL` — gateway URL (default: `https://enrich-gate.vercel.app`)

## How it works

Tool call → gateway responds `402 Payment Required` with terms →
[x402-fetch](https://www.npmjs.com/package/x402-fetch) signs a USDC transfer
authorization → gateway verifies & settles via the Coinbase CDP facilitator →
you get the result. Round trip is typically 2–4 seconds.

MIT
