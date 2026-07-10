import { Hono } from "hono";
import { paymentMiddleware, type Network, type RoutesConfig } from "x402-hono";
import { news, fx, geocode } from "./feeds.js";

try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;

const CATALOG = [
  {
    path: "/news",
    price: "$0.002",
    description: "Live news headlines. POST { topic?: string, limit?: number } → { headlines: [{title,url,source,publishedAt}] }. Omit topic for top stories.",
  },
  {
    path: "/fx",
    price: "$0.001",
    description: "Daily FX reference rates (ECB). POST { base?: string, symbols?: string } → { base, date, rates }. e.g. { base: 'USD', symbols: 'EUR,PKR,GBP' }.",
  },
  {
    path: "/geocode",
    price: "$0.002",
    description: "Geocode any place name or address to coordinates (OpenStreetMap). POST { query: string, limit?: number } → { results: [{name,lat,lon}] }.",
  },
] as const;

export const app = new Hono();

app.get("/", (c) =>
  c.json({
    name: "data-feed",
    description:
      "The boring data every agent needs, per call: live news headlines, FX rates, geocoding. Sub-cent prices, USDC on Base via x402. No accounts, no API keys.",
    payment: PAY_TO ? { protocol: "x402", network: NETWORK } : { mode: "free (no PAY_TO configured)" },
    endpoints: Object.fromEntries(CATALOG.map((e) => [`POST ${e.path}`, { price: e.price, description: e.description }])),
  })
);

if (PAY_TO) {
  const routes: RoutesConfig = Object.fromEntries(
    CATALOG.map((e) => [e.path, { price: e.price, network: NETWORK, config: { description: e.description } }])
  );
  const useCdp = !!(process.env.CDP_API_KEY_ID && process.env.CDP_API_KEY_SECRET);
  const facilitatorConfig = (useCdp
    ? (await import("@coinbase/x402")).facilitator
    : { url: "https://x402.org/facilitator" }) as Parameters<typeof paymentMiddleware>[2];
  console.log(`facilitator: ${useCdp ? "Coinbase CDP (Bazaar-discoverable)" : "x402.org (testnet)"}`);
  app.use(paymentMiddleware(PAY_TO, routes, facilitatorConfig));
} else {
  console.warn("PAY_TO not set — running in FREE mode (no paywall).");
}

app.post("/news", async (c) => {
  const { topic, limit } = await c.req.json().catch(() => ({}));
  if (topic !== undefined && (typeof topic !== "string" || topic.length > 200)) {
    return c.json({ error: "topic must be a string under 200 chars" }, 400);
  }
  return c.json(await news(topic, Math.min(Number(limit) || 15, 30)));
});

app.post("/fx", async (c) => {
  const { base, symbols } = await c.req.json().catch(() => ({}));
  return c.json(await fx(typeof base === "string" ? base.toUpperCase() : "USD", typeof symbols === "string" ? symbols.toUpperCase() : undefined));
});

app.post("/geocode", async (c) => {
  const { query, limit } = await c.req.json().catch(() => ({}));
  if (!query || typeof query !== "string") return c.json({ error: "Body must be { query: string }" }, 400);
  return c.json(await geocode(query, Math.min(Number(limit) || 5, 10)));
});

app.onError((err, c) => c.json({ error: err.message }, 502));

export default app;
