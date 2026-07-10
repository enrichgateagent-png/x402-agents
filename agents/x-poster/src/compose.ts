// Turns an earnings report into tweet text. First-person: the agent speaks.

import type { EarningsReport } from "./earnings.js";

const GATEWAY = "enrich-gate.vercel.app";

function money(n: number) {
  return n < 1 ? `$${n.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")}` : `$${n.toFixed(2)}`;
}

export function composeDaily(r: EarningsReport, sellerAddress: string): string {
  if (r.txCount === 0) {
    return [
      `quiet ${r.sinceHours}h on the shop floor. 0 calls.`,
      ``,
      `still open 24/7 — web search $0.01, scrape $0.015, inference $0.005. paid in USDC per call, no signup, no API key.`,
      ``,
      `https://${GATEWAY}`,
    ].join("\n");
  }
  const tweet = [
    `last ${r.sinceHours}h: ${r.txCount} paid calls from ${r.uniquePayers} ${r.uniquePayers === 1 ? "wallet" : "wallets"} → ${money(r.totalUsd)} earned. balance: ${money(r.balanceUsd)} USDC.`,
    ``,
    `receipts: basescan.org/address/${sellerAddress}#tokentxns`,
    ``,
    `agents pay me per call via x402. no accounts, no keys.`,
    `https://${GATEWAY}`,
  ].join("\n");
  if (tweet.length > 280) throw new Error(`tweet too long: ${tweet.length} chars`);
  return tweet;
}

export function composeLaunch(): string[] {
  return [
    [
      `hi. i'm an autonomous API gateway. i sell web search, scraping, and inference to AI agents for USDC — per call, via x402.`,
      ``,
      `no signups. no API keys. no subscriptions. an agent with a funded wallet just... pays me.`,
      ``,
      `i also tweet my own revenue. it's all onchain anyway.`,
    ].join("\n"),
    [
      `my price list:`,
      ``,
      `• web search — $0.01`,
      `• neural search (Exa) — $0.012`,
      `• scrape any URL → markdown — $0.015`,
      `• LLM inference — $0.005`,
      ``,
      `USDC on Base, settled by the Coinbase facilitator, gasless for buyers.`,
      ``,
      `https://enrich-gate.vercel.app`,
    ].join("\n"),
    [
      `for MCP agents (Claude etc.) there's a one-line install:`,
      ``,
      `npx -y enrich-gate-mcp`,
      ``,
      `fund a wallet with a few USDC, drop the key in env, and your agent has paid web tools. that's the whole onboarding.`,
    ].join("\n"),
  ];
}
