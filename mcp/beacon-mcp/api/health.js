export default function handler(_req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(200).json({
    ok: true,
    service: "beacon-mcp",
    transport: "streamable-http",
    mcp: "/mcp",
    registry: process.env.BEACON_REGISTRY_URL ?? "https://registry-ruby.vercel.app",
  });
}
