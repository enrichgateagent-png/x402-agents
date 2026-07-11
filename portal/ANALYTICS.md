# Beacon Portal Analytics (Vercel Serverless + Upstash Redis)

Tracks three metrics:
- **visits** — unique page loads (once per browser session)
- **api_hits** — registry API calls from the portal
- **installs** — MCP install command copies

## 1. Create Upstash Redis (free tier works)

1. Go to [console.upstash.com](https://console.upstash.com) → Create database
2. Copy **UPSTASH_REDIS_REST_URL** and **UPSTASH_REDIS_REST_TOKEN**

Or use **Vercel KV** (Storage tab in Vercel project) — it sets `KV_REST_API_URL` and `KV_REST_API_TOKEN` automatically.

## 2. Add env vars to Vercel

Project → Settings → Environment Variables:

| Variable | Value |
|----------|-------|
| `UPSTASH_REDIS_REST_URL` | `https://....upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` | your token |

Apply to **Production**, **Preview**, and **Development**.

## 3. Deploy

```bash
cd x402-agents/portal
npm install
npx vercel deploy --prod
```

## 4. API

### POST `/api/track`

```bash
curl -X POST https://portal-five-phi-54.vercel.app/api/track \
  -H "content-type: application/json" \
  -d '{"event":"visit"}'
```

Events: `visit` | `api_hit` | `install`

### GET `/api/stats`

```bash
curl https://portal-five-phi-54.vercel.app/api/stats
```

Response:

```json
{
  "ok": true,
  "configured": true,
  "visits": 42,
  "api_hits": 128,
  "installs": 7
}
```

## Repository layout

```
portal/
  api/
    track.js      # POST — increment counter
    stats.js      # GET  — read counters
  lib/
    redis.js      # Upstash client + keys
  index.html      # auto-tracks visits, api hits, installs
  vercel.json     # proxies /api/v1/* to GCP registry only
  package.json
```

## Admin dashboard (password-protected)

Set in Vercel → Settings → Environment Variables:

| Variable | Value |
|----------|-------|
| `ADMIN_SECRET_PASSWORD` | your strong secret (pick a long random string) |

### GET `/api/admin/analytics-details`

Requires auth via **one** of:

```bash
# Bearer token (recommended)
curl -H "Authorization: Bearer YOUR_ADMIN_SECRET_PASSWORD" \
  https://portal-five-phi-54.vercel.app/api/admin/analytics-details

# Or X-Admin-Token header
curl -H "X-Admin-Token: YOUR_ADMIN_SECRET_PASSWORD" \
  https://portal-five-phi-54.vercel.app/api/admin/analytics-details
```

Returns bot vs human breakdown, npm install counts, top user-agents and IPs.

Wrong or missing password → `401 Unauthorized`.

---

## Registry VM env (optional)

On the GCP registry `.env`:

```bash
TAG_CACHE_TTL_SECS=3600
MCP_SSE_URL=http://34.45.7.252:8001/sse
```
