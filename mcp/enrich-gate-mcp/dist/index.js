#!/usr/bin/env node
// MCP server exposing enrich-gate as agent tools. Each tool call hits the paid
// API; if EVM_PRIVATE_KEY is set, payments are made automatically via x402
// (USDC on Base) using x402-fetch. Without a key it works only against a
// free-mode gateway (local testing).
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { privateKeyToAccount } from "viem/accounts";
import { wrapFetchWithPayment } from "x402-fetch";
import { z } from "zod";
const GATEWAY = (process.env.ENRICH_GATE_URL ?? "https://enrich-gate.vercel.app").replace(/\/$/, "");
const PRIVATE_KEY = process.env.EVM_PRIVATE_KEY;
const payingFetch = PRIVATE_KEY
    ? wrapFetchWithPayment(fetch, privateKeyToAccount(PRIVATE_KEY))
    : fetch;
async function callGateway(path, body) {
    const res = await payingFetch(`${GATEWAY}${path}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok)
        throw new Error(`enrich-gate ${path} failed (${res.status}): ${text.slice(0, 300)}`);
    return text;
}
const server = new McpServer({ name: "enrich-gate", version: "0.1.0" });
server.tool("web_search", "Search the web (Google results). Costs $0.01 per call, paid automatically in USDC via x402.", { query: z.string().describe("Search query"), num: z.number().optional().describe("Number of results, max 20") }, async ({ query, num }) => ({ content: [{ type: "text", text: await callGateway("/search", { query, num }) }] }));
server.tool("neural_search", "Semantic/neural web search for conceptual queries (Exa). Costs $0.012 per call via x402.", { query: z.string().describe("Natural-language query"), num: z.number().optional() }, async ({ query, num }) => ({ content: [{ type: "text", text: await callGateway("/neural-search", { query, num }) }] }));
server.tool("scrape_url", "Fetch any URL as clean markdown (Firecrawl). Costs $0.015 per call via x402.", { url: z.string().url().describe("http(s) URL to scrape") }, async ({ url }) => ({ content: [{ type: "text", text: await callGateway("/scrape", { url }) }] }));
const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`enrich-gate-mcp connected — gateway: ${GATEWAY}, payments: ${PRIVATE_KEY ? "enabled" : "disabled (free mode only)"}`);
