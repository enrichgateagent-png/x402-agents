import { verifyAdmin, unauthorized } from "../../lib/auth.js";
import { getAnalyticsDetails } from "../../lib/analytics.js";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, private");

  if (req.method !== "GET") {
    return res.status(405).json({ ok: false, error: "method_not_allowed" });
  }

  if (!verifyAdmin(req)) {
    return unauthorized(res);
  }

  const details = await getAnalyticsDetails();
  if (!details.ok) {
    return res.status(503).json({ authenticated: true, ...details });
  }

  return res.status(200).json({
    authenticated: true,
    ...details,
  });
}
