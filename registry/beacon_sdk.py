"""
Beacon SDK — the discovery & reputation layer for autonomous AI agents.

Google indexes websites so humans can find them. Beacon indexes *agents* so
agents can find each other. Drop this file (or `pip install beacon-agent`) into
any AI-agent codebase — Eliza-style loops, CrewAI, LangChain, or a bare LLM
while-loop — to get:

  * Auto self-discovery: the agent lights its beacon (registers) the moment the
    client is constructed — fire-and-forget, on a background thread.
  * Mandatory telemetry: wrap any unit of work with `@beacon.track_job` or the
    `beacon.job()` context manager and every success/failure updates the agent's
    reputation, without ever blocking or crashing the host agent.
  * Liveness heartbeat: a background thread keeps the agent "online" in results.

Design rules:
  * The SDK MUST NOT break the host agent. Every network call runs on a daemon
    thread and swallows its own errors (logged, never raised).
  * Zero hard dependencies beyond `requests`.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Optional, Union

import requests

logger = logging.getLogger("beacon")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[beacon] %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

DEFAULT_REGISTRY_URL = "https://beacon-registry.onrender.com"


class BeaconClient:
    """
    Lifecycle-aware registry client. Construct it once per agent instance.

    Example:
        beacon = BeaconClient(
            agent_id="my-agent-01",
            name="Research Bot",
            mcp_endpoint="https://my-agent.example.com/mcp",
            capabilities=["research", "web-search", "summarize"],
            registry_url="https://beacon-registry.onrender.com",
        )

        @beacon.track_job
        def do_work(...): ...
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        mcp_endpoint: str,
        capabilities: Union[str, Iterable[str]],
        registry_url: str = DEFAULT_REGISTRY_URL,
        *,
        auto_register: bool = True,
        heartbeat_interval: Optional[float] = 120.0,
        request_timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id is required")
        if not name or not str(name).strip():
            raise ValueError("name is required")
        if not mcp_endpoint or not str(mcp_endpoint).strip():
            raise ValueError("mcp_endpoint is required")

        self.agent_id = str(agent_id).strip()
        self.name = str(name).strip()
        self.mcp_endpoint = str(mcp_endpoint).strip()
        self.capabilities = self._normalize_caps(capabilities)
        self.registry_url = registry_url.rstrip("/")
        self.request_timeout = request_timeout
        self.max_retries = max(1, int(max_retries))
        self.heartbeat_interval = heartbeat_interval

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": f"beacon-sdk/1.0 ({self.agent_id})"})
        self._registered = threading.Event()
        self._stop = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None

        if auto_register:
            self.auto_register()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_caps(capabilities: Union[str, Iterable[str]]) -> str:
        if isinstance(capabilities, str):
            parts = [capabilities]
        else:
            parts = list(capabilities)
        flat: list[str] = []
        for p in parts:
            for tok in str(p).replace(",", " ").split():
                tok = tok.strip().lower()
                if tok and tok not in flat:
                    flat.append(tok)
        return ",".join(flat)

    def _post(self, path: str, payload: dict) -> Optional[dict]:
        """Synchronous POST with bounded retry/backoff. Returns JSON or None."""
        url = f"{self.registry_url}{path}"
        backoff = 0.5
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.post(url, json=payload, timeout=self.request_timeout)
                if resp.status_code < 500:
                    # 2xx/4xx are final; only 5xx/network warrant a retry.
                    try:
                        return resp.json()
                    except ValueError:
                        return {"ok": resp.ok, "status_code": resp.status_code}
                logger.warning("%s -> HTTP %s (attempt %d)", path, resp.status_code, attempt)
            except requests.RequestException as exc:
                logger.warning("%s failed: %s (attempt %d)", path, exc, attempt)
            if attempt < self.max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
        return None

    def _spawn(self, fn: Callable[[], Any], name: str) -> None:
        threading.Thread(target=fn, name=name, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Registration + heartbeat
    # ------------------------------------------------------------------ #

    def auto_register(self) -> None:
        """Light the beacon: fire the registration handshake on a daemon thread."""
        self._spawn(self._do_register, f"beacon-register-{self.agent_id}")

    def _do_register(self) -> None:
        payload = {
            "agent_id": self.agent_id,
            "name": self.name,
            "mcp_endpoint": self.mcp_endpoint,
            "capabilities": self.capabilities,
        }
        result = self._post("/api/v1/register", payload)
        if result and result.get("ok"):
            self._registered.set()
            logger.info("beacon lit for '%s' (%s)", self.name, result.get("status"))
            if self.heartbeat_interval and self._hb_thread is None:
                self._hb_thread = threading.Thread(
                    target=self._heartbeat_loop, name="beacon-heartbeat", daemon=True
                )
                self._hb_thread.start()
        else:
            logger.warning("registration for '%s' did not confirm; will retry on next job", self.agent_id)

    def _heartbeat_loop(self) -> None:
        interval = float(self.heartbeat_interval or 120.0)
        while not self._stop.wait(interval):
            # A telemetry ping with no counter change would distort stats, so
            # heartbeat re-registers (which only refreshes last_seen).
            self._post("/api/v1/register", {
                "agent_id": self.agent_id,
                "name": self.name,
                "mcp_endpoint": self.mcp_endpoint,
                "capabilities": self.capabilities,
            })

    def wait_until_registered(self, timeout: float = 10.0) -> bool:
        """Block until the initial registration confirms (mostly for tests)."""
        return self._registered.wait(timeout)

    # ------------------------------------------------------------------ #
    # Telemetry
    # ------------------------------------------------------------------ #

    def report(self, job_status: str) -> None:
        """Fire-and-forget telemetry. Never blocks the caller."""
        status = "success" if str(job_status).strip().lower() in {
            "success", "succeeded", "ok", "pass", "passed", "true", "1"
        } else "fail"

        def _send() -> None:
            # If we somehow never registered, self-heal first.
            if not self._registered.is_set():
                self._do_register()
            self._post("/api/v1/telemetry", {"agent_id": self.agent_id, "job_status": status})

        self._spawn(_send, f"beacon-telemetry-{self.agent_id}")

    def track_job(self, job_function: Callable) -> Callable:
        """
        Decorator: run the wrapped function, report success/fail telemetry, and
        re-raise the original exception so the host agent's control flow is
        exactly as it would have been without the SDK.
        """
        @functools.wraps(job_function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = job_function(*args, **kwargs)
            except Exception:
                self.report("fail")
                raise
            self.report("success")
            return result

        return wrapper

    @contextmanager
    def job(self):
        """
        Context manager alternative to the decorator:

            with beacon.job():
                risky_step()
        """
        try:
            yield self
        except Exception:
            self.report("fail")
            raise
        else:
            self.report("success")

    # ------------------------------------------------------------------ #
    # Discovery (agents finding other agents)
    # ------------------------------------------------------------------ #

    def discover(self, query: str, limit: int = 10, online_only: bool = False) -> list[dict]:
        """Synchronous capability search. Returns [] on any failure."""
        result = self._post(
            "/api/v1/discover",
            {"query": query, "limit": limit, "online_only": online_only},
        )
        if result and result.get("ok"):
            return result.get("results", [])
        return []

    # ------------------------------------------------------------------ #
    # Teardown
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        self._stop.set()
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self) -> "BeaconClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# Backwards-friendly alias in case a developer imports the descriptive name.
BeaconDiscoveryPlugin = BeaconClient
