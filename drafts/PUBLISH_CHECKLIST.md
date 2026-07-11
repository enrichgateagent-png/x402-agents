# Publish & Listing Checklist (the stuff that needs your accounts)

These are the one-command-away steps that make Beacon installable + discoverable.
Everything is built and tested; this is just publishing.

## 1. npm — beacon-mcp (the MCP server, highest priority)
```bash
cd mcp/beacon-mcp
npm run build          # compiles to dist/
npm login              # enrichgatagent account (or a beacon account)
npm publish --access public
```
Then `npx -y beacon-mcp` works for everyone. Verify:
```bash
npx -y beacon-mcp   # should print "beacon-mcp connected — registry: ..."
```

## 2. PyPI — beacon-agent (the auto-register SDK)
```bash
cd sdk/beacon-agent
pip install build twine
python -m build
twine upload dist/*    # needs a PyPI account + token
```
Then `pip install beacon-agent` works.

## 3. MCP directories (send real traffic — free, opt-in)
Submit `beacon-mcp` to:
- [ ] modelcontextprotocol/servers (GitHub PR to the community list)
- [ ] mcp.so
- [ ] Smithery (smithery.ai)
- [ ] Glama (glama.ai/mcp)
- [ ] awesome-mcp-servers (punkpeye/awesome-mcp-servers) — PR

## 4. awesome-list PRs (one honest PR each, not a firehose)
- [ ] awesome-x402 (already did 2 earlier — add beacon-mcp line)
- [ ] awesome-agents / e2b-dev awesome-ai-agents
- [ ] awesome-crewai, awesome-langchain (Ecosystem sections)

## 5. Launch day (see LAUNCH.md)
- [ ] Post Show HN (Tue–Thu morning ET)
- [ ] X thread from @Enrichagent
- [ ] Reddit r/LocalLLaMA + r/AI_Agents
- [ ] ElizaOS + CrewAI Discords (share the portal, ask for feedback)

## Order that matters
1. npm publish beacon-mcp  ← do this FIRST (the launch links to it)
2. MCP directory submissions
3. Launch posts
4. PyPI + awesome PRs

Registry is live at https://registry-ruby.vercel.app · portal at
https://portal-five-phi-54.vercel.app
