// The research pipeline: buys search/scrape/inference from enrich-gate via
// x402 (agent-to-agent commerce), synthesizes a markdown brief.

import { privateKeyToAccount } from "viem/accounts";
import { wrapFetchWithPayment } from "x402-fetch";

const GATEWAY = (process.env.ENRICH_GATE_URL ?? "https://enrich-gate.vercel.app").replace(/\/$/, "");

function payingFetch(): typeof fetch {
  const pk = process.env.AGENT_PRIVATE_KEY as `0x${string}` | undefined;
  if (!pk) return fetch; // free-mode gateway (local testing)
  return wrapFetchWithPayment(fetch, privateKeyToAccount(pk)) as typeof fetch;
}

async function call<T>(path: string, body: unknown): Promise<T> {
  const res = await payingFetch()(`${GATEWAY}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed (${res.status}): ${(await res.text()).slice(0, 160)}`);
  return res.json() as Promise<T>;
}

interface SearchResult { title: string; url: string; snippet?: string }

export interface Report {
  topic: string;
  markdown: string;
  sources: string[];
  costBreakdown: { calls: number; estUsd: number };
}

export async function research(topic: string): Promise<Report> {
  let calls = 0;
  let estUsd = 0;
  const track = <T>(p: Promise<T>, usd: number) => ((calls++), (estUsd += usd), p);

  // 1. Two search angles in parallel
  const [web, neural] = await Promise.all([
    track(call<{ results: SearchResult[] }>("/search", { query: topic, num: 6 }), 0.01),
    track(call<{ results: SearchResult[] }>("/neural-search", { query: topic, num: 6 }), 0.012),
  ]);

  // 2. Dedupe, pick top 3 URLs, scrape them
  const seen = new Set<string>();
  const urls = [...web.results, ...neural.results]
    .filter((r) => r.url && !seen.has(new URL(r.url).hostname) && seen.add(new URL(r.url).hostname))
    .slice(0, 3)
    .map((r) => r.url);

  const pages = await Promise.allSettled(
    urls.map((url) => track(call<{ url: string; title?: string; markdown: string }>("/scrape", { url }), 0.015))
  );
  const scraped = pages.flatMap((p) => (p.status === "fulfilled" ? [p.value] : []));

  // 3. Synthesize with the gateway's own inference route
  const evidence = [
    ...web.results.slice(0, 6).map((r) => `- ${r.title} (${r.url}): ${r.snippet ?? ""}`),
    ...scraped.map((p) => `\n## Source: ${p.title ?? p.url}\n${p.markdown.slice(0, 2500)}`),
  ].join("\n");

  const synthesis = await track(
    call<{ response: string }>("/ai", {
      system:
        "You are a research analyst. Write a concise, well-structured markdown brief: ## Summary (3-4 sentences), ## Key Findings (bullets), ## Details, ## Caveats. Ground every claim in the provided evidence only. No preamble.",
      prompt: `Topic: ${topic}\n\nEvidence:\n${evidence.slice(0, 6000)}`,
    }),
    0.005
  );

  const sources = [...seen].length ? urls : web.results.slice(0, 3).map((r) => r.url);
  return {
    topic,
    markdown: `# ${topic}\n\n${synthesis.response}\n\n## Sources\n${sources.map((u) => `- ${u}`).join("\n")}`,
    sources,
    costBreakdown: { calls, estUsd: Number(estUsd.toFixed(3)) },
  };
}
