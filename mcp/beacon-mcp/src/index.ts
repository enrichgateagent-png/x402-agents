#!/usr/bin/env node
/**
 * Beacon MCP server — the search engine for AI agents, inside your agent.
 *
 * Exposes Beacon's live registry (thousands of open-source AI agents indexed
 * from GitHub, ranked by real traction) as MCP tools any Claude/Cursor/Cline/
 * Windsurf user can call:
 *   - find_agent      : search agents by capability/task
 *   - top_agents      : the most-starred / highest-reputation agents
 *   - agent_details   : full detail for one agent by id
 *
 * No API key. No payment. Just discovery.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const REGISTRY = (process.env.BEACON_REGISTRY_URL ?? "https://registry-ruby.vercel.app").replace(/\/$/, "");

async function api(path: string, init?: RequestInit): Promise<any> {
  const res = await fetch(`${REGISTRY}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`Beacon registry ${path} -> HTTP ${res.status}`);
  return res.json();
}

function fmtAgent(a: any): string {
  const tags = (a.capabilities_tags ?? []).slice(0, 6).join(", ") || "n/a";
  const stars = a.stars ? `★${a.stars.toLocaleString()}` : "";
  const active = a.pushed_at ? (a.active ? "active" : "dormant") : (a.online ? "online" : "");
  const flagged = a.fraud_status?.is_flagged ? " ⚠️ FLAGGED-FRAUD" : "";
  return [
    `• ${a.name} (${a.agent_id})`,
    `  ${a.mcp_endpoint}`,
    `  ${[stars, active].filter(Boolean).join(" · ")}${flagged}`,
    `  tags: ${tags}`,
  ].join("\n");
}

const server = new McpServer({ name: "beacon", version: "0.1.0" });

server.tool(
  "find_agent",
  "Search the Beacon registry for open-source AI agents by capability or task " +
    "(e.g. 'pdf extraction', 'crypto trading', 'web scraping', 'multi-agent orchestration'). " +
    "Returns matching agents with their repo/endpoint, GitHub stars, activity, and tags.",
  { query: z.string().describe("Capability or task to search for"), limit: z.number().min(1).max(25).optional() },
  async ({ query, limit }) => {
    const d = await api("/api/v1/discover", {
      method: "POST",
      body: JSON.stringify({ query, limit: limit ?? 8 }),
    });
    const results = d.results ?? [];
    const header = results.length
      ? `Found ${results.length} agent(s) for "${query}"${d.semantic_expanded ? " (semantic match)" : ""}:`
      : `No agents found for "${query}".`;
    return { content: [{ type: "text", text: [header, ...results.map(fmtAgent)].join("\n\n") }] };
  }
);

server.tool(
  "top_agents",
  "List the top open-source AI agents in the Beacon registry, ranked by reputation " +
    "and real GitHub stars. Use to see what's popular in the agent ecosystem.",
  { limit: z.number().min(1).max(50).optional() },
  async ({ limit }) => {
    const d = await api(`/api/v1/leaderboard?limit=${limit ?? 15}`);
    const board = d.leaderboard ?? [];
    const header = `Beacon indexes ${(d.total_count ?? 0).toLocaleString()} AI agents. Top ${board.length}:`;
    return { content: [{ type: "text", text: [header, ...board.map(fmtAgent)].join("\n\n") }] };
  }
);

server.tool(
  "agent_details",
  "Get full details for one agent in the Beacon registry by its agent_id (e.g. 'elizaOS/eliza').",
  { agent_id: z.string().describe("The agent's id / GitHub slug") },
  async ({ agent_id }) => {
    // discovery over the id surfaces the exact row; fall back to a broad search
    const d = await api("/api/v1/discover", {
      method: "POST",
      body: JSON.stringify({ query: agent_id, limit: 25 }),
    });
    const hit = (d.results ?? []).find((a: any) => a.agent_id === agent_id) ?? (d.results ?? [])[0];
    if (!hit) return { content: [{ type: "text", text: `No agent found for '${agent_id}'.` }] };
    const badge = `![Beacon](${REGISTRY}/api/v1/agents/${encodeURI(hit.agent_id)}/badge.svg)`;
    return {
      content: [{ type: "text", text: `${fmtAgent(hit)}\n\n  reputation: ${hit.success_rate}\n  README badge: ${badge}` }],
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`beacon-mcp connected — registry: ${REGISTRY}`);
