"""
Programmatic SEO — dynamic /discover/* landing pages, sitemap.xml, robots.txt.

Each page lists real agents from the live index (not thin doorway pages), with
keyword-targeted titles, an intro, internal links to related pages (crawl + link
equity), and an FAQ block emitting FAQPage JSON-LD for rich results.
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from typing import Callable, Optional

PER_PAGE = 24
MIN_AGENTS = 5
YEAR = datetime.now(timezone.utc).year

PORTAL_URL = os.environ.get("PORTAL_URL", "https://portal-five-phi-54.vercel.app").rstrip("/")


def _caps() -> list[tuple[str, str]]:
    """Curated high-intent slugs: capabilities, frameworks, and framework×capability
    combos. Any slug resolves to a live search, so breadth = organic surface area."""
    caps: list[tuple[str, str]] = [
        # capabilities (what people actually search)
        ("web-scraping", "web scraping"), ("pdf-extraction", "pdf extraction"),
        ("browser-automation", "browser automation"), ("rag", "rag retrieval"),
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
        ("multi-agent", "multi agent orchestration"), ("finance", "finance analysis"),
        ("chatbot", "chatbot"), ("code-generation", "code generation"),
        ("documentation", "documentation"), ("transcription", "transcription"),
        ("text-to-speech", "text to speech"), ("speech-to-text", "speech to text"),
        ("sentiment-analysis", "sentiment analysis"), ("lead-generation", "lead generation"),
        ("seo", "seo"), ("copywriting", "copywriting"), ("resume", "resume builder"),
        ("recruiting", "recruiting"), ("legal", "legal assistant"), ("medical", "medical assistant"),
        ("real-estate", "real estate"), ("e-commerce", "ecommerce"), ("invoice", "invoice processing"),
        ("recommendation", "recommendation engine"), ("forecasting", "forecasting"),
        ("anomaly-detection", "anomaly detection"), ("fraud-detection", "fraud detection"),
        ("moderation", "content moderation"), ("embeddings", "embeddings"),
        ("fine-tuning", "fine tuning"), ("prompt-engineering", "prompt engineering"),
        ("evaluation", "llm evaluation"), ("observability", "agent observability"),
        ("guardrails", "guardrails"), ("memory", "agent memory"),
        ("semantic-search", "semantic search"), ("knowledge-graph", "knowledge graph"),
        ("etl", "data pipeline etl"), ("web-crawler", "web crawler"),
        ("monitoring", "monitoring"), ("devops", "devops automation"),
        ("kubernetes", "kubernetes"), ("aws", "aws automation"),
        ("notion", "notion"), ("slack", "slack bot"), ("gmail", "gmail"),
        ("jira", "jira"), ("shopify", "shopify"), ("stripe", "stripe"),
        ("stock-analysis", "stock analysis"), ("options-trading", "options trading"),
        ("crypto-trading", "crypto trading"), ("nft", "nft"), ("ethereum", "ethereum agent"),
        ("video-generation", "video generation"), ("music-generation", "music generation"),
        ("game", "game agent"), ("tutoring", "tutoring"), ("data-extraction", "data extraction"),
        ("form-filling", "form filling"), ("captcha", "captcha"), ("api-testing", "api testing"),
        ("data-labeling", "data labeling"), ("synthetic-data", "synthetic data"),
    ]
    # framework hubs
    frameworks = [
        ("mcp-server", "mcp server"), ("langchain", "langchain"), ("langgraph", "langgraph"),
        ("crewai", "crewai"), ("autogen", "autogen"), ("llamaindex", "llamaindex"),
        ("elizaos", "elizaos"), ("semantic-kernel", "semantic kernel"), ("n8n", "n8n"),
        ("smolagents", "smolagents"), ("pydantic-ai", "pydantic ai"),
        ("openai-agents", "openai agents"), ("dspy", "dspy"), ("agno", "agno"),
        ("autogpt", "autogpt"), ("haystack", "haystack"),
    ]
    # framework × top capability combos (high-intent long-tail)
    combo_caps = [("rag", "rag"), ("web-scraping", "web scraping"), ("agent", "agent"),
                  ("chatbot", "chatbot"), ("research", "research"), ("automation", "automation"),
                  ("mcp", "mcp")]
    combos: list[tuple[str, str]] = []
    for fslug, flabel in frameworks:
        for cslug, clabel in combo_caps:
            combos.append((f"{fslug}-{cslug}", f"{flabel} {clabel}"))
    return caps + frameworks + combos


CAPABILITIES: list[tuple[str, str]] = _caps()
_SLUG_TO_LABEL = dict(CAPABILITIES)
_ALL_SLUGS = [s for s, _ in CAPABILITIES]


def label_for_slug(slug: str) -> str:
    return _SLUG_TO_LABEL.get(slug, slug.replace("-", " "))


def _related(slug: str, n: int = 12) -> list[tuple[str, str]]:
    """Deterministic window of other slugs — connects the link graph so Google
    crawls every page and link equity flows between them."""
    if slug in _SLUG_TO_LABEL:
        i = _ALL_SLUGS.index(slug)
    else:
        i = abs(hash(slug)) % len(_ALL_SLUGS)
    out = []
    for k in range(1, n + 1):
        s = _ALL_SLUGS[(i + k) % len(_ALL_SLUGS)]
        out.append((s, _SLUG_TO_LABEL[s]))
    return out


def page_html(slug: str, label: str, agents: list[dict], total: int) -> str:
    e = html.escape
    n = len(agents)
    title = f"Best {label.title()} AI Agents ({YEAR}) — {n}+ open-source | Beacon"
    desc = (
        f"The best open-source {label} AI agents, ranked by real maintenance health "
        f"(freshness + GitHub stars + activity). {n} actively-maintained options from "
        f"a free index of {total:,}+ agents. No API key."
    )
    top_names = [a.get("name", "") for a in agents[:3] if a.get("name")]
    top_str = ", ".join(top_names) if top_names else f"open-source {label} agents"

    faqs = [
        (f"What is the best open-source {label} agent?",
         f"Top-ranked {label} agents on Beacon include {top_str}, ranked by maintenance "
         f"health — recent activity, GitHub stars, and open-issue load — not stars alone."),
        (f"Are these {label} agents free to use?",
         f"Yes. Every {label} agent listed is open-source and free. Beacon is a free "
         f"directory — no API key or signup to browse or search."),
        (f"How do I use a {label} agent from my editor or AI assistant?",
         f"Run 'npx -y beacon-mcp' to add Beacon as an MCP server in Cursor, Claude "
         f"Desktop, Cline, or Windsurf, then ask your AI to find a {label} agent."),
    ]

    items = [{
        "@type": "ListItem", "position": i + 1,
        "item": {"@type": "SoftwareSourceCode", "name": a.get("name"),
                 "codeRepository": a.get("mcp_endpoint"), "url": a.get("mcp_endpoint"),
                 "keywords": ", ".join((a.get("capabilities_tags") or [])[:8])},
    } for i, a in enumerate(agents)]
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "description": desc,
         "url": f"{PORTAL_URL}/discover/{slug}"},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Beacon", "item": PORTAL_URL},
            {"@type": "ListItem", "position": 2, "name": f"{label.title()} agents",
             "item": f"{PORTAL_URL}/discover/{slug}"}]},
        {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]}

    cards = "\n".join(
        f'''<article class="card">
  <div class="row"><a class="name" href="{e(a.get("mcp_endpoint",""))}" rel="nofollow noopener" target="_blank">{e(a.get("name",""))}</a>
  <span class="stars">★ {int(a.get("stars",0) or 0):,}</span></div>
  <div class="tags">{"".join(f'<span class="tag">{e(t)}</span>' for t in (a.get("capabilities_tags") or [])[:5])}</div>
</article>''' for a in agents)

    related_html = " · ".join(
        f'<a href="{PORTAL_URL}/discover/{rs}">{e(rl.title())}</a>' for rs, rl in _related(slug))
    faq_html = "\n".join(
        f'<div class="faq"><h3>{e(q)}</h3><p>{e(a)}</p></div>' for q, a in faqs)

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
h1{{color:#fff;font-size:2rem;margin:0 0 6px}} h2{{color:#fff;font-size:1.3rem;margin:34px 0 12px}}
h3{{color:#e2e8f0;font-size:1rem;margin:0 0 4px}} .sub{{color:#64748b;margin:0 0 18px}}
.intro{{color:#94a3b8;margin:0 0 20px}}
.card{{border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);border-radius:14px;padding:14px 16px;margin-bottom:10px}}
.row{{display:flex;justify-content:space-between;gap:10px;align-items:center}}
.name{{font-weight:600;color:#fff}} .stars{{color:#fbbf24;font-size:.85rem;white-space:nowrap}}
.tags{{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}}
.tag{{font-size:.72rem;background:rgba(99,102,241,.1);color:#a5b4fc;border:1px solid rgba(99,102,241,.2);border-radius:6px;padding:2px 8px}}
.cta{{display:inline-block;margin:8px 0 8px;background:linear-gradient(100deg,#6366f1,#8b5cf6);color:#fff;padding:10px 18px;border-radius:12px;font-weight:600}}
.faq{{border-top:1px solid rgba(255,255,255,.06);padding:14px 0}}
.related{{color:#64748b;font-size:.9rem;line-height:2}}
code{{background:#14141f;border:1px solid rgba(255,255,255,.1);padding:2px 8px;border-radius:6px;color:#a5b4fc}}
footer{{margin-top:40px;color:#475569;font-size:.85rem}}
</style></head><body><div class="wrap">
<p><a href="{PORTAL_URL}">← Beacon</a> · open-source AI agent registry</p>
<h1>Best {e(label.title())} AI agents</h1>
<p class="sub">{n} actively-maintained {e(label)} agents · ranked by maintenance health · {total:,}+ indexed</p>
<p class="intro">Looking for the best open-source {e(label)} AI agent? Beacon indexes {total:,}+ agents and MCP servers from GitHub and ranks them by real maintenance health — freshness, stars, and activity — so abandoned repos don't top the list. Below are {n} {e(label)} agents you can install today, free and with no API key.</p>
<a class="cta" href="{PORTAL_URL}/?q={e(slug)}">Search all {e(label)} agents →</a>
<p>Use from your editor: <code>npx -y beacon-mcp</code> then ask your AI to find a {e(label)} agent.</p>
<h2>Top {n} {e(label)} agents</h2>
{cards}
<h2>Frequently asked questions</h2>
{faq_html}
<h2>Related searches</h2>
<p class="related">{related_html}</p>
<footer>Part of <a href="{PORTAL_URL}">Beacon</a> — {total:,}+ open-source AI agents indexed from GitHub, ranked by health not hype.</footer>
</div></body></html>"""


