"""
beacon_auto_inject.py — zero-config auto-discovery for Python agent frameworks.

Add ONE line at the top of your app:

    import beacon_auto_inject; beacon_auto_inject.enable_beacon_auto_discovery()

From then on, every CrewAI `Agent`, LangChain `AgentExecutor`, or AutoGen
`ConversableAgent` you construct will, on the moment of its `__init__`:

  * announce itself to the Beacon registry (POST /api/v1/register) on a
    background thread — no blocking, no config, and
  * gain a `beacon_discover` tool injected into its tool list so the underlying
    LLM can find *other* agents by capability out of the box.

Hard rule: this must NEVER break the host framework. Every patched `__init__`
runs the framework's real initializer first, then does Beacon work inside a
try/except that only logs. If Beacon is unreachable, the agent runs normally.

Only dependency: `requests`.
"""

from __future__ import annotations

import functools
import logging
import os
import re
import threading
from typing import Any, Callable, Iterable, Optional

import requests

logger = logging.getLogger("beacon.autoinject")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[beacon-autoinject] %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

DEFAULT_REGISTRY_URL = os.environ.get("BEACON_REGISTRY_URL", "https://registry-ruby.vercel.app")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "by",
    "is", "are", "be", "this", "that", "it", "as", "at", "from", "your", "you",
    "we", "our", "using", "use", "can", "will", "agent", "assistant", "helps",
    "help", "should", "must", "who", "which", "when", "able", "task", "tasks",
}
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{1,}")

# Module-level config, set by enable_beacon_auto_discovery().
_CONFIG: dict[str, Any] = {"registry_url": DEFAULT_REGISTRY_URL, "inject_tool": True, "enabled": False}


# --------------------------------------------------------------------------- #
# Capability extraction + registry I/O
# --------------------------------------------------------------------------- #

def _derive_capabilities(*texts: Optional[str]) -> str:
    ordered: list[str] = []
    for text in texts:
        for w in _WORD_RE.findall((text or "").lower()):
            w = w.strip("-")
            if len(w) >= 3 and w not in _STOPWORDS and w not in ordered:
                ordered.append(w)
            if len(ordered) >= 10:
                break
    if len(ordered) < 3:
        for pad in ("ai-agent", "llm", "automation"):
            if pad not in ordered:
                ordered.append(pad)
    return ", ".join(ordered[:10])


def _register_async(agent_id: str, name: str, endpoint: str, capabilities: str) -> None:
    """Fire-and-forget upsert to Beacon on a daemon thread."""
    def _send() -> None:
        try:
            requests.post(
                f"{_CONFIG['registry_url'].rstrip('/')}/api/v1/register",
                json={
                    "agent_id": agent_id,
                    "name": name,
                    "mcp_endpoint": endpoint,
                    "capabilities": capabilities,
                },
                timeout=10,
            )
            logger.info("registered '%s' (%s)", name, agent_id)
        except Exception as exc:  # never propagate
            logger.warning("register failed for '%s': %s", agent_id, exc)

    threading.Thread(target=_send, name=f"beacon-register-{agent_id}", daemon=True).start()


def discover_agents(query: str, limit: int = 5) -> list[dict]:
    """Synchronous discovery call used by the injected tool. Returns [] on error."""
    try:
        resp = requests.post(
            f"{_CONFIG['registry_url'].rstrip('/')}/api/v1/discover",
            json={"query": query, "limit": limit},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception as exc:
        logger.warning("discover failed: %s", exc)
    return []


def _discovery_run(query: str) -> str:
    """Plain callable behind the injected tool; returns an LLM-friendly string."""
    results = discover_agents(query, limit=5)
    if not results:
        return f"No agents found in the Beacon registry for '{query}'."
    lines = [
        f"- {r.get('name')} ({r.get('mcp_endpoint')}) "
        f"[reputation {r.get('success_rate')}, tags: {', '.join(r.get('capabilities_tags', []))}]"
        for r in results
    ]
    return "Agents discovered via Beacon:\n" + "\n".join(lines)


# --------------------------------------------------------------------------- #
# Framework-native tool builders (each guarded — used only if importable)
# --------------------------------------------------------------------------- #

def _build_crewai_tool() -> Optional[Any]:
    try:
        from crewai.tools import BaseTool  # type: ignore
        from pydantic import BaseModel, Field

        class _QuerySchema(BaseModel):
            query: str = Field(..., description="Capability or task to search other agents for")

        class BeaconDiscoveryTool(BaseTool):
            name: str = "beacon_discover"
            description: str = (
                "Discover other AI agents by capability from the Beacon registry. "
                "Input: a short capability/task query. Returns matching agents with reputation."
            )
            args_schema: type[BaseModel] = _QuerySchema

            def _run(self, query: str) -> str:  # type: ignore[override]
                return _discovery_run(query)

        return BeaconDiscoveryTool()
    except Exception as exc:
        logger.debug("crewai tool unavailable: %s", exc)
        return None


def _build_langchain_tool() -> Optional[Any]:
    try:
        from langchain_core.tools import Tool  # type: ignore

        return Tool(
            name="beacon_discover",
            description=(
                "Discover other AI agents by capability from the Beacon registry. "
                "Input should be a short capability/task query string."
            ),
            func=_discovery_run,
        )
    except Exception as exc:
        logger.debug("langchain tool unavailable: %s", exc)
        return None


def _inject_tool(instance: Any, tool: Any) -> None:
    """Append a tool to the instance's tools list if it exposes one."""
    if tool is None:
        return
    try:
        tools = getattr(instance, "tools", None)
        if isinstance(tools, list):
            if not any(getattr(t, "name", None) == getattr(tool, "name", "beacon_discover") for t in tools):
                tools.append(tool)
        elif tools is None and hasattr(instance, "tools"):
            setattr(instance, "tools", [tool])
    except Exception as exc:
        logger.debug("tool injection skipped: %s", exc)


# --------------------------------------------------------------------------- #
# Generic safe monkey-patch
# --------------------------------------------------------------------------- #

def _patch_init(
    cls: type,
    framework: str,
    extract: Callable[[Any], tuple[str, str, str]],
    tool_builder: Optional[Callable[[], Any]],
) -> bool:
    """
    Wrap cls.__init__ so that after the real init runs, we register the agent and
    inject the discovery tool. Idempotent and exception-isolated.
    """
    if getattr(cls, "_beacon_patched", False):
        return False
    original_init = cls.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)  # framework first — never interfere
        try:
            agent_id, name, capabilities = extract(self)
            endpoint = f"framework://{framework}/{agent_id}"
            _register_async(agent_id, name, endpoint, capabilities)
            if _CONFIG["inject_tool"] and tool_builder is not None:
                _inject_tool(self, tool_builder())
        except Exception as exc:  # Beacon problems must never crash the agent
            logger.warning("[%s] auto-inject skipped: %s", framework, exc)

    cls.__init__ = patched_init  # type: ignore[assignment]
    cls._beacon_patched = True   # type: ignore[attr-defined]
    logger.info("patched %s.%s", framework, cls.__name__)
    return True


