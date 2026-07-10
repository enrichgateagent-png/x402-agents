import { Hono } from "hono";
import { paymentMiddleware, type Network, type RoutesConfig } from "x402-hono";
import { vatCheck, leiLookup } from "./checks.js";

try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;

const CATALOG = [
  {
    path: "/vat",
    price: "$0.01",
    description:
      "Validate an EU VAT number against the official VIES registry — returns validity, registered legal name, and address. POST { countryCode: 'DE', vatNumber: '...' }.",
  },
  {
    path: "/lei",
    price: "$0.005",
    description:
      "Look up legal entities in the official GLEIF LEI registry by name or LEI code — returns LEI, legal name, jurisdiction, status, and registered address. POST { name?: string, lei?: string }.",
  },
] as const;

export const app = new Hono();

app.get("/", (c) =>
  c.json({
    name: "compliance-check",
    description:
      "KYB primitives for agents, straight from authoritative registries: EU VAT validation (VIES) and legal entity lookup (GLEIF LEI). Pay per check in USDC via x402 — no accounts, no API keys.",
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

app.post("/vat", async (c) => {
  const { countryCode, vatNumber } = await c.req.json().catch(() => ({}));
  if (typeof countryCode !== "string" || countryCode.length !== 2 || typeof vatNumber !== "string" || !vatNumber) {
    return c.json({ error: "Body must be { countryCode: 'DE', vatNumber: string }" }, 400);
  }
  return c.json(await vatCheck(countryCode, vatNumber));
});

app.post("/lei", async (c) => {
  const { name, lei, limit } = await c.req.json().catch(() => ({}));
  if ((!name || typeof name !== "string") && (!lei || typeof lei !== "string")) {
    return c.json({ error: "Body must include { name: string } or { lei: string }" }, 400);
  }
  return c.json(await leiLookup({ name, lei }, Math.min(Number(limit) || 5, 10)));
});

app.onError((err, c) => c.json({ error: err.message }, 502));

export default app;
