// Beacon's own X voice. Pulls live registry stats and posts an update thread.
// DRY_RUN=1 prints instead of posting.  Usage: npx tsx src/index.ts [launch|stats]
import { TwitterApi } from "twitter-api-v2";

process.loadEnvFile(new URL("../.env", import.meta.url).pathname);

const REGISTRY = (process.env.REGISTRY_URL ?? "http://34.45.7.252:8000").replace(/\/$/, "");
const PORTAL = process.env.PORTAL_URL ?? "https://portal-five-phi-54.vercel.app";
const MODE = process.argv[2] ?? "launch";

const keys = {
  appKey: process.env.X_API_KEY!,
  appSecret: process.env.X_API_SECRET!,
  accessToken: process.env.X_ACCESS_TOKEN!,
  accessSecret: process.env.X_ACCESS_SECRET!,
};
const canPost = !process.env.DRY_RUN && Object.values(keys).every(Boolean);

async function stats() {
  const r = await fetch(`${REGISTRY}/api/v1/leaderboard?limit=5`);
  const d = await r.json();
  const top = (d.leaderboard || [])
    .filter((a: any) => a.stars > 0)
    .slice(0, 3)
    .map((a: any) => `${a.name} (★${a.stars.toLocaleString()})`);
  return { total: d.total_count as number, top };
}

function threadLaunch(total: number, top: string[]): string[] {
  return [
    `Introducing Beacon — the discovery registry for AI agents.\n\nGoogle indexes websites so humans can find them. Beacon indexes agents so agents can find each other.\n\n${total.toLocaleString()}+ open-source AI agents indexed and searchable by capability. 🧵`,
    `Every agent gets a portable, telemetry-backed reputation — and a real-time fraud engine flags & quarantines malicious nodes automatically.\n\nDiscovery filters them out; the portal shows a red FRAUD WARNING. Trust, built in.`,
    `One line makes any CrewAI / LangChain / Eliza agent self-register + gain cross-agent discovery. There's a LangChain tool + MCP too.\n\nAnd a live SVG badge for your README that updates with your reputation.`,
    `Browse the whole live index — search by capability, watch the network feed, see the leaderboard ranked by real traction:\n\n${PORTAL}`,
  ];
}

function threadStats(total: number, top: string[]): string {
  const lead = top.length ? `\n\nMost-starred right now: ${top.join(", ")}.` : "";
  return `Beacon now indexes ${total.toLocaleString()}+ AI agents, searchable by capability with reputation + fraud defense built in.${lead}\n\nExplore: ${PORTAL}`;
}

async function send(tweets: string[]) {
  for (const [i, t] of tweets.entries()) {
    if (t.length > 280) throw new Error(`tweet ${i + 1} too long: ${t.length}`);
  }
  if (!canPost) {
    console.log(`--- DRY RUN (${process.env.DRY_RUN ? "DRY_RUN set" : "missing keys"}) ---`);
    tweets.forEach((t, i) => console.log(`\n[${i + 1}/${tweets.length}] (${t.length} chars)\n${t}`));
    return;
  }
  const client = new TwitterApi(keys);
  let replyTo: string | undefined;
  for (const text of tweets) {
    const res = await client.v2.tweet(replyTo ? { text, reply: { in_reply_to_tweet_id: replyTo } } : { text });
    console.log(`posted: https://x.com/Enrichagent/status/${res.data.id}`);
    replyTo = res.data.id;
  }
}

const { total, top } = await stats();
await send(MODE === "stats" ? [threadStats(total, top)] : threadLaunch(total, top));
