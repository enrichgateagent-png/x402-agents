// Upstream provider adapters. Each returns normalized JSON so buyers get one
// consistent shape regardless of provider. Routes only mount when the key is set.

async function post(url: string, headers: Record<string, string>, body: unknown, timeoutMs = 20000) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`Upstream ${new URL(url).hostname} returned ${res.status}`);
  return res.json();
}

export interface SearchResult {
  title: string;
  url: string;
  snippet?: string;
}

// Serper.dev — Google SERP
export async function serperSearch(apiKey: string, query: string, num = 10): Promise<{ results: SearchResult[] }> {
  const data: any = await post("https://google.serper.dev/search", { "X-API-KEY": apiKey }, { q: query, num });
  const results: SearchResult[] = (data.organic ?? []).map((r: any) => ({
    title: r.title,
    url: r.link,
    snippet: r.snippet,
  }));
  return { results };
}

// Exa — neural web search
export async function exaSearch(apiKey: string, query: string, num = 10): Promise<{ results: SearchResult[] }> {
  const data: any = await post(
    "https://api.exa.ai/search",
    { "x-api-key": apiKey },
    { query, numResults: num, contents: { text: { maxCharacters: 500 } } }
  );
  const results: SearchResult[] = (data.results ?? []).map((r: any) => ({
    title: r.title,
    url: r.url,
    snippet: r.text,
  }));
  return { results };
}

// Cloudflare Workers AI — LLM inference (llama-3-8b)
export async function workersAi(
  accountId: string,
  apiToken: string,
  prompt: string,
  system?: string
): Promise<{ response: string; model: string }> {
  const model = process.env.CF_AI_MODEL ?? "@cf/meta/llama-3.1-8b-instruct-fp8";
  const messages = [
    ...(system ? [{ role: "system", content: system }] : []),
    { role: "user", content: prompt },
  ];
  const data: any = await post(
    `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run/${model}`,
    { authorization: `Bearer ${apiToken}` },
    { messages },
    30000
  );
  if (!data.success) throw new Error(data.errors?.[0]?.message ?? "Workers AI call failed");
  return { response: data.result?.response ?? "", model };
}

// Firecrawl — URL → clean markdown
export async function firecrawlScrape(apiKey: string, url: string): Promise<{ url: string; markdown: string; title?: string }> {
  const data: any = await post(
    "https://api.firecrawl.dev/v1/scrape",
    { authorization: `Bearer ${apiKey}` },
    { url, formats: ["markdown"] }
  );
  if (!data.success) throw new Error(data.error ?? "Firecrawl scrape failed");
  return { url, markdown: data.data?.markdown ?? "", title: data.data?.metadata?.title };
}
