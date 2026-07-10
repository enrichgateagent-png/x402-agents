import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { paymentMiddleware, type Network } from "x402-hono";
import { buildReport, SUPPORTED_CHAINS } from "./score.js";

const PORT = Number(process.env.PORT ?? 4021);
const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;
const PRICE = process.env.PRICE ?? "$0.005";

const app = new Hono();

// Free discovery endpoint — describes the service to agents and humans
app.get("/", (c) =>
  c.json({
    name: "token-guard",
    description:
      "Token safety / rug-check scoring. Aggregates GoPlus contract security, Honeypot.is sell simulation, and DexScreener liquidity into a 0-100 risk score with structured flags.",
    payment: PAY_TO ? { protocol: "x402", network: NETWORK, price: PRICE } : { mode: "free (no PAY_TO configured)" },
    endpoints: {
      "GET /check/{chain}/{address}": {
        chains: SUPPORTED_CHAINS,
        returns: "TokenReport { riskScore: 0-100, verdict, flags[], liquidityUsd, sources[] }",
      },
    },
  })
);

if (PAY_TO) {
  app.use(
    paymentMiddleware(
      PAY_TO,
      {
        "/check/*": {
          price: PRICE,
          network: NETWORK,
          config: {
            description:
              "Rug-check a token: 0-100 risk score from contract security flags (honeypot, hidden owner, mintable, taxes), sell simulation, and DEX liquidity depth.",
            outputSchema: {
              type: "object",
              properties: {
                riskScore: { type: "number", description: "0 safest - 100 worst" },
                verdict: { type: "string", enum: ["low-risk", "caution", "high-risk", "likely-scam"] },
                flags: { type: "array" },
                liquidityUsd: { type: "number" },
              },
            },
          },
        },
      },
      { url: "https://x402.org/facilitator" }
    )
  );
} else {
  console.warn("PAY_TO not set — running in FREE mode (no paywall). Set PAY_TO to enable x402 payments.");
}

app.get("/check/:chain/:address", async (c) => {
  const chain = c.req.param("chain").toLowerCase();
  const address = c.req.param("address");
  if (!SUPPORTED_CHAINS.includes(chain)) {
    return c.json({ error: `Unsupported chain '${chain}'. Supported: ${SUPPORTED_CHAINS.join(", ")}` }, 400);
  }
  if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
    return c.json({ error: "Invalid EVM token address" }, 400);
  }
  try {
    return c.json(await buildReport(chain, address));
  } catch (err) {
    return c.json({ error: err instanceof Error ? err.message : "Upstream failure" }, 502);
  }
});

serve({ fetch: app.fetch, port: PORT }, (info) => {
  console.log(`token-guard listening on http://localhost:${info.port} (network: ${NETWORK}, price: ${PRICE})`);
});
