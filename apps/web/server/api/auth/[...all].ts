import { auth, CLIENT_IP_HEADER } from "../../lib/auth";

export default defineEventHandler((event) => {
  const req = toWebRequest(event);
  // Better Auth reads the client IP (rate limiting, session.ipAddress) only from this header, which we
  // always overwrite with the socket address so clients cannot spoof it via X-Forwarded-For.
  // Stage 8 (Caddy): switch to getRequestIP(event, { xForwardedFor: true }) once the proxy is trusted.
  const headers = new Headers(req.headers);
  headers.set(CLIENT_IP_HEADER, getRequestIP(event) ?? "");
  return auth.handler(new Request(req, { headers }));
});
