import { getRedis, KEYS } from "./redis.js";

export const BOT_BUCKETS = [
  "Glama",
  "Claude/Anthropic",
  "OpenAI",
  "PythonScrapers",
  "ScriptClients",
  "Human",
  "UnknownBots",
];

const ZSET_UA = "beacon:stats:top_ua";
const ZSET_IP = "beacon:stats:top_ip";
const PREFIX_BOT = "beacon:stats:bot:";
const KEY_HUMAN_VISITS = "beacon:stats:human_visits";
const KEY_BOT_VISITS = "beacon:stats:bot_visits";
const KEY_HUMAN_API = "beacon:stats:human_api_hits";
const KEY_BOT_API = "beacon:stats:bot_api_hits";

export function clientIp(req) {
  const xf = req.headers["x-forwarded-for"] || req.headers["x-real-ip"] || "";
  const ip = String(xf).split(",")[0].trim();
  return ip || "unknown";
}

export function classifyClient(ua, event) {
  const u = (ua || "").toLowerCase();

  if (u.includes("glama")) return "Glama";
  if (u.includes("claudebot") || u.includes("anthropic")) return "Claude/Anthropic";
  if (u.includes("gptbot") || u.includes("oai-searchbot") || u.includes("chatgpt-user")) {
    return "OpenAI";
  }
  if (
    u.includes("python-requests") ||
    u.includes("httpx") ||
    u.includes("aiohttp") ||
    u.includes("urllib")
  ) {
    return "PythonScrapers";
  }
  if (
    u.includes("axios") ||
    u.includes("node") ||
    u.includes("undici") ||
    u.includes("curl") ||
    u.includes("wget") ||
    u.includes("go-http")
  ) {
    return "ScriptClients";
  }
  if (u.includes("bot") || u.includes("crawler") || u.includes("spider") || u.includes("scan")) {
    return "UnknownBots";
  }
  if (
    event === "visit" ||
    u.includes("mozilla") ||
    u.includes("chrome") ||
    u.includes("safari") ||
    u.includes("firefox") ||
    u.includes("edg/")
  ) {
    return "Human";
  }
  return "UnknownBots";
}

function uaLabel(ua) {
  const s = String(ua || "unknown").slice(0, 200);
  return s || "unknown";
}

export async function recordEvent(event, req) {
  const client = getRedis();
  if (!client) {
    return { ok: false, error: "redis_not_configured" };
  }

  const metricKey = KEYS[event];
  if (!metricKey) {
    return { ok: false, error: "invalid_event" };
  }

  const ua = req.headers["user-agent"] || "unknown";
  const ip = clientIp(req);
  const category = classifyClient(ua, event);
  const uaKey = uaLabel(ua);

  const pipe = client.pipeline();
  pipe.incr(metricKey);
  pipe.incr(`${PREFIX_BOT}${category}`);
  pipe.zincrby(ZSET_UA, 1, uaKey);
  pipe.zincrby(ZSET_IP, 1, ip);

  if (event === "visit") {
    if (category === "Human") pipe.incr(KEY_HUMAN_VISITS);
    else pipe.incr(KEY_BOT_VISITS);
  }
  if (event === "api_hit") {
    if (category === "Human") pipe.incr(KEY_HUMAN_API);
    else pipe.incr(KEY_BOT_API);
  }

  const results = await pipe.exec();
  const total = Number(results?.[0]) || 0;

  return { ok: true, event, total, category, ip: ip.slice(0, 8) + "…" };
}

export async function getPublicStats() {
  const client = getRedis();
  if (!client) {
    return { ok: true, configured: false, visits: 0, api_hits: 0, installs: 0 };
  }

  const [visits, api_hits, installs] = await client.mget(
    KEYS.visits,
    KEYS.api_hits,
    KEYS.installs,
  );

  return {
    ok: true,
    configured: true,
    visits: Number(visits) || 0,
    api_hits: Number(api_hits) || 0,
    installs: Number(installs) || 0,
  };
}

async function topFromZset(client, key, limit = 15) {
  const rows = await client.zrange(key, 0, limit - 1, { rev: true, withScores: true });
  if (!rows?.length) return [];

  const out = [];
  for (let i = 0; i < rows.length; i += 2) {
    out.push({ value: rows[i], hits: Number(rows[i + 1]) || 0 });
  }
  return out;
}

export async function getAnalyticsDetails() {
  const client = getRedis();
  if (!client) {
    return {
      ok: false,
      configured: false,
      error: "redis_not_configured",
    };
  }

  const keys = [
    KEYS.visits,
    KEYS.api_hits,
    KEYS.installs,
    KEY_HUMAN_VISITS,
    KEY_BOT_VISITS,
    KEY_HUMAN_API,
    KEY_BOT_API,
    ...BOT_BUCKETS.map((b) => `${PREFIX_BOT}${b}`),
  ];

  const values = await client.mget(...keys);
  const pick = (i) => Number(values[i]) || 0;

  const bot_traffic_breakdown = {};
  BOT_BUCKETS.forEach((bucket, i) => {
    const v = pick(7 + i);
    if (v > 0) bot_traffic_breakdown[bucket] = v;
  });

  const topUa = await topFromZset(client, ZSET_UA, 20);
  const topIp = await topFromZset(client, ZSET_IP, 15);

  const top_consumers = topUa.map((row) => ({
    user_agent: row.value,
    hits: row.hits,
    category: classifyClient(row.value, "api_hit"),
  }));

  const top_ips = topIp.map((row) => ({
    ip: row.value,
    hits: row.hits,
  }));

  return {
    ok: true,
    configured: true,
    summary: {
      total_visits: pick(0),
      api_hits: pick(1),
      npm_installs: pick(2),
      human_browser_visits: pick(3),
      bot_browser_visits: pick(4),
      human_api_hits: pick(5),
      bot_api_hits: pick(6),
    },
    bot_traffic_breakdown,
    top_consumers,
    top_ips,
    generated_at: new Date().toISOString(),
  };
}
