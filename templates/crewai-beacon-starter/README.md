# CrewAI + Beacon starter

Copy-paste starter: your CrewAI agents auto-register and can discover other agents by capability.

## 1. Install

```bash
pip install beacon-agent crewai
```

## 2. One line at the top of your app

```python
import beacon_agent
beacon_agent.enable()  # hooks CrewAI/LangChain/AutoGen — registers + injects discover tool
```

## 3. Use in Cursor / Claude (MCP)

```bash
npx beacon-mcp init
```

Then ask: *"Use beacon to find a PDF extraction MCP server."*

## Links

- Portal: https://portal-five-phi-54.vercel.app
- Registry API: https://registry-ruby.vercel.app
- npm MCP: https://www.npmjs.com/package/beacon-mcp
