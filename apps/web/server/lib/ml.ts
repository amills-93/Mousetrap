// Typed client for the internal ML service (ARCHITECTURE.md 8.1). Only Nuxt talks to it, with X-Internal-Key.
import type { TelemetryBatch } from "@mousetrap-auth/collector";

function ml<T>(path: string, opts: { method?: "GET" | "POST"; body?: unknown } = {}) {
  const { mlUrl, mlInternalKey } = useRuntimeConfig();
  return $fetch<T>(`${mlUrl}${path}`, {
    method: opts.method ?? "GET",
    body: opts.body as Record<string, unknown> | undefined,
    headers: { "X-Internal-Key": mlInternalKey },
    timeout: 2000,
  });
}

export const mlIngest = (body: { userId: string; sessionId: string; batch: TelemetryBatch }) =>
  ml<{ ok: boolean; buffered: number }>("/ingest", { method: "POST", body });
