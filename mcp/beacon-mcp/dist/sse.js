#!/usr/bin/env node
/**
 * Beacon MCP server — SSE transport for Glama remote proxy (no hosted credits).
 *
 * Glama Console → Remote → SSE URL:
 *   http://<YOUR_GCP_VM_IP>:8001/sse
 */
import express from "express";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { createBeaconServer, registryUrl } from "./beacon-server.js";
const PORT = Number(process.env.MCP_SSE_PORT ?? "8001");
const server = createBeaconServer();
const app = express();
app.use(express.json());
const transports = new Map();
app.get("/healthz", (_req, res) => {
    res.json({ ok: true, transport: "sse", registry: registryUrl() });
});
app.get("/sse", async (req, res) => {
    const transport = new SSEServerTransport("/messages", res);
    transports.set(transport.sessionId, transport);
    res.on("close", () => transports.delete(transport.sessionId));
    await server.connect(transport);
});
app.post("/messages", async (req, res) => {
    const sessionId = String(req.query.sessionId ?? "");
    const transport = transports.get(sessionId);
    if (!transport) {
        res.status(404).json({ error: "unknown sessionId" });
        return;
    }
    await transport.handlePostMessage(req, res);
});
app.listen(PORT, "0.0.0.0", () => {
    console.error(`beacon-mcp SSE listening on http://0.0.0.0:${PORT}/sse — registry: ${registryUrl()}`);
});
