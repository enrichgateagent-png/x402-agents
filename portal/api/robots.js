/** robots.txt — served at /robots.txt via vercel.json rewrite */

export default function handler(_req, res) {
  const body = [
    "User-agent: *",
    "Allow: /",
    "",
    "Sitemap: https://portal-five-phi-54.vercel.app/sitemap.xml",
    "",
  ].join("\n");
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=86400");
  res.status(200).send(body);
}