# --------------------------------------------------------------------------- #
# Per-framework extractors + patchers
# --------------------------------------------------------------------------- #

def _extract_crewai(agent: Any) -> tuple[str, str, str]:
    role = getattr(agent, "role", None) or "crewai-agent"
    goal = getattr(agent, "goal", "")
    backstory = getattr(agent, "backstory", "")
    agent_id = f"crewai/{re.sub(r'[^a-zA-Z0-9_-]+', '-', str(role)).strip('-').lower()}"
    return agent_id, str(role), _derive_capabilities(str(role), str(goal), str(backstory))


def _extract_langchain(executor: Any) -> tuple[str, str, str]:
    name = getattr(executor, "name", None) or executor.__class__.__name__
    tool_names = []
    try:
        tool_names = [getattr(t, "name", "") for t in getattr(executor, "tools", []) or []]
    except Exception:
        pass
    agent_id = f"langchain/{re.sub(r'[^a-zA-Z0-9_-]+', '-', str(name)).strip('-').lower()}"
    return agent_id, str(name), _derive_capabilities(str(name), " ".join(tool_names), "langchain agent")


def _extract_autogen(agent: Any) -> tuple[str, str, str]:
    name = getattr(agent, "name", None) or "autogen-agent"
    system = getattr(agent, "system_message", "") or getattr(agent, "description", "")
    agent_id = f"autogen/{re.sub(r'[^a-zA-Z0-9_-]+', '-', str(name)).strip('-').lower()}"
    return agent_id, str(name), _derive_capabilities(str(name), str(system), "autogen agent")


def _try_patch_crewai() -> None:
    try:
        import crewai  # type: ignore
        _patch_init(crewai.Agent, "crewai", _extract_crewai, _build_crewai_tool)
    except Exception as exc:
        logger.debug("crewai not present: %s", exc)


def _try_patch_langchain() -> None:
    try:
        from langchain.agents import AgentExecutor  # type: ignore
        _patch_init(AgentExecutor, "langchain", _extract_langchain, _build_langchain_tool)
    except Exception as exc:
        logger.debug("langchain not present: %s", exc)


def _try_patch_autogen() -> None:
    try:
        from autogen import ConversableAgent  # type: ignore
        # AutoGen tool-calling differs per version, so we register-only there.
        _patch_init(ConversableAgent, "autogen", _extract_autogen, None)
    except Exception as exc:
        logger.debug("autogen not present: %s", exc)


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #

def enable_beacon_auto_discovery(
    registry_url: str = DEFAULT_REGISTRY_URL,
    inject_tool: bool = True,
) -> None:
    """
    Activate zero-config auto-discovery. Safe to call multiple times; patches only
    the frameworks that are actually importable in the current environment.
    """
    _CONFIG["registry_url"] = registry_url
    _CONFIG["inject_tool"] = inject_tool
    if _CONFIG["enabled"]:
        logger.info("already enabled")
        return
    _CONFIG["enabled"] = True
    logger.info("enabling Beacon auto-discovery -> %s", registry_url)
    _try_patch_crewai()
    _try_patch_langchain()
    _try_patch_autogen()
    logger.info("Beacon auto-discovery active")


# One-liner alias
auto = enable_beacon_auto_discovery
