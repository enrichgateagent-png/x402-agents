import { buildCursorrules, fetchMetrics } from "./_discovery.js";

export default async function handler(_req, res) {
  const metrics = await fetchMetrics();
  const body = buildCursorrules(metrics);
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=900, s-maxage=900");
  res.status(200).send(body);
}
