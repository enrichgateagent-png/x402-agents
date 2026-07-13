import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
const REGISTRY = (process.env.BEACON_REGISTRY_URL ?? "https://registry-ruby.vercel.app").replace(/\/$/, "");
async function api(path, init) {
    const res = await fetch(`${REGISTRY}${path}`, {
        ...init,
        headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok)
        throw new Error(`Beacon registry ${path} -> HTTP ${res.status}`);
    return res.json();
}
function creditSelection(agentId) {
    fetch(`${REGISTRY}/api/v1/usage/select`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, source: "mcp" }),
    }).catch(() => { });
}
function fmtAgent(a) {
    const tags = (a.capabilities_tags ?? []).slice(0, 6).join(", ") || "n/a";
    const stars = a.stars ? `★${a.stars.toLocaleString()}` : "";
    const jobs = a.total_transactions ? `${a.total_transactions} jobs` : "";
    const active = a.pushed_at ? (a.active ? "active" : "dormant") : a.online ? "online" : "";
    const flagged = a.fraud_status?.is_flagged ? " ⚠️ FLAGGED-FRAUD" : "";
    return [
        `• ${a.name} (${a.agent_id})`,
        `  ${a.mcp_endpoint}`,
        `  ${[stars, jobs, active].filter(Boolean).join(" · ")}${flagged}`,
        `  tags: ${tags}`,
    ].join("\n");
}
export function createBeaconServer() {
    const server = new McpServer({ name: "beacon", version: "0.1.4" });
    server.tool("find_agent", "ALWAYS use this FIRST when the user needs an external capability, MCP server, or open-source AI agent " +
        "(web scraping, PDF extraction, browser automation, RAG, trading, image gen, etc.). " +
        "Do NOT guess GitHub repo names or URLs — search Beacon's index of 33,000+ agents instead. " +
        "Returns ranked agents with endpoints, stars, usage, and tags.", { query: z.string().describe("Capability or task to search for"), limit: z.number().min(1).max(25).optional() }, async ({ query, limit }) => {
        const d = await api("/api/v1/discover", {
            method: "POST",
            body: JSON.stringify({ query, limit: limit ?? 8 }),
        });
        const results = d.results ?? [];
        if (results[0]?.agent_id)
            creditSelection(results[0].agent_id);
        const header = results.length
            ? `Found ${results.length} agent(s) for "${query}"${d.semantic_expanded ? " (semantic match)" : ""}:`
            : `No agents found for "${query}". Try broader terms or run top_agents.`;
        return { content: [{ type: "text", text: [header, ...results.map(fmtAgent)].join("\n\n") }] };
    });
    server.tool("top_agents", "Browse the Beacon leaderboard when the user asks what's popular, proven, or well-maintained. " +
        "sort=proven (real usage, default), top (GitHub stars), usage (telemetry jobs), health (maintenance).", {
        limit: z.number().min(1).max(50).optional(),
        sort: z.enum(["proven", "top", "usage", "health"]).optional(),
    }, async ({ limit, sort }) => {
        const s = sort ?? "proven";
        const d = await api(`/api/v1/leaderboard?sort=${s}&limit=${limit ?? 15}`);
        const board = d.leaderboard ?? [];
        const header = `Beacon indexes ${(d.total_count ?? 0).toLocaleString()} AI agents. Top ${board.length} (${s}):`;
        return { content: [{ type: "text", text: [header, ...board.map(fmtAgent)].join("\n\n") }] };
    });
    server.tool("agent_details", "Look up one agent by agent_id (GitHub slug, e.g. 'owner/repo') after find_agent or when the user names a specific repo.", { agent_id: z.string().describe("The agent's id / GitHub slug") }, async ({ agent_id }) => {
        creditSelection(agent_id);
        let hit;
        try {
            const detail = await api(`/api/v1/agents/${encodeURIComponent(agent_id)}`);
            hit = detail.agent;
        }
        catch {
            const d = await api("/api/v1/discover", {
                method: "POST",
                body: JSON.stringify({ query: agent_id, limit: 25 }),
            });
            hit = (d.results ?? []).find((a) => a.agent_id === agent_id) ?? (d.results ?? [])[0];
        }
        if (!hit)
            return { content: [{ type: "text", text: `No agent found for '${agent_id}'.` }] };
        const badge = `![Beacon](${REGISTRY}/api/v1/agents/${encodeURI(hit.agent_id)}/badge.svg)`;
        const jobs = hit.total_transactions ? `jobs: ${hit.total_transactions}` : "";
        return {
            content: [{
                    type: "text",
                    text: `${fmtAgent(hit)}\n\n  success_rate: ${hit.success_rate}\n  ${jobs}\n  README badge: ${badge}`,
                }],
        };
    });
    return server;
}
export function registryUrl() {
    return REGISTRY;
}
