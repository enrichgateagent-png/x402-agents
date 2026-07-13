/** Sitemap for Google Search Console — served at /sitemap.xml via vercel.json rewrite */

const PORTAL = "https://portal-five-phi-54.vercel.app";

const SLUGS = [
  "web-scraping", "pdf-extraction", "browser-automation", "rag", "trading-bot", "code-review",
  "data-analysis", "image-generation", "voice-agent", "sql-agent", "github-automation", "discord-bot",
  "telegram-bot", "email-automation", "research-assistant", "customer-support", "content-writing", "translation",
  "ocr", "knowledge-base", "vector-database", "workflow-automation", "api-integration", "testing",
  "security-audit", "blockchain", "solana", "defi", "twitter-agent", "scheduling",
  "summarization", "web-search", "multi-agent", "finance", "chatbot", "code-generation",
  "documentation", "transcription", "text-to-speech", "speech-to-text", "sentiment-analysis", "lead-generation",
  "seo", "copywriting", "resume", "recruiting", "legal", "medical",
  "real-estate", "e-commerce", "invoice", "recommendation", "forecasting", "anomaly-detection",
  "fraud-detection", "moderation", "embeddings", "fine-tuning", "prompt-engineering", "evaluation",
  "observability", "guardrails", "memory", "semantic-search", "knowledge-graph", "etl",
  "web-crawler", "monitoring", "devops", "kubernetes", "aws", "notion",
  "slack", "gmail", "jira", "shopify", "stripe", "stock-analysis",
  "options-trading", "crypto-trading", "nft", "ethereum", "video-generation", "music-generation",
  "game", "tutoring", "data-extraction", "form-filling", "captcha", "api-testing",
  "data-labeling", "synthetic-data", "mcp-server", "langchain", "langgraph", "crewai",
  "autogen", "llamaindex", "elizaos", "semantic-kernel", "n8n", "smolagents",
  "pydantic-ai", "openai-agents", "dspy", "agno", "autogpt", "haystack",
  "mcp-server-rag", "mcp-server-web-scraping", "mcp-server-agent", "mcp-server-chatbot", "mcp-server-research", "mcp-server-automation",
  "mcp-server-mcp", "langchain-rag", "langchain-web-scraping", "langchain-agent", "langchain-chatbot", "langchain-research",
  "langchain-automation", "langchain-mcp", "langgraph-rag", "langgraph-web-scraping", "langgraph-agent", "langgraph-chatbot",
  "langgraph-research", "langgraph-automation", "langgraph-mcp", "crewai-rag", "crewai-web-scraping", "crewai-agent",
  "crewai-chatbot", "crewai-research", "crewai-automation", "crewai-mcp", "autogen-rag", "autogen-web-scraping",
  "autogen-agent", "autogen-chatbot", "autogen-research", "autogen-automation", "autogen-mcp", "llamaindex-rag",
  "llamaindex-web-scraping", "llamaindex-agent", "llamaindex-chatbot", "llamaindex-research", "llamaindex-automation", "llamaindex-mcp",
  "elizaos-rag", "elizaos-web-scraping", "elizaos-agent", "elizaos-chatbot", "elizaos-research", "elizaos-automation",
  "elizaos-mcp", "semantic-kernel-rag", "semantic-kernel-web-scraping", "semantic-kernel-agent", "semantic-kernel-chatbot", "semantic-kernel-research",
  "semantic-kernel-automation", "semantic-kernel-mcp", "n8n-rag", "n8n-web-scraping", "n8n-agent", "n8n-chatbot",
  "n8n-research", "n8n-automation", "n8n-mcp", "smolagents-rag", "smolagents-web-scraping", "smolagents-agent",
  "smolagents-chatbot", "smolagents-research", "smolagents-automation", "smolagents-mcp", "pydantic-ai-rag", "pydantic-ai-web-scraping",
  "pydantic-ai-agent", "pydantic-ai-chatbot", "pydantic-ai-research", "pydantic-ai-automation", "pydantic-ai-mcp", "openai-agents-rag",
  "openai-agents-web-scraping", "openai-agents-agent", "openai-agents-chatbot", "openai-agents-research", "openai-agents-automation", "openai-agents-mcp",
  "dspy-rag", "dspy-web-scraping", "dspy-agent", "dspy-chatbot", "dspy-research", "dspy-automation",
  "dspy-mcp", "agno-rag", "agno-web-scraping", "agno-agent", "agno-chatbot", "agno-research",
  "agno-automation", "agno-mcp", "autogpt-rag", "autogpt-web-scraping", "autogpt-agent", "autogpt-chatbot",
  "autogpt-research", "autogpt-automation", "autogpt-mcp", "haystack-rag", "haystack-web-scraping", "haystack-agent",
  "haystack-chatbot", "haystack-research", "haystack-automation", "haystack-mcp",
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
