import { recordEvent } from "../lib/analytics.js";

const ALLOWED = new Set(["visit", "api_hit", "install"]);

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method_not_allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      return res.status(400).json({ ok: false, error: "invalid_json" });
    }
  }

  const event = (body?.event || "").trim();
  if (!ALLOWED.has(event)) {
    return res.status(400).json({
      ok: false,
      error: "invalid_event",
      allowed: [...ALLOWED],
    });
  }

  const result = await recordEvent(event, req);
  if (!result.ok) {
    return res.status(503).json(result);
  }

  return res.status(200).json(result);
}
