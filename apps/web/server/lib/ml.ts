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

export interface MlUserStatus {
  enrolled: boolean;
  enrolling: boolean;
  enrollWindows: number; // windows collected in the current enrollment
  windowCount: number; // windows the current model was trained on
  modelVersion: number;
}

export const mlEnrollStart = (userId: string) =>
  ml<{ ok: boolean }>(`/enroll/${encodeURIComponent(userId)}/start`, { method: "POST" });

export const mlEnrollFinish = (userId: string) =>
  ml<{ ok: boolean; windowCount: number; modelVersion?: number | null; error?: string | null }>(
    `/enroll/${encodeURIComponent(userId)}/finish`,
    { method: "POST" },
  );

export const mlUserStatus = (userId: string) => ml<MlUserStatus>(`/users/${encodeURIComponent(userId)}/status`);
