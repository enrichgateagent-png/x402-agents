import { Hono } from "hono";
import { paymentMiddleware, type Network } from "x402-hono";
import { extractDocument } from "./extract.js";

try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const PAY_TO = process.env.PAY_TO as `0x${string}` | undefined;
const NETWORK = (process.env.NETWORK ?? "base-sepolia") as Network;
const PRICE = process.env.PRICE ?? "$0.03";

export const app = new Hono();

app.get("/", (c) =>
  c.json({
    name: "doc-extract",
    description:
      "Documents → structured JSON. POST a URL to any PDF, image, DOCX, or HTML document and get extracted fields (invoice/receipt/contract aware, or bring your own field spec) plus full markdown. Pay per document via x402.",
    payment: PAY_TO ? { protocol: "x402", network: NETWORK, price: PRICE } : { mode: "free (no PAY_TO configured)" },
    endpoints: {
      "POST /extract": {
        price: PRICE,
        body: "{ url: string, fields?: string (describe the fields you want) }",
        returns: "{ fields: object, markdown: string }",
        formats: "pdf, jpg, png, webp, svg, docx, xlsx, html, csv, and more",
      },
    },
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
        "/extract": {
          price: PRICE,
          network: NETWORK,
          config: {
            description:
              "Extract structured JSON from any document URL (PDF, image, DOCX, HTML): invoice/receipt/contract fields by default, or specify your own fields. Also returns full markdown of the document.",
          },
        },
      },
      facilitatorConfig
    )
  );
} else {
  console.warn("PAY_TO not set — running in FREE mode (no paywall).");
}

app.post("/extract", async (c) => {
  const { url, fields } = await c.req.json().catch(() => ({}));
  if (!url || typeof url !== "string" || !/^https?:\/\//.test(url)) {
    return c.json({ error: "Body must be { url: string, fields?: string } with http(s) URL" }, 400);
  }
  if (fields !== undefined && (typeof fields !== "string" || fields.length > 1000)) {
    return c.json({ error: "fields must be a string under 1000 chars" }, 400);
  }
  return c.json(await extractDocument(url, fields));
});

app.onError((err, c) => c.json({ error: err.message }, 502));

export default app;
