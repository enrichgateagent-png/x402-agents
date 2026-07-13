"""
beacon_langchain_plugin.py — native LangChain plugin for the Beacon registry.

Exposes Beacon's agent-discovery capability as a first-class LangChain tool that
plugs straight into modern Agent Executors and LCEL runnable sequences. It ships
in two interchangeable forms:

  * `BeaconAgentDiscoveryTool` — a `BaseTool` subclass (class-inheritance model),
    with a typed `args_schema`, sync `_run`, and async `_arun`, fully wired into
    LangChain's callback/tracing manager.
  * `beacon_agent_discovery` — the same capability exposed via the modern `@tool`
    decorator for developers who prefer the functional style.

Both call POST https://registry-ruby.vercel.app/api/v1/discover and NEVER raise
into the agent loop: every failure is caught and returned as a plain, useful
string so the LLM can reason about it and continue.

Dependencies: langchain-core, pydantic, requests.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional, Type

import requests
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

BEACON_REGISTRY_URL = os.environ.get("BEACON_REGISTRY_URL", "https://registry-ruby.vercel.app").rstrip("/")
DISCOVER_ENDPOINT = f"{BEACON_REGISTRY_URL}/api/v1/discover"
DEFAULT_LIMIT = 5
REQUEST_TIMEOUT = 10

TOOL_NAME = "beacon_agent_discovery"
TOOL_DESCRIPTION = (
    "Discover other live AI agents by capability from the Beacon registry "
    "(the discovery index for AI agents). Use this whenever the task would "
    "benefit from finding, delegating to, or connecting with another agent, "
    "tool, or service. Input: a short natural-language capability or task "
    "query (e.g. 'pdf extraction', 'crypto trading', 'web scraping'). Returns "
    "the best-matching agents with their endpoint, capability tags, reputation "
    "score, and online status."
)

# Reuse one pooled session for connection reuse across many tool calls.
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "beacon-langchain-plugin/1.0"})


class BeaconDiscoveryInput(BaseModel):
    """Typed argument schema so the LLM knows exactly what to pass."""

    query: str = Field(
        ...,
        description="Semantic capability or task to search other agents for, e.g. 'summarize research papers'.",
    )
    limit: int = Field(
        DEFAULT_LIMIT,
        ge=1,
        le=25,
        description="Maximum number of agents to return (1-25).",
    )


def _format_results(query: str, results: list) -> str:
    """Render discovery results into an LLM-friendly string."""
    if not results:
        return (
            f"Beacon discovery: no agents matched '{query}'. "
            f"Try a broader capability term."
        )
    lines = [f"Beacon found {len(results)} agent(s) for '{query}':"]
    for i, r in enumerate(results, 1):
        tags = ", ".join(r.get("capabilities_tags", []) or []) or "n/a"
        status = "online" if r.get("online") else "offline"
        rep = r.get("success_rate", "n/a")
        lines.append(
            f"{i}. {r.get('name', 'unknown')} — endpoint: {r.get('mcp_endpoint', 'n/a')} "
            f"| reputation: {rep} | status: {status} | tags: {tags}"
        )
    return "\n".join(lines)


def beacon_discover(query: str, limit: int = DEFAULT_LIMIT) -> str:
    """
    Core discovery call shared by both tool forms. Performs the POST and returns
    a formatted string. Catches ALL errors and returns a functional message so
    the caller never has to handle an exception.
    """
    query = (query or "").strip()
    if not query:
        return "Beacon discovery: empty query. Provide a capability to search for."
    try:
        resp = _SESSION.post(
            DISCOVER_ENDPOINT,
            json={"query": query, "limit": max(1, min(int(limit), 25))},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return (
                f"Beacon discovery is temporarily unavailable "
                f"(registry returned HTTP {resp.status_code}). Proceed without it."
            )
        data = resp.json()
        return _format_results(query, data.get("results", []))
    except requests.Timeout:
        return "Beacon discovery timed out. Proceed without it or retry later."
    except requests.RequestException as exc:
        return f"Beacon discovery could not reach the registry ({exc}). Proceed without it."
    except (ValueError, KeyError) as exc:
        return f"Beacon discovery returned an unexpected response ({exc}). Proceed without it."


class BeaconAgentDiscoveryTool(BaseTool):
    """
    Class-inheritance form of the Beacon discovery tool. Drop an instance into
    any Agent Executor's `tools` list; it integrates with LangChain's callback
    manager (tracing, LangSmith, streaming) via the run-manager hooks.
    """

    name: str = TOOL_NAME
    description: str = TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = BeaconDiscoveryInput
    return_direct: bool = False

    def _run(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return beacon_discover(query, limit)

    async def _arun(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        # Run the sync call in a worker thread so the event loop is never blocked.
        return await asyncio.to_thread(beacon_discover, query, limit)


@tool(TOOL_NAME, args_schema=BeaconDiscoveryInput)
def beacon_agent_discovery(query: str, limit: int = DEFAULT_LIMIT) -> str:
    """Discover other live AI agents by capability from the Beacon registry.

    Use when the task benefits from finding or delegating to another agent/tool.
    Returns matching agents with endpoint, capability tags, reputation, and
    online status. Never raises — errors come back as readable text.
    """
    return beacon_discover(query, limit)


# Ready-to-use singleton for the class-based form.
beacon_tool = BeaconAgentDiscoveryTool()

# Public exports.
__all__ = [
    "BeaconAgentDiscoveryTool",
    "beacon_agent_discovery",
    "beacon_tool",
    "beacon_discover",
    "BeaconDiscoveryInput",
]


if __name__ == "__main__":
    # ------------------------------------------------------------------ #
    # Reference: wiring Beacon into a modern LangChain OpenAI-tools agent.
    # ------------------------------------------------------------------ #
    #
    # from langchain_openai import ChatOpenAI
    # from langchain.agents import create_openai_tools_agent, AgentExecutor
    # from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    # from beacon_langchain_plugin import beacon_tool
    #
    # llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # prompt = ChatPromptTemplate.from_messages([
    #     ("system", "You are a helpful assistant. Use tools when useful."),
    #     ("human", "{input}"),
    #     MessagesPlaceholder("agent_scratchpad"),
    # ])
    # agent = create_openai_tools_agent(llm, tools=[beacon_tool], prompt=prompt)
    # executor = AgentExecutor(agent=agent, tools=[beacon_tool], verbose=True)
    # executor.invoke({"input": "Find me an agent that can extract data from PDFs"})
    #
    # Standalone smoke test of the discovery core (no LLM required):
    print(beacon_discover("pdf extraction", limit=3))
