import { Redis } from "@upstash/redis";

export const KEYS = {
  visits: "beacon:stats:visits",
  api_hits: "beacon:stats:api_hits",
  installs: "beacon:stats:installs",
};

let redis = null;

export function getRedis() {
  if (redis) return redis;

  const url =
    process.env.UPSTASH_REDIS_REST_URL ||
    process.env.KV_REST_API_URL;
  const token =
    process.env.UPSTASH_REDIS_REST_TOKEN ||
    process.env.KV_REST_API_TOKEN;

  if (!url || !token) return null;

  redis = new Redis({ url, token });
  return redis;
}
