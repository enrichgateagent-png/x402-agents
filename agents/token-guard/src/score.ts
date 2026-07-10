// Aggregates free security/liquidity sources into a single 0-100 risk score.
// All upstreams are keyless free APIs, so every paid call is pure margin.

const CHAIN_IDS: Record<string, string> = {
  ethereum: "1",
  bsc: "56",
  polygon: "137",
  base: "8453",
  arbitrum: "42161",
};

// Honeypot.is only simulates on these chains
const HONEYPOT_CHAINS = new Set(["ethereum", "bsc", "base"]);

export const SUPPORTED_CHAINS = Object.keys(CHAIN_IDS);

export interface RiskFlag {
  id: string;
  severity: "high" | "medium" | "low";
  detail: string;
}

export interface TokenReport {
  chain: string;
  address: string;
  name?: string;
  symbol?: string;
  riskScore: number; // 0 safest — 100 worst
  verdict: "low-risk" | "caution" | "high-risk" | "likely-scam";
  flags: RiskFlag[];
  liquidityUsd?: number;
  volume24hUsd?: number;
  priceUsd?: string;
  sources: string[];
}

async function getJson(url: string, timeoutMs = 8000): Promise<any | null> {
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(timeoutMs),
      headers: { accept: "application/json" },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function buildReport(chain: string, address: string): Promise<TokenReport> {
  const chainId = CHAIN_IDS[chain];
  const addr = address.toLowerCase();

  const [goplus, dex, honeypot] = await Promise.all([
    getJson(`https://api.gopluslabs.io/api/v1/token_security/${chainId}?contract_addresses=${addr}`),
    getJson(`https://api.dexscreener.com/latest/dex/tokens/${addr}`),
    HONEYPOT_CHAINS.has(chain)
      ? getJson(`https://api.honeypot.is/v2/IsHoneypot?address=${addr}&chain=${chain === "ethereum" ? "eth" : chain}`)
      : Promise.resolve(null),
  ]);

  const flags: RiskFlag[] = [];
  const sources: string[] = [];
  let score = 0;

  // --- GoPlus contract security flags ---
  const gp = goplus?.result?.[addr];
  if (gp) {
    sources.push("goplus");
    const truthy = (v: unknown) => v === "1";
    if (truthy(gp.is_honeypot)) {
      score += 60;
      flags.push({ id: "honeypot", severity: "high", detail: "GoPlus flags token as honeypot (cannot sell)" });
    }
    if (truthy(gp.hidden_owner)) {
      score += 20;
      flags.push({ id: "hidden-owner", severity: "high", detail: "Contract has a hidden owner" });
    }
    if (truthy(gp.can_take_back_ownership)) {
      score += 15;
      flags.push({ id: "reclaimable-ownership", severity: "high", detail: "Ownership can be taken back after renounce" });
    }
    if (truthy(gp.is_mintable)) {
      score += 10;
      flags.push({ id: "mintable", severity: "medium", detail: "Supply can be inflated by owner" });
    }
    if (truthy(gp.transfer_pausable)) {
      score += 10;
      flags.push({ id: "pausable", severity: "medium", detail: "Transfers can be paused by owner" });
    }
    if (truthy(gp.is_blacklisted)) {
      score += 8;
      flags.push({ id: "blacklist", severity: "medium", detail: "Owner can blacklist addresses" });
    }
    if (truthy(gp.is_proxy)) {
      score += 5;
      flags.push({ id: "proxy", severity: "low", detail: "Upgradeable proxy contract — logic can change" });
    }
    if (truthy(gp.is_open_source) === false && gp.is_open_source !== undefined) {
      score += 12;
      flags.push({ id: "unverified-source", severity: "medium", detail: "Contract source not verified" });
    }
    const buyTax = parseFloat(gp.buy_tax ?? "0");
    const sellTax = parseFloat(gp.sell_tax ?? "0");
    if (sellTax >= 0.2 || buyTax >= 0.2) {
      score += 20;
      flags.push({ id: "extreme-tax", severity: "high", detail: `Buy/sell tax ${(buyTax * 100).toFixed(0)}%/${(sellTax * 100).toFixed(0)}%` });
    } else if (sellTax >= 0.1 || buyTax >= 0.1) {
      score += 8;
      flags.push({ id: "high-tax", severity: "medium", detail: `Buy/sell tax ${(buyTax * 100).toFixed(0)}%/${(sellTax * 100).toFixed(0)}%` });
    }
  }

  // --- Honeypot.is simulation ---
  if (honeypot) {
    sources.push("honeypot.is");
    if (honeypot.honeypotResult?.isHoneypot) {
      score += 60;
      flags.push({ id: "honeypot-sim", severity: "high", detail: "Sell simulation failed — honeypot confirmed by simulation" });
    }
  }

  // --- DexScreener liquidity / market data ---
  let liquidityUsd: number | undefined;
  let volume24hUsd: number | undefined;
  let priceUsd: string | undefined;
  let name: string | undefined;
  let symbol: string | undefined;
  const pairs: any[] = dex?.pairs?.filter((p: any) => p.chainId === chain) ?? dex?.pairs ?? [];
  if (dex) sources.push("dexscreener");
  if (pairs.length > 0) {
    const best = pairs.reduce((a, b) => ((a.liquidity?.usd ?? 0) >= (b.liquidity?.usd ?? 0) ? a : b));
    liquidityUsd = best.liquidity?.usd;
    volume24hUsd = best.volume?.h24;
    priceUsd = best.priceUsd;
    name = best.baseToken?.name;
    symbol = best.baseToken?.symbol;
    if ((liquidityUsd ?? 0) < 5_000) {
      score += 15;
      flags.push({ id: "thin-liquidity", severity: "high", detail: `Only $${Math.round(liquidityUsd ?? 0)} liquidity — exit may be impossible` });
    } else if ((liquidityUsd ?? 0) < 50_000) {
      score += 6;
      flags.push({ id: "low-liquidity", severity: "medium", detail: `$${Math.round(liquidityUsd ?? 0)} liquidity` });
    }
  } else {
    score += 10;
    flags.push({ id: "no-dex-listing", severity: "medium", detail: "No DEX pairs found" });
  }

  if (sources.length === 0) {
    throw new Error("All upstream data sources unavailable for this token");
  }

  const riskScore = Math.min(100, score);
  const verdict =
    riskScore >= 70 ? "likely-scam" : riskScore >= 40 ? "high-risk" : riskScore >= 15 ? "caution" : "low-risk";

  return { chain, address: addr, name, symbol, riskScore, verdict, flags, liquidityUsd, volume24hUsd, priceUsd, sources };
}
