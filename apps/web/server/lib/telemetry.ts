// Telemetry validation and in-memory guards (ARCHITECTURE.md 5.1, 9). Single web instance, so memory is enough.
import { z } from "zod";

const t = z.number().nonnegative();
const coord = z.number().int();
const KeyClass = z.enum(["letter", "digit", "space", "backspace", "enter", "modifier", "nav", "other"]);
const Key = { t, kc: KeyClass, code_hash: z.number().int().min(0).max(0xffff) };
const Button = { t, x: coord, y: coord, b: z.number().int().min(0).max(4) };

// z.object strips unknown keys, so anything beyond schema v1 (e.g. a stray `key`) never reaches ML.
const CollectorEvent = z.discriminatedUnion("k", [
  z.object({ k: z.literal("kd"), ...Key }),
  z.object({ k: z.literal("ku"), ...Key }),
  z.object({ k: z.literal("mm"), t, x: coord, y: coord }),
  z.object({ k: z.literal("md"), ...Button }),
  z.object({ k: z.literal("mu"), ...Button }),
  z.object({ k: z.literal("wh"), t, dy: z.number() }),
  z.object({ k: z.literal("fc"), t, role: z.string().max(40) }),
  z.object({ k: z.literal("nv"), t, route: z.string().max(200) }),
]);

export const TelemetryBatch = z.object({
  v: z.literal(1),
  pageId: z.uuid(),
  seq: z.number().int().positive(),
  vw: z.number().int().positive(),
  vh: z.number().int().positive(),
  synthetic: z.number().int().nonnegative().optional(),
  events: z.array(CollectorEvent).max(1000),
});

const TTL_MS = 30 * 60 * 1000;

function sweep<V extends { at: number }>(map: Map<string, V>) {
  if (map.size < 5000) return;
  const cutoff = Date.now() - TTL_MS;
  for (const [k, v] of map) if (v.at < cutoff) map.delete(k);
}

// Replay guard: seq must strictly increase per (session, pageId).
const lastSeq = new Map<string, { seq: number; at: number }>();

export function acceptSeq(sessionId: string, pageId: string, seq: number): boolean {
  const key = `${sessionId}:${pageId}`;
  const prev = lastSeq.get(key);
  if (prev && seq <= prev.seq) return false;
  sweep(lastSeq);
  lastSeq.set(key, { seq, at: Date.now() });
  return true;
}

// Token bucket per session: 5 req/s sustained, burst of 5.
const RATE = 5;
const buckets = new Map<string, { tokens: number; at: number }>();

export function allowRequest(sessionId: string): boolean {
  const now = Date.now();
  const b = buckets.get(sessionId) ?? { tokens: RATE, at: now };
  b.tokens = Math.min(RATE, b.tokens + ((now - b.at) / 1000) * RATE);
  b.at = now;
  const ok = b.tokens >= 1;
  if (ok) b.tokens -= 1;
  sweep(buckets);
  buckets.set(sessionId, b);
  return ok;
}
