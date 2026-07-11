#!/usr/bin/env python3
"""
multi_source_crawler.py — expand Beacon beyond GitHub toward "the index".

Crawls npm, Hugging Face (Spaces + models), and PyPI for AI-agent / MCP / tool
packages and registers them into Beacon via the public POST /api/v1/register.
Fully decoupled from the backend (it only hits the public API), so it can run
anywhere and never touches server code.

Being cross-ecosystem — GitHub + npm + PyPI + Hugging Face — is what makes Beacon
genuinely more comprehensive than any single-source competitor.

Env:
  REGISTRY_URL    Beacon base (default https://registry-ruby.vercel.app)
  MAX_PER_QUERY   cap per search query per source (default 120)
  SOURCES         comma list: npm,hf,pypi (default all)
  SLEEP           seconds between register writes (default 0.1)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout)
log = logging.getLogger("beacon-multicrawl")

REGISTRY = os.environ.get("REGISTRY_URL", "https://registry-ruby.vercel.app").rstrip("/")
REGISTER = f"{REGISTRY}/api/v1/register"
MAX_PER_QUERY = int(os.environ.get("MAX_PER_QUERY", "120"))
SOURCES = set((os.environ.get("SOURCES", "npm,hf,pypi")).split(","))
SLEEP = float(os.environ.get("SLEEP", "0.1"))
TIMEOUT = 25

_UA = {"User-Agent": "beacon-multicrawler/1.0"}
# Only index genuinely agent-relevant packages (npm/pypi search is noisy).
_RELEVANT = ("mcp", "agent", "ai-agent", "aiagent", "llm", "langchain", "langgraph",
             "crewai", "autogen", "eliza", "autonomous", "gpt", "assistant", "rag",
             "openai", "anthropic", "model-context")
_STOP = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "by",
         "is", "are", "be", "this", "that", "it", "as", "from", "your", "you", "using",
         "use", "server", "package", "library", "python", "node", "js", "typescript",
         "simple", "easy", "based", "via", "api", "tool", "tools", "app"}
_WORD = re.compile(r"[a-z0-9][a-z0-9\-]{1,}")


def _get_json(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        import json
        return json.load(r)


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _norm_caps(*parts) -> str:
    toks: list[str] = []
    for p in parts:
        if isinstance(p, (list, tuple)):
            for t in p:
                t = str(t).strip().lower()
                if t and t not in toks:
                    toks.append(t)
        else:
            for w in _WORD.findall(str(p or "").lower()):
                if len(w) >= 3 and w not in _STOP and w not in toks:
                    toks.append(w)
        if len(toks) >= 10:
            break
    return ", ".join(toks[:10])


def _relevant(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _RELEVANT)


def _register(agent_id: str, name: str, endpoint: str, caps: str) -> bool:
    import json
    payload = json.dumps({
        "agent_id": agent_id, "name": name[:256], "mcp_endpoint": endpoint,
        "capabilities": caps, "source": "scraper",
    }).encode()
    req = urllib.request.Request(REGISTER, data=payload,
                                 headers={**_UA, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status == 200
    except Exception as e:
        log.warning("register failed %s: %s", agent_id, e)
        return False


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #

NPM_QUERIES = ["mcp server", "mcp", "ai agent", "langchain", "crewai", "autogen",
               "eliza plugin", "ai-agent", "llm agent", "model context protocol"]
HF_QUERIES = ["agent", "mcp", "langchain", "autonomous agent", "ai agent", "crewai"]
PYPI_QUERIES = ["mcp", "ai agent", "langchain", "crewai", "autogen", "llm agent", "autonomous agent"]


def crawl_npm(seen: set) -> int:
    n = 0
    for q in NPM_QUERIES:
        frm = 0
        got = 0
        while got < MAX_PER_QUERY:
            try:
                url = (f"https://registry.npmjs.org/-/v1/search?"
                       f"text={urllib.parse.quote(q)}&size=100&from={frm}")
                objs = _get_json(url).get("objects", [])
            except Exception as e:
                log.warning("[npm] %s: %s", q, e); break
            if not objs:
                break
            for o in objs:
                p = o.get("package", {})
                name = p.get("name", "")
                if not name:
                    continue
                aid = f"npm/{name}"
                if aid in seen:
                    continue
                kw = p.get("keywords", []) or []
                desc = p.get("description", "") or ""
                if not _relevant(name + " " + " ".join(kw) + " " + desc):
                    continue
                seen.add(aid)
                repo = (((p.get("links") or {}).get("repository")) or
                        f"https://www.npmjs.com/package/{name}")
                caps = _norm_caps(kw, desc, "npm")
                if _register(aid, name.split("/")[-1], repo, caps):
                    n += 1
                got += 1
                time.sleep(SLEEP)
                if got >= MAX_PER_QUERY:
                    break
            frm += len(objs)
            if len(objs) < 100:
                break
        log.info("[npm] '%s' done (running total %d)", q, n)
    return n


def crawl_hf(seen: set) -> int:
    n = 0
    for kind in ("spaces", "models"):
        for q in HF_QUERIES:
            try:
                url = (f"https://huggingface.co/api/{kind}?"
                       f"search={urllib.parse.quote(q)}&limit={MAX_PER_QUERY}")
                items = _get_json(url)
            except Exception as e:
                log.warning("[hf/%s] %s: %s", kind, q, e); continue
            for it in items:
                hid = it.get("id", "")
                if not hid:
                    continue
                aid = f"hf/{kind}/{hid}"
                if aid in seen:
                    continue
                tags = it.get("tags", []) or []
                if not _relevant(hid + " " + " ".join(map(str, tags))):
                    continue
                seen.add(aid)
                endpoint = f"https://huggingface.co/{'spaces/' if kind=='spaces' else ''}{hid}"
                caps = _norm_caps(tags, hid.replace("/", " "), "huggingface")
                if _register(aid, hid.split("/")[-1], endpoint, caps):
                    n += 1
                time.sleep(SLEEP)
            log.info("[hf/%s] '%s' done (running total %d)", kind, q, n)
    return n


_PYPI_LINK = re.compile(r'<a class="package-snippet" href="/project/([^/]+)/">')
_PYPI_DESC = re.compile(r'<p class="package-snippet__description">([^<]*)</p>')


def crawl_pypi(seen: set) -> int:
    n = 0
    for q in PYPI_QUERIES:
        for page in range(1, 4):  # PyPI paginates; a few pages per query
            try:
                html = _get_text(f"https://pypi.org/search/?q={urllib.parse.quote(q)}&page={page}")
            except Exception as e:
                log.warning("[pypi] %s p%d: %s", q, page, e); break
            names = _PYPI_LINK.findall(html)
            descs = _PYPI_DESC.findall(html)
            if not names:
                break
            for i, name in enumerate(names):
                aid = f"pypi/{name}"
                if aid in seen:
                    continue
                desc = descs[i] if i < len(descs) else ""
                if not _relevant(name + " " + desc):
                    continue
                seen.add(aid)
                caps = _norm_caps(desc, name.replace("-", " "), "pypi")
                if _register(aid, name, f"https://pypi.org/project/{name}", caps):
                    n += 1
                time.sleep(SLEEP)
            time.sleep(0.5)
        log.info("[pypi] '%s' done (running total %d)", q, n)
    return n


def main() -> None:
    log.info("multi-source crawl -> %s (sources: %s)", REGISTER, ",".join(sorted(SOURCES)))
    seen: set = set()
    totals = {}
    if "npm" in SOURCES:
        totals["npm"] = crawl_npm(seen)
    if "hf" in SOURCES:
        totals["hf"] = crawl_hf(seen)
    if "pypi" in SOURCES:
        totals["pypi"] = crawl_pypi(seen)
    log.info("DONE — registered: %s (total %d)", totals, sum(totals.values()))


if __name__ == "__main__":
    main()
