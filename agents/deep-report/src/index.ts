// Local/VPS entrypoint. On Vercel, api/index.ts is used instead.
import { serve } from "@hono/node-server";
import { app } from "./app.js";

const PORT = Number(process.env.PORT ?? 4023);
serve({ fetch: app.fetch, port: PORT }, (info) => console.log(`deep-report on http://localhost:${info.port}`));
