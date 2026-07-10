import { Hono } from "hono";
import { paymentMiddleware, type Network, type RoutesConfig } from "x402-hono";
import { serperSearch, exaSearch, firecrawlScrape, workersAi } from "./providers.js";

// Local dev only; on Vercel env vars come from the dashboard
try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;

const KEYS = {
  serper: process.env.SERPER_API_KEY,
  exa: process.env.EXA_API_KEY,
  firecrawl: process.env.FIRECRAWL_API_KEY,
  cfAccount: process.env.CF_ACCOUNT_ID,
  cfToken: process.env.CF_API_TOKEN,
};

// route → price + description; only key-enabled routes are mounted and paywalled
export const CATALOG = [
  {
    path: "/search",
    price: "$0.01",
    enabled: !!KEYS.serper,
    description: "Google web search (Serper-backed). POST { query, num? } → { results: [{title,url,snippet}] }. No API key, no subscription — pay per call.",
  },
  {
    path: "/neural-search",
    price: "$0.012",
    enabled: !!KEYS.exa,
    description: "Semantic/neural web search (Exa-backed). POST { query, num? } → { results: [{title,url,snippet}] }.",
  },
  {
    path: "/scrape",
    price: "$0.015",
    enabled: !!KEYS.firecrawl,
    description: "Scrape any URL to clean markdown (Firecrawl-backed). POST { url } → { url, title, markdown }.",
  },
  {
    path: "/ai",
    price: "$0.005",
    enabled: !!(KEYS.cfAccount && KEYS.cfToken),
    description: "LLM inference (Llama-3.1-8B via Cloudflare Workers AI). POST { prompt, system? } → { response, model }.",
  },
] as const;

export const app = new Hono();

app.get("/", (c) =>
  c.json({
    name: "enrich-gate",
    description:
      "One endpoint, many premium APIs. Web search, neural search, scraping, and inference — pay per request in USDC via x402. No accounts, no API keys, no subscriptions.",
    payment: PAY_TO ? { protocol: "x402", network: NETWORK } : { mode: "free (no PAY_TO configured)" },
    endpoints: Object.fromEntries(
      CATALOG.map((e) => [`POST ${e.path}`, { price: e.price, live: e.enabled, description: e.description }])
    ),
  })
);

if (PAY_TO) {
  const routes: RoutesConfig = Object.fromEntries(
    CATALOG.filter((e) => e.enabled).map((e) => [
      e.path,
      { price: e.price, network: NETWORK, config: { description: e.description } },
    ])
  );
  // CDP facilitator (mainnet + Bazaar discovery) when CDP keys are set,
  // else the free x402.org facilitator (base-sepolia only)
  const useCdp = !!(process.env.CDP_API_KEY_ID && process.env.CDP_API_KEY_SECRET);
  const facilitatorConfig = (useCdp
    ? (await import("@coinbase/x402")).facilitator
    : { url: "https://x402.org/facilitator" }) as Parameters<typeof paymentMiddleware>[2];
  console.log(`facilitator: ${useCdp ? "Coinbase CDP (Bazaar-discoverable)" : "x402.org (testnet)"}`);
  app.use(paymentMiddleware(PAY_TO, routes, facilitatorConfig));
} else {
  console.warn("PAY_TO not set — running in FREE mode (no paywall).");
}

function requireKey(key: string | undefined, provider: string) {
  if (!key) throw Object.assign(new Error(`${provider} route not enabled on this deployment`), { status: 503 });
  return key;
}

app.post("/search", async (c) => {
  const { query, num } = await c.req.json().catch(() => ({}));
  if (!query || typeof query !== "string") return c.json({ error: "Body must be { query: string, num?: number }" }, 400);
  return c.json(await serperSearch(requireKey(KEYS.serper, "search"), query, Math.min(Number(num) || 10, 20)));
});

app.post("/neural-search", async (c) => {
  const { query, num } = await c.req.json().catch(() => ({}));
  if (!query || typeof query !== "string") return c.json({ error: "Body must be { query: string, num?: number }" }, 400);
  return c.json(await exaSearch(requireKey(KEYS.exa, "neural-search"), query, Math.min(Number(num) || 10, 20)));
});

app.post("/scrape", async (c) => {
  const { url } = await c.req.json().catch(() => ({}));
  if (!url || typeof url !== "string" || !/^https?:\/\//.test(url)) {
    return c.json({ error: "Body must be { url: string } with http(s) URL" }, 400);
  }
  return c.json(await firecrawlScrape(requireKey(KEYS.firecrawl, "scrape"), url));
});

app.post("/ai", async (c) => {
  const { prompt, system } = await c.req.json().catch(() => ({}));
  if (!prompt || typeof prompt !== "string") return c.json({ error: "Body must be { prompt: string, system?: string }" }, 400);
  requireKey(KEYS.cfToken, "ai");
  return c.json(await workersAi(KEYS.cfAccount!, KEYS.cfToken!, prompt, system));
});

app.onError((err, c) => {
  const status = (err as any).status ?? 502;
  return c.json({ error: err.message }, status);
});
