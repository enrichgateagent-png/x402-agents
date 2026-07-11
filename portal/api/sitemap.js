/** Sitemap for Google Search Console — served at /sitemap.xml via vercel.json rewrite */

const PORTAL = "https://portal-five-phi-54.vercel.app";

const SLUGS = [
  "web-scraping", "pdf-extraction", "browser-automation", "mcp-server", "crewai",
  "langchain", "langgraph", "elizaos", "autogen", "rag", "trading-bot", "code-review",
  "data-analysis", "image-generation", "voice-agent", "sql-agent", "github-automation",
  "discord-bot", "telegram-bot", "email-automation", "research-assistant",
  "customer-support", "content-writing", "translation", "ocr", "knowledge-base",
  "vector-database", "workflow-automation", "api-integration", "testing",
  "security-audit", "blockchain", "solana", "defi", "twitter-agent", "scheduling",
  "summarization", "web-search", "multi-agent", "finance",
];

function buildSitemap() {
  const urls = [PORTAL + "/"].concat(SLUGS.map((s) => `${PORTAL}/discover/${s}`));
  const entries = urls
    .map(
      (loc) =>
        `  <url><loc>${loc}</loc><lastmod>${new Date().toISOString().slice(0, 10)}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>`
    )
    .join("\n");
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    entries +
    "\n</urlset>\n"
  );
}

export default function handler(req, res) {
  const body = buildSitemap();
  res.setHeader("Content-Type", "text/xml; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600, s-maxage=3600");
  res.status(200).send(body);
}
