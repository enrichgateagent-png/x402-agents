# Beacon — Organic Volume Engine (SEO + LLM ingestion)

White-hat programmatic SEO for the live GCP backend (18k+ agents, SQLite on
Compute Engine, portal rewrites `/api/*` → GCP). Two of the three requested tasks
are built; the third is replaced with a version that won't get us banned.

Live API base for all of this: `https://portal-five-phi-54.vercel.app/api/v1`
(GET /search?q=, /discovery, /health, /agents/{id}, /leaderboard).

---

## TASK 1 + 2 — SEO landing pages + sitemap (BUILT)

`portal/generate_seo.py` generates one indexable landing page per high-intent
capability (`/discover/<slug>`), each with:
- REAL agent listings pulled live from `GET /search?q=<capability>` (unique per
  page — not thin doorway pages; pages with <5 results are skipped).
- Full `schema.org` JSON-LD (`CollectionPage` + `BreadcrumbList` + `ItemList` of
  `SoftwareSourceCode`), canonical URL, OG tags, `robots: index,follow`.
- A CTA back to the portal search + the `npx -y beacon-mcp` line.

It also emits `sitemap.xml` (all pages) and `robots.txt` (welcomes crawlers +
points to the sitemap).

Verified against live GCP: generated real pages for web-scraping, mcp-server,
rag, langchain, elizaos, trading-bot, etc. (18,471 agents indexed at run time).

### Deploying it — do it ONE of these two safe ways

**Option A — dynamic FastAPI routes on GCP (recommended, always fresh).**
Add these to your GCP `main.py` (they use your existing `/search` internally, so
no DB coupling). Because the portal already rewrites to GCP, expose `/discover/*`,
`/sitemap.xml`, `/robots.txt` through the same rewrite.

```python
# --- SEO routes (paste into GCP main.py) ---
from fastapi import Response
import html, json

SEO_CAPS = [
    ("web-scraping","web scraping"),("pdf-extraction","pdf extraction"),
    ("browser-automation","browser automation"),("mcp-server","mcp server"),
    ("langchain","langchain"),("langgraph","langgraph"),("elizaos","elizaos"),
    ("rag","rag retrieval"),("trading-bot","trading bot"),("code-review","code review"),
    ("data-analysis","data analysis"),("voice-agent","voice agent"),("sql-agent","sql agent"),
    ("github-automation","github automation"),("discord-bot","discord bot"),
    ("telegram-bot","telegram bot"),("research-assistant","research assistant"),
    ("web-search","web search"),("multi-agent","multi-agent orchestration"),
]
PORTAL = "https://portal-five-phi-54.vercel.app"

def _seo_page(slug, label, agents, total):
    e = html.escape
    items=[{"@type":"ListItem","position":i+1,"item":{"@type":"SoftwareSourceCode",
        "name":a["name"],"codeRepository":a["mcp_endpoint"],"url":a["mcp_endpoint"],
        "keywords":", ".join(a.get("capabilities_tags",[])[:8])}} for i,a in enumerate(agents)]
    ld={"@context":"https://schema.org","@type":"ItemList","numberOfItems":len(items),
        "itemListElement":items,"name":f"{label.title()} AI agents"}
    cards="".join(f'<article><a href="{e(a["mcp_endpoint"])}" rel="nofollow">{e(a["name"])}</a> ★{a.get("stars",0)}</article>' for a in agents)
    return (f'<!doctype html><html lang=en><head><meta charset=utf-8>'
        f'<title>{e(label.title())} AI Agents — Beacon</title>'
        f'<meta name=description content="Browse {len(agents)} open-source {e(label)} AI agents from {total:,}+ indexed. Free.">'
        f'<link rel=canonical href="{PORTAL}/discover/{slug}">'
        f'<script type="application/ld+json">{json.dumps(ld)}</script></head>'
        f'<body><h1>{e(label.title())} AI agents</h1>{cards}'
        f'<p><a href="{PORTAL}/?q={slug}">Search all on Beacon →</a></p></body></html>')

@app.get("/discover/{slug}")
def seo_discover(slug: str) -> Response:
    label = dict(SEO_CAPS).get(slug, slug.replace("-"," "))
    agents = search(label)["results"][:24]   # reuse your /search impl
    total = _health_total()                    # your health count
    return Response(_seo_page(slug, label, agents, total), media_type="text/html")

@app.get("/sitemap.xml")
def sitemap() -> Response:
    urls = [f"{PORTAL}/"] + [f"{PORTAL}/discover/{s}" for s,_ in SEO_CAPS]
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(f"<url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
            + "</urlset>")
    return Response(body, media_type="application/xml")

@app.get("/robots.txt")
def robots() -> Response:
    return Response(f"User-agent: *\nAllow: /\n\nSitemap: {PORTAL}/sitemap.xml\n", media_type="text/plain")
```
Then ensure the portal's `vercel.json` rewrites `/discover/:path*`, `/sitemap.xml`,
and `/robots.txt` to GCP (same as `/api/*`).

**Option B — static pages.** Run `python portal/generate_seo.py` and deploy the
resulting `discover/`, `sitemap.xml`, `robots.txt` to the portal — **but preserve
your current `index.html` (`const API=""`) and `vercel.json` rewrites**, or you'll
break the GCP consolidation. (This is why the automated deploy was NOT run.)

### After deploy
Submit `https://portal-five-phi-54.vercel.app/sitemap.xml` in Google Search
Console. Indexing takes days–weeks; SEO is a slow compounding channel, not
"immediate volume."

---

## TASK 3 — milestone notifications: NOT built as requested (would get us banned)

The request was to auto-send notifications **to other people's GitHub repos** when
they hit a milestone, to pull their community to Beacon. That is automated
unsolicited messaging to thousands of repos = **GitHub Acceptable-Use spam** →
the `enrichgateagent-png` account gets banned and Beacon gets branded as spam.
Same reason we didn't build the mass-PR bot. I won't build the auto-send.

### The legitimate version (attract, don't spam)
Detect milestones internally and surface them **on our own surfaces** so people
come to us:
- A `GET /api/v1/growth/trending` feed (we already have the pattern) that lists
  agents which just crossed a star threshold or had a big push — recomputed by the
  enrichment cron (it already fetches stars/pushed_at).
- A "🔥 Trending this week" strip on the portal, and a weekly trending post from
  @Enrichagent ("Fastest-growing open-source agents this week, indexed by Beacon:
  …"). That tags the maintainers *in public, opt-in* content — they engage because
  it flatters them, and it's shareable — with zero spam and zero ban risk.

If you want, I can add the trending detection to the enrichment worker + a portal
strip. That's the real "pull developers back" mechanism.
