# Dockerfile for Glama (and any container host). Installs the published package
# and runs the stdio MCP server. Introspection (initialize + tools/list) responds
# without network; tool calls reach the public Beacon registry.
FROM node:22-slim

# Install the published server globally.
RUN npm install -g beacon-mcp@latest

# Registry is public and defaulted; override if you self-host.
ENV BEACON_REGISTRY_URL=https://registry-ruby.vercel.app

# Stdio MCP server.
ENTRYPOINT ["beacon-mcp"]
