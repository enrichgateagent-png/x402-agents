/** Sitemap — all /discover/* SEO pages + homepage. Slugs from lib/seo-capabilities.json */

import caps from "../lib/seo-capabilities.json" with { type: "json" };

const PORTAL = "https://portal-five-phi-54.vercel.app";
const TODAY = new Date().toISOString().slice(0, 10);

const EXTRA = [
  "/for-agents.html",
];

function buildSitemap() {
  const urls = [
    PORTAL + "/",
    ...EXTRA.map((p) => PORTAL + p),
    ...caps.map((c) => `${PORTAL}/discover/${c.slug}`),
  ];
  const entries = urls
    .map(
      (loc) =>
        `  <url><loc>${loc}</loc><lastmod>${TODAY}</lastmod><changefreq>daily</changefreq><priority>${loc.endsWith("/") ? "1.0" : "0.8"}</priority></url>`
    )
    .join("\n");
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    entries +
    "\n</urlset>\n"
  );
}

export default function handler(_req, res) {
  const body = buildSitemap();
  res.setHeader("Content-Type", "text/xml; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600, s-maxage=3600");
  res.status(200).send(body);
}
