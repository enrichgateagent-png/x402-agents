import { Hono } from "hono";
import { paymentMiddleware, type Network } from "x402-hono";
import { research } from "./research.js";

try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;
const PRICE = process.env.PRICE ?? "$0.25";

export const app = new Hono();

app.get("/", (c) =>
  c.json({
    name: "deep-report",
    description:
      "Finished research briefs, not raw data. POST a topic, get a grounded markdown report with sources. The agent buys its own search/scrape/inference from enrich-gate via x402 — agent-to-agent commerce all the way down.",
    payment: PAY_TO ? { protocol: "x402", network: NETWORK, price: PRICE } : { mode: "free (no PAY_TO configured)" },
    endpoints: { "POST /report": { price: PRICE, body: "{ topic: string }", returns: "{ topic, markdown, sources[] }" } },
  })
);

if (PAY_TO) {
  const useCdp = !!(process.env.CDP_API_KEY_ID && process.env.CDP_API_KEY_SECRET);
  const facilitatorConfig = (useCdp
    ? (await import("@coinbase/x402")).facilitator
    : { url: "https://x402.org/facilitator" }) as Parameters<typeof paymentMiddleware>[2];
  console.log(`facilitator: ${useCdp ? "Coinbase CDP (Bazaar-discoverable)" : "x402.org (testnet)"}`);
  app.use(
    paymentMiddleware(
      PAY_TO,
      {
        "/report": {
          price: PRICE,
          network: NETWORK,
          config: {
            description:
              "Research-any-topic brief: multi-angle web search + page scraping + grounded synthesis, returned as markdown with sources. One call, finished deliverable.",
          },
        },
      },
      facilitatorConfig
    )
  );
} else {
  console.warn("PAY_TO not set — running in FREE mode (no paywall).");
}

app.post("/report", async (c) => {
  const { topic } = await c.req.json().catch(() => ({}));
  if (!topic || typeof topic !== "string" || topic.length < 3 || topic.length > 300) {
    return c.json({ error: "Body must be { topic: string } (3-300 chars)" }, 400);
  }
  return c.json(await research(topic));
});

app.onError((err, c) => c.json({ error: err.message }, 502));

export default app;
