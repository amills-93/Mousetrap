import { auth, CLIENT_IP_HEADER } from "../../lib/auth";

const TRUST_PROXY = process.env.TRUST_PROXY === "true";

export default defineEventHandler((event) => {
  const req = toWebRequest(event);
  // Better Auth reads the client IP (rate limiting, session.ipAddress) only from this header, which we
  // always overwrite: with the socket address, or behind Caddy (TRUST_PROXY=true) with the X-Forwarded-For
  // that Caddy overwrites per request (deploy/Caddyfile), so clients cannot spoof it either way.
  const headers = new Headers(req.headers);
  headers.set(CLIENT_IP_HEADER, getRequestIP(event, { xForwardedFor: TRUST_PROXY }) ?? "");
  return auth.handler(new Request(req, { headers }));
});
