#!/usr/bin/env node
/**
 * Beacon MCP — stdio transport (Cursor, Claude Desktop, Cline).
 * Subcommands: init (configure IDE), default (run MCP server).
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createBeaconServer, registryUrl } from "./beacon-server.js";
import { runInit } from "./init.js";

if (process.argv.includes("init")) {
  await runInit();
  process.exit(0);
}

const server = createBeaconServer();
const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`beacon-mcp connected — registry: ${registryUrl()}`);
