#!/usr/bin/env node
/**
 * Beacon MCP server — stdio transport (Cursor, Claude Desktop, Cline).
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createBeaconServer, registryUrl } from "./beacon-server.js";
const server = createBeaconServer();
const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`beacon-mcp connected — registry: ${registryUrl()}`);
