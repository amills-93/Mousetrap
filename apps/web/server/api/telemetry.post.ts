// Collector ingest (ARCHITECTURE.md 5.1). Accepts same-origin fetch (application/json) and sendBeacon
// (text/plain). User and session come from the Better Auth cookie, never from the payload.
import { requireSession } from "../lib/session";
import { TelemetryBatch, acceptSeq, allowRequest } from "../lib/telemetry";
import { mlIngest } from "../lib/ml";
import { logRiskEvent } from "../lib/trust";
import { passiveEnroll } from "../lib/enroll";

// One "score" RiskEvent per session every SCORE_EVERY_MS feeds the /admin/risk timeline.
const SCORE_EVERY_MS = 5000;
const lastScore = new Map<string, number>();

const MAX_BODY = 256 * 1024;

export default defineEventHandler(async (event) => {
  const { user, session } = await requireSession(event);

  const site = getHeader(event, "sec-fetch-site");
  if (site && site !== "same-origin") throw createError({ statusCode: 403, statusMessage: "Cross-site telemetry" });
  const type = getHeader(event, "content-type") ?? "";
  if (!/^(application\/json|text\/plain)\b/.test(type)) {
    throw createError({ statusCode: 415, statusMessage: "Expected JSON" });
  }

  if (!allowRequest(session.id)) throw createError({ statusCode: 429, statusMessage: "Too many telemetry batches" });

  const raw = (await readRawBody(event, "utf8")) ?? "";
  if (raw.length > MAX_BODY) throw createError({ statusCode: 413, statusMessage: "Batch too large" });
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    throw createError({ statusCode: 400, statusMessage: "Invalid JSON" });
  }
  const parsed = TelemetryBatch.safeParse(json);
  if (!parsed.success) throw createError({ statusCode: 400, statusMessage: "Invalid telemetry batch" });
  const batch = parsed.data;

  if (!acceptSeq(session.id, batch.pageId, batch.seq)) {
    throw createError({ statusCode: 409, statusMessage: "Stale or replayed batch" });
  }

  try {
    const res = await mlIngest({ userId: user.id, sessionId: session.id, batch });
    const { buffered, risk } = res;
    void passiveEnroll(user.id, res);
    const now = Date.now();
    if (risk != null && now - (lastScore.get(session.id) ?? 0) >= SCORE_EVERY_MS) {
      if (lastScore.size > 5000) lastScore.clear();
      lastScore.set(session.id, now);
      void logRiskEvent({ userId: user.id, sessionId: session.id, type: "score", risk });
    }
    return { buffered }; // events held for this session at ML; shown by the dev overlay
  } catch (err) {
    console.error("[telemetry] ML ingest failed:", (err as Error).message);
    throw createError({ statusCode: 502, statusMessage: "ML service unavailable" });
  }
});
