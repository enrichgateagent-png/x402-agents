// Free, keyless upstream feeds normalized for agents:
// news (Google News RSS), FX rates (Frankfurter/ECB), geocoding (Nominatim/OSM).

async function getText(url: string, headers: Record<string, string> = {}) {
  const res = await fetch(url, { signal: AbortSignal.timeout(12000), headers });
  if (!res.ok) throw new Error(`Upstream ${new URL(url).hostname} returned ${res.status}`);
  return res.text();
}

// --- News: Google News RSS (topic search or top stories) ---
export interface Headline { title: string; url: string; source?: string; publishedAt?: string }

export async function news(topic?: string, limit = 15): Promise<{ headlines: Headline[] }> {
  const feed = topic
    ? `https://news.google.com/rss/search?q=${encodeURIComponent(topic)}&hl=en-US&gl=US&ceid=US:en`
    : "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en";
  const xml = await getText(feed);
  const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].slice(0, limit);
  const pick = (block: string, tag: string) =>
    block.match(new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?<\\/${tag}>`))?.[1]?.trim();
  const headlines = items.map(([, block]) => ({
    title: pick(block, "title") ?? "",
    url: pick(block, "link") ?? "",
    source: pick(block, "source"),
    publishedAt: pick(block, "pubDate"),
  }));
  return { headlines };
}

// --- FX: Frankfurter (ECB reference rates, free, no key) ---
export async function fx(base = "USD", symbols?: string): Promise<{ base: string; date: string; rates: Record<string, number> }> {
  const url = `https://api.frankfurter.dev/v1/latest?base=${encodeURIComponent(base)}${symbols ? `&symbols=${encodeURIComponent(symbols)}` : ""}`;
  const data = JSON.parse(await getText(url));
  if (!data.rates) throw new Error("Unknown base currency");
  return { base: data.base, date: data.date, rates: data.rates };
}

// --- Geocoding: OpenStreetMap Nominatim (usage policy: identify app, low volume) ---
export interface Place { name: string; lat: number; lon: number; type?: string; importance?: number }

export async function geocode(query: string, limit = 5): Promise<{ results: Place[] }> {
  const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=${limit}&q=${encodeURIComponent(query)}`;
  const data = JSON.parse(await getText(url, { "user-agent": "data-feed-x402/0.1 (contact: enrichgateagent@gmail.com)" }));
  return {
    results: data.map((p: any) => ({
      name: p.display_name,
      lat: Number(p.lat),
      lon: Number(p.lon),
      type: p.type,
      importance: p.importance,
    })),
  };
}
