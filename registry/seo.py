"""
Programmatic SEO — dynamic /discover/* landing pages, sitemap.xml, robots.txt.

Each page lists real agents from the live index (not thin doorway pages).
"""

from __future__ import annotations

import html
import json
import os
from typing import Callable, Optional

PER_PAGE = 24
MIN_AGENTS = 5

PORTAL_URL = os.environ.get("PORTAL_URL", "https://portal-five-phi-54.vercel.app").rstrip("/")

# Curated high-intent capabilities — synced with portal/generate_seo.py
CAPABILITIES: list[tuple[str, str]] = [
    ("web-scraping", "web scraping"),
    ("pdf-extraction", "pdf extraction"),
    ("browser-automation", "browser automation"),
    ("mcp-server", "mcp server"),
    ("crewai", "crewai"),
    ("langchain", "langchain"),
    ("langgraph", "langgraph"),
    ("elizaos", "elizaos"),
    ("autogen", "autogen"),
    ("rag", "rag retrieval"),
    ("trading-bot", "trading bot"),
    ("code-review", "code review"),
    ("data-analysis", "data analysis"),
    ("image-generation", "image generation"),
    ("voice-agent", "voice agent"),
    ("sql-agent", "sql database agent"),
    ("github-automation", "github automation"),
    ("discord-bot", "discord bot"),
    ("telegram-bot", "telegram bot"),
    ("email-automation", "email automation"),
    ("research-assistant", "research assistant"),
    ("customer-support", "customer support"),
    ("content-writing", "content writing"),
    ("translation", "translation"),
    ("ocr", "ocr document"),
    ("knowledge-base", "knowledge base"),
    ("vector-database", "vector database"),
    ("workflow-automation", "workflow automation"),
    ("api-integration", "api integration"),
    ("testing", "test automation"),
    ("security-audit", "security audit"),
    ("blockchain", "blockchain agent"),
    ("solana", "solana agent"),
    ("defi", "defi trading"),
    ("twitter-agent", "twitter social media"),
    ("scheduling", "calendar scheduling"),
    ("summarization", "summarization"),
    ("web-search", "web search"),
    ("multi-agent", "multi-agent orchestration"),
    ("finance", "finance analysis"),
]

_SLUG_TO_LABEL = dict(CAPABILITIES)


def label_for_slug(slug: str) -> str:
    return _SLUG_TO_LABEL.get(slug, slug.replace("-", " "))


def page_html(slug: str, label: str, agents: list[dict], total: int) -> str:
    e = html.escape
    title = f"{label.title()} AI Agents — {len(agents)}+ open-source options | Beacon"
    desc = (
        f"Browse {len(agents)} open-source {label} AI agents, ranked by GitHub "
        f"traction and maintenance. Free directory of {total:,}+ agents. Search on Beacon."
    )
    items = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "item": {
                "@type": "SoftwareSourceCode",
                "name": a.get("name"),
                "codeRepository": a.get("mcp_endpoint"),
                "url": a.get("mcp_endpoint"),
                "keywords": ", ".join((a.get("capabilities_tags") or [])[:8]),
            },
        }
        for i, a in enumerate(agents)
    ]
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "name": title,
                "description": desc,
                "url": f"{PORTAL_URL}/discover/{slug}",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Beacon", "item": PORTAL_URL},
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": f"{label.title()} agents",
                        "item": f"{PORTAL_URL}/discover/{slug}",
                    },
                ],
            },
            {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
        ],
    }
    cards = "\n".join(
        f'''<article class="card">
  <div class="row"><a class="name" href="{e(a.get("mcp_endpoint", ""))}" rel="nofollow noopener" target="_blank">{e(a.get("name", ""))}</a>
  <span class="stars">★ {int(a.get("stars", 0) or 0):,}</span></div>
  <div class="tags">{"".join(f'<span class="tag">{e(t)}</span>' for t in (a.get("capabilities_tags") or [])[:5])}</div>
</article>'''
        for a in agents
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{PORTAL_URL}/discover/{slug}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{PORTAL_URL}/discover/{slug}"><meta name="robots" content="index,follow">
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
<p><a href="{PORTAL_URL}">← Beacon</a> · open-source agent registry</p>
<h1>{e(label.title())} AI agents</h1>
<p class="sub">{len(agents)} open-source {e(label)} agents from a live index of {total:,}+, ranked by GitHub traction.</p>
<a class="cta" href="{PORTAL_URL}/?q={e(slug)}">Search all {e(label)} agents →</a>
<p>Use from your editor: <code>npx -y beacon-mcp</code> then ask your AI to find a {e(label)} agent.</p>
{cards}
<footer>Part of <a href="{PORTAL_URL}">Beacon</a> — {total:,}+ open-source AI agents indexed from GitHub.</footer>
</div></body></html>"""


def thin_page(slug: str, label: str, total: int) -> str:
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="robots" content="noindex,follow">
<title>{e(label.title())} AI Agents | Beacon</title>
</head><body style="font-family:system-ui;background:#08080c;color:#cbd5e1;padding:40px">
<p><a href="{PORTAL_URL}" style="color:#a5b4fc">← Beacon</a></p>
<h1>{e(label.title())} agents</h1>
<p>Not enough listings yet for a dedicated page. <a href="{PORTAL_URL}/?q={e(slug)}" style="color:#a5b4fc">Search the full index</a> ({total:,}+ agents).</p>
</body></html>"""


def sitemap_xml(slugs: Optional[list[str]] = None) -> str:
    slugs = slugs or [s for s, _ in CAPABILITIES]
    urls = [f"{PORTAL_URL}/"] + [f"{PORTAL_URL}/discover/{s}" for s in slugs]
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
        + "\n</urlset>"
    )
    return body


def robots_txt() -> str:
    return (
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {PORTAL_URL}/sitemap.xml\n"
    )


def build_discover_page(
    slug: str,
    search_fn: Callable[[str, int], list[dict]],
    total_agents: int,
) -> tuple[str, int, bool]:
    """
    Returns (html, agent_count, indexable).
    indexable=False when fewer than MIN_AGENTS results (noindex thin page).
    """
    label = label_for_slug(slug)
    agents = search_fn(label, PER_PAGE)
    if len(agents) < MIN_AGENTS:
        return thin_page(slug, label, total_agents), len(agents), False
    return page_html(slug, label, agents, total_agents), len(agents), True