def thin_page(slug: str, label: str, total: int) -> str:
    e = html.escape
    related_html = " · ".join(
        f'<a href="{PORTAL_URL}/discover/{rs}" style="color:#a5b4fc">{e(rl.title())}</a>'
        for rs, rl in _related(slug, 8))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="robots" content="noindex,follow">
<title>{e(label.title())} AI Agents | Beacon</title>
</head><body style="font-family:system-ui;background:#08080c;color:#cbd5e1;padding:40px">
<p><a href="{PORTAL_URL}" style="color:#a5b4fc">← Beacon</a></p>
<h1>{e(label.title())} agents</h1>
<p>Not enough listings yet for a dedicated page. <a href="{PORTAL_URL}/?q={e(slug)}" style="color:#a5b4fc">Search the full index</a> ({total:,}+ agents).</p>
<p style="color:#64748b">Related: {related_html}</p>
</body></html>"""


def sitemap_xml(slugs: Optional[list[str]] = None) -> str:
    slugs = slugs or _ALL_SLUGS
    urls = [f"{PORTAL_URL}/"] + [f"{PORTAL_URL}/discover/{s}" for s in slugs]
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
        + "\n</urlset>"
    )
    return body


def robots_txt() -> str:
    return "User-agent: *\nAllow: /\n\n" + f"Sitemap: {PORTAL_URL}/sitemap.xml\n"


def build_discover_page(
    slug: str,
    search_fn: Callable[[str, int], list[dict]],
    total_agents: int,
) -> tuple[str, int, bool]:
    """Returns (html, agent_count, indexable). indexable=False for thin pages."""
    label = label_for_slug(slug)
    agents = search_fn(label, PER_PAGE)
    if len(agents) < MIN_AGENTS:
        return thin_page(slug, label, total_agents), len(agents), False
    return page_html(slug, label, agents, total_agents), len(agents), True
