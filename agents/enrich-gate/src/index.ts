// Local/VPS entrypoint. On Vercel, api/index.ts is used instead.
import { serve } from "@hono/node-server";
import { app, CATALOG } from "./app.js";

const PORT = Number(process.env.PORT ?? 4022);

serve({ fetch: app.fetch, port: PORT }, (info) => {
  const live = CATALOG.filter((e) => e.enabled).map((e) => e.path).join(", ") || "none (set provider keys)";
  console.log(`enrich-gate on http://localhost:${info.port} — live routes: ${live}`);
});
