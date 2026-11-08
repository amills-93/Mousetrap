// Typed client for the internal ML service (ARCHITECTURE.md 8.1). Only Nuxt talks to it, with X-Internal-Key.
import type { TelemetryBatch } from "@mousetrap-auth/collector";
import type { CoachingSignals } from "./policy";

function ml<T>(path: string, opts: { method?: "GET" | "POST"; body?: unknown; timeout?: number } = {}) {
  const { mlUrl, mlInternalKey } = useRuntimeConfig();
  return $fetch<T>(`${mlUrl}${path}`, {
    method: opts.method ?? "GET",
    body: opts.body as Record<string, unknown> | undefined,
    headers: { "X-Internal-Key": mlInternalKey },
    timeout: opts.timeout ?? 2000,
  });
}

export const mlIngest = (body: { userId: string; sessionId: string; batch: TelemetryBatch }) =>
  ml<MlIngest>("/ingest", { method: "POST", body });

export interface MlIngest {
  ok: boolean;
  buffered: number;
  risk?: number | null;
  scoredWindows?: number | null;
  enrolled: boolean; // the user has a trained model
  enrolling: boolean; // windows go to the enrollment buffer instead of scoring
  enrollReady: boolean; // enough enrollment windows to train
}

export interface MlUserStatus {
  enrolled: boolean;
  enrolling: boolean;
  enrollWindows: number; // windows collected in the current enrollment
  enrollKeyWindows: number; // of those, windows with typing
  enrollTarget: number; // enrollWindows needed before training
  enrollKeyTarget: number; // enrollKeyWindows needed before training
  windowCount: number; // windows the current model was trained on
  modelVersion: number;
}

export const mlEnrollStart = (userId: string) =>
  ml<{ ok: boolean }>(`/enroll/${encodeURIComponent(userId)}/start`, { method: "POST" });

export const mlEnrollFinish = (userId: string) =>
  ml<{ ok: boolean; windowCount: number; modelVersion?: number | null; error?: string | null }>(
    `/enroll/${encodeURIComponent(userId)}/finish`,
    { method: "POST", timeout: 15000 }, // trains the model
  );

export const mlUserStatus = (userId: string) => ml<MlUserStatus>(`/users/${encodeURIComponent(userId)}/status`);

export interface MlRisk {
  risk: number; // session EWMA in [0, 1]
  windows: number; // windows scored this session
  lastUpdated: number | null; // unix seconds
  components: Partial<Record<"keys" | "mouse" | "touch", number>>;
  bot: number; // bot-heuristic penalty on the last window
  coaching?: CoachingSignals; // counts from ML's coaching.py
}

// 300 ms budget (ARCHITECTURE.md 7.4 step 3): policy treats a slow ML the same as a down ML.
export const mlRisk = (sessionId: string) =>
  ml<MlRisk>(`/risk/${encodeURIComponent(sessionId)}`, { timeout: 300 });

// Same, after ML scores the session's open window. Used when a gated action is attempted.
export const mlRiskClose = (userId: string, sessionId: string) =>
  ml<MlRisk>(`/risk/${encodeURIComponent(sessionId)}/close`, { method: "POST", body: { userId }, timeout: 300 });

export interface MlChallenge {
  keysModeled: boolean;
  started: boolean;
  windows: number;
  risk: number | null;
}

// Step-up typing challenge: start when the prompt opens; result when the code is submitted.
export const mlChallengeStart = (userId: string, sessionId: string) =>
  ml<MlChallenge>(`/challenge/${encodeURIComponent(sessionId)}/start`, { method: "POST", body: { userId }, timeout: 1000 });
export const mlChallengeResult = (userId: string, sessionId: string) =>
  ml<MlChallenge>(`/challenge/${encodeURIComponent(sessionId)}/result`, { method: "POST", body: { userId }, timeout: 1000 });

export interface MlVerdict {
  verdict: "scam" | "suspicious" | "ok";
  scamProbability: number;
  category: string | null;
  categoryLabel: string | null;
  categoryProbability: number | null;
  advice: string | null;
  accountRisk: boolean;
  redFlags: { id: string; label: string }[];
}

// Scam verdict for one text message (ARCHITECTURE.md 8.7). ML scores it and keeps nothing.
export const mlClassify = (text: string) => ml<MlVerdict>("/classify", { method: "POST", body: { text }, timeout: 2000 });

// After a successful step-up only (principle 5): ML adds the session's recent windows and retrains.
export const mlFeedback = (body: { userId: string; sessionId: string; label: "genuine" }) =>
  ml<{ ok: boolean; windows: number }>("/feedback", { method: "POST", body });

// DEMO_MODE only: ML forgets all per-session state (risk EWMA, coaching counts, buffers). Models are kept.
export const mlDemoReset = () => ml<{ ok: boolean }>("/demo/reset", { method: "POST" });
