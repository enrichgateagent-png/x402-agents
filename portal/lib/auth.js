/**
 * Admin auth — checks ADMIN_SECRET_PASSWORD via Bearer, Basic, or X-Admin-Token.
 */

export function getAdminSecret() {
  return process.env.ADMIN_SECRET_PASSWORD || "";
}

export function verifyAdmin(req) {
  const secret = getAdminSecret();
  if (!secret) return false;

  const auth = req.headers.authorization || "";

  if (auth.startsWith("Bearer ")) {
    return auth.slice(7).trim() === secret;
  }

  if (auth.startsWith("Basic ")) {
    try {
      const decoded = Buffer.from(auth.slice(6), "base64").toString("utf8");
      const colon = decoded.indexOf(":");
      const user = colon >= 0 ? decoded.slice(0, colon) : decoded;
      const pass = colon >= 0 ? decoded.slice(colon + 1) : "";
      return pass === secret || decoded === secret || user === secret;
    } catch {
      return false;
    }
  }

  const headerToken = req.headers["x-admin-token"];
  if (typeof headerToken === "string" && headerToken.trim() === secret) {
    return true;
  }

  return false;
}

export function unauthorized(res) {
  res.setHeader("WWW-Authenticate", 'Bearer realm="beacon-admin"');
  return res.status(401).json({
    ok: false,
    authenticated: false,
    error: "unauthorized",
    message: "Valid ADMIN_SECRET_PASSWORD required (Bearer token, Basic auth, or X-Admin-Token header).",
  });
}
