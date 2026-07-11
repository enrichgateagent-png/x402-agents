#!/usr/bin/env python3
"""
generate_seo.py — programmatic SEO pages for Beacon (white-hat).

Generates one indexable landing page per high-value capability, each with REAL
agent listings pulled live from the registry + schema.org JSON-LD. Also emits
sitemap.xml and robots.txt. Pages are genuinely unique (real, different results
per capability) — not thin doorway pages.

Run:  python generate_seo.py   (writes into ./discover/, ./sitemap.xml, ./robots.txt)
Re-run any time (e.g. daily via CI) to keep listings fresh.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import urllib.parse
import urllib.request

# Live GCP backend (via the portal's /api rewrite). SQLite on a Compute Engine VM.
API = os.environ.get("BEACON_API", "https://portal-five-phi-54.vercel.app/api/v1").rstrip("/")
PORTAL = os.environ.get("PORTAL_URL", "https://portal-five-phi-54.vercel.app").rstrip("/")
OUT = pathlib.Path(__file__).parent
PER_PAGE = 24

# Curated high-value capabilities people actually search for. Each becomes
# /discover/<slug>. Kept to a focused set so every page has real depth.
CAPABILITIES = [
    ("web-scraping", "web scraping"), ("pdf-extraction", "pdf extraction"),
    ("browser-automation", "browser automation"), ("mcp-server", "mcp server"),
    ("crewai", "crewai"), ("langchain", "langchain"), ("langgraph", "langgraph"),
    ("elizaos", "elizaos"), ("autogen", "autogen"), ("rag", "rag retrieval"),
    ("trading-bot", "trading bot"), ("code-review", "code review"),
    ("data-analysis", "data analysis"), ("image-generation", "image generation"),
    ("voice-agent", "voice agent"), ("sql-agent", "sql database agent"),
    ("github-automation", "github automation"), ("discord-bot", "discord bot"),
    ("telegram-bot", "telegram bot"), ("email-automation", "email automation"),
    ("research-assistant", "research assistant"), ("customer-support", "customer support"),
    ("content-writing", "content writing"), ("translation", "translation"),
    ("ocr", "ocr document"), ("knowledge-base", "knowledge base"),
    ("vector-database", "vector database"), ("workflow-automation", "workflow automation"),
    ("api-integration", "api integration"), ("testing", "test automation"),
    ("security-audit", "security audit"), ("blockchain", "blockchain agent"),
    ("solana", "solana agent"), ("defi", "defi trading"),
    ("twitter-agent", "twitter social media"), ("scheduling", "calendar scheduling"),
    ("summarization", "summarization"), ("web-search", "web search"),
    ("multi-agent", "multi-agent orchestration"), ("finance", "finance analysis"),
]


def discover(query: str) -> list[dict]:
    """GET /search?q= on the live GCP backend."""
    url = f"{API}/search?q={urllib.parse.quote(query)}&limit={PER_PAGE}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r).get("results", [])
    except Exception as e:
        print(f"  ! {query}: {e}")
        return []


def total_count() -> int:
    try:
        with urllib.request.urlopen(f"{API}/health", timeout=20) as r:
            return int(json.load(r).get("total_agents", 0))
    except Exception:
        return 18000


def page_html(slug: str, label: str, agents: list[dict], total: int) -> str:
    e = html.escape
    title = f"{label.title()} AI Agents — {len(agents)}+ open-source options | Beacon"
    desc = (f"Browse {len(agents)} open-source {label} AI agents, ranked by GitHub "
            f"traction and maintenance. Free directory of {total:,}+ agents. Search on Beacon.")
    # schema.org ItemList of the real agents on this page
    items = [{
        "@type": "ListItem", "position": i + 1,
        "item": {
            "@type": "SoftwareSourceCode",
            "name": a.get("name"),
            "codeRepository": a.get("mcp_endpoint"),
            "url": a.get("mcp_endpoint"),
            "keywords": ", ".join(a.get("capabilities_tags", [])[:8]),
        },
    } for i, a in enumerate(agents)]
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "name": title, "description": desc,
             "url": f"{PORTAL}/discover/{slug}"},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Beacon", "item": PORTAL},
                {"@type": "ListItem", "position": 2, "name": f"{label.title()} agents",
                 "item": f"{PORTAL}/discover/{slug}"}]},
            {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
        ],
    }
    cards = "\n".join(
        f'''<article class="card">
  <div class="row"><a class="name" href="{e(a.get("mcp_endpoint",""))}" rel="nofollow noopener" target="_blank">{e(a.get("name",""))}</a>
  <span class="stars">★ {a.get("stars",0):,}</span></div>
  <div class="tags">{"".join(f'<span class="tag">{e(t)}</span>' for t in a.get("capabilities_tags",[])[:5])}</div>
</article>''' for a in agents)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{PORTAL}/discover/{slug}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{PORTAL}/discover/{slug}"><meta name="robots" content="index,follow">
<script type="application/ld+json">{json.dumps(jsonld)}</script>
<style>
:root{{color-scheme:dark}}
body{{margin:0;background:#08080c;color:#cbd5e1;font-family:Inter,system-ui,sans-serif;line-height:1.6}}
.wrap{{max-width:900px;margin:0 auto;padding:40px 20px 80px}}
a{{color:#a5b4fc;text-decoration:none}} a:hover{{color:#c7d2fe}}
h1{{color:#fff;font-size:2rem;margin:0 0 6px}} .sub{{color:#64748b;margin:0 0 28px}}
.card{{border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);border-radius:14px;padding:14px 16px;margin-bottom:10px}}
.row{{display:flex;justify-content:space-between;gap:10px;align-items:center}}
.name{{font-weight:600;color:#fff}} .stars{{color:#fbbf24;font-size:.85rem;white-space:nowrap}}
.tags{{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}}
.tag{{font-size:.72rem;background:rgba(99,102,241,.1);color:#a5b4fc;border:1px solid rgba(99,102,241,.2);border-radius:6px;padding:2px 8px}}
.cta{{display:inline-block;margin:8px 0 28px;background:linear-gradient(100deg,#6366f1,#8b5cf6);color:#fff;padding:10px 18px;border-radius:12px;font-weight:600}}
code{{background:#14141f;border:1px solid rgba(255,255,255,.1);padding:2px 8px;border-radius:6px;color:#a5b4fc}}
footer{{margin-top:40px;color:#475569;font-size:.85rem}}
</style></head><body><div class="wrap">
<p><a href="{PORTAL}">← Beacon</a> · the search engine for AI agents</p>
<h1>{e(label.title())} AI agents</h1>
<p class="sub">{len(agents)} open-source {e(label)} agents from a live index of {total:,}+, ranked by GitHub traction.</p>
<a class="cta" href="{PORTAL}/?q={e(slug)}">Search all {label} agents →</a>
<p>Use these from your editor: <code>npx -y beacon-mcp</code> then ask your AI to “find a {e(label)} agent”.</p>
{cards}
<footer>Part of <a href="{PORTAL}">Beacon</a> — {total:,}+ open-source AI agents indexed from GitHub. Data refreshed continuously.</footer>
</div></body></html>"""


def main() -> None:
    total = total_count()
    (OUT / "discover").mkdir(exist_ok=True)
    urls = [f"{PORTAL}/"]
    print(f"generating SEO pages ({total:,} agents indexed)...")
    for slug, label in CAPABILITIES:
        agents = discover(label)
        if len(agents) < 5:   # skip thin pages — Google penalizes low-value doorway pages
            print(f"  · skip /discover/{slug} (only {len(agents)} — too thin)")
            continue
        d = OUT / "discover" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_html(slug, label, agents, total), encoding="utf-8")
        urls.append(f"{PORTAL}/discover/{slug}")
        print(f"  ✓ /discover/{slug} ({len(agents)} agents)")

    # sitemap.xml
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"  <url><loc>{u}</loc><changefreq>daily</changefreq></url>")
    sm.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    # robots.txt — welcome search + LLM crawlers, point to sitemap
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {PORTAL}/sitemap.xml\n", encoding="utf-8")

    print(f"done: {len(urls)-1} pages + sitemap.xml + robots.txt")


if __name__ == "__main__":
    main()
