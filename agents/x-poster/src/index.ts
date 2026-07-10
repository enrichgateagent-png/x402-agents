// The agent's voice: reads its own onchain revenue, composes a tweet, posts it.
// DRY_RUN=1 (or missing X keys) prints instead of posting.
// Usage: npx tsx src/index.ts [daily|launch]

import { TwitterApi } from "twitter-api-v2";
import { getEarnings } from "./earnings.js";
import { composeDaily, composeLaunch } from "./compose.js";

try {
  process.loadEnvFile(new URL("../.env", import.meta.url).pathname);
} catch {}

const SELLER = (process.env.SELLER_ADDRESS ?? "0xfAE3B355Dce282768Da52ECD43c861927222fD30") as `0x${string}`;
const MODE = process.argv[2] ?? "daily";

const keys = {
  appKey: process.env.X_API_KEY,
  appSecret: process.env.X_API_SECRET,
  accessToken: process.env.X_ACCESS_TOKEN,
  accessSecret: process.env.X_ACCESS_SECRET,
};
const canPost = !process.env.DRY_RUN && Object.values(keys).every(Boolean);

async function send(tweets: string[]) {
  if (!canPost) {
    console.log(`--- DRY RUN (${canPost ? "" : "X keys missing or DRY_RUN set"}) ---`);
    tweets.forEach((t, i) => console.log(`\n[tweet ${i + 1}] (${t.length} chars)\n${t}`));
    return;
  }
  const client = new TwitterApi(keys as Required<typeof keys> & { appKey: string; appSecret: string; accessToken: string; accessSecret: string });
  let replyTo: string | undefined;
  for (const text of tweets) {
    const res = await client.v2.tweet(replyTo ? { text, reply: { in_reply_to_tweet_id: replyTo } } : { text });
    console.log(`posted: https://x.com/i/status/${res.data.id}`);
    replyTo = res.data.id;
  }
}

if (MODE === "launch") {
  await send(composeLaunch());
} else {
  const report = await getEarnings(SELLER, Number(process.env.SINCE_HOURS ?? 24));
  await send([composeDaily(report, SELLER)]);
}
