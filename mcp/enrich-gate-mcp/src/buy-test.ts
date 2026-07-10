// End-to-end buyer test: pays real USDC on Base to enrich-gate via x402.
// Usage: npx tsx src/buy-test.ts [gateway-url]

import { createPublicClient, http, formatUnits, erc20Abi } from "viem";
import { base } from "viem/chains";
import { privateKeyToAccount } from "viem/accounts";
import { wrapFetchWithPayment } from "x402-fetch";

try {
  process.loadEnvFile(new URL("../../../.buyer.env", import.meta.url).pathname);
} catch {}

const GATEWAY = process.argv[2] ?? "https://enrich-gate.vercel.app";
const USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
const pk = process.env.BUYER_PRIVATE_KEY as `0x${string}`;
if (!pk) throw new Error("BUYER_PRIVATE_KEY missing — check .buyer.env");

const account = privateKeyToAccount(pk);
const client = createPublicClient({ chain: base, transport: http() });

async function usdcBalance(addr: `0x${string}`) {
  const bal = await client.readContract({
    address: USDC_BASE,
    abi: erc20Abi,
    functionName: "balanceOf",
    args: [addr],
  });
  return formatUnits(bal, 6);
}

const payingFetch = wrapFetchWithPayment(fetch, account) as typeof fetch;

async function buy(path: string, body: unknown) {
  const started = Date.now();
  const res = await payingFetch(`${GATEWAY}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  const paymentResponse = res.headers.get("x-payment-response");
  console.log(`\n=== ${path} → HTTP ${res.status} (${Date.now() - started}ms)`);
  if (paymentResponse) {
    const decoded = JSON.parse(Buffer.from(paymentResponse, "base64").toString());
    console.log(`    settled: ${decoded.success} tx: ${decoded.transaction ?? decoded.txHash ?? "?"}`);
  }
  console.log(`    ${text.slice(0, 220).replace(/\n/g, " ")}`);
}

console.log(`buyer: ${account.address}`);
console.log(`USDC balance (Base): $${await usdcBalance(account.address)}`);

await buy("/ai", { prompt: "In one sentence, what is x402?" });
await buy("/search", { query: "x402 bazaar discovery", num: 3 });
await buy("/neural-search", { query: "agent payment protocols", num: 3 });
await buy("/scrape", { url: "https://x402.org" });

console.log(`\nUSDC balance after: $${await usdcBalance(account.address)}`);
console.log(`seller wallet balance: $${await usdcBalance("0xfAE3B355Dce282768Da52ECD43c861927222fD30")}`);
