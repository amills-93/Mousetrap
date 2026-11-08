// Enforcement around the pure policy (ARCHITECTURE.md 5.2-5.4, 7.4): gathers decide()'s inputs, logs every
// decision as a RiskEvent, revokes the session on deny, and tracks step-up state in SessionTrust.
import { randomUUID } from "node:crypto";
import type { H3Event } from "h3";
import { mlChallengeResult, mlChallengeStart, mlFeedback, mlRisk, mlRiskClose, type MlRisk } from "./ml";
import { MIN_WINDOWS, decide, judgeTyping, type Decision, type Tier, type TrustInput } from "./policy";
import { prisma } from "./prisma";
import { requireSession } from "./session";

export const STEP_UP_TTL_MS = 60 * 1000; // short on purpose: long enough to retry the action, not to browse on
export const MAX_STEP_UP_FAILURES = 3;

// closeWindow: have ML score the open window first (gated actions only; the overlay's polling must not).
export async function loadTrust(userId: string, sessionId: string, closeWindow = false): Promise<{ input: TrustInput; ml: MlRisk | null }> {
  const [ml, profile, trust] = await Promise.all([
    (closeWindow ? mlRiskClose(userId, sessionId) : mlRisk(sessionId)).catch(() => null),
    prisma.biometricProfile.findUnique({ where: { userId } }),
    prisma.sessionTrust.findUnique({ where: { sessionId } }),
  ]);
  return {
    ml,
    input: {
      risk: ml?.risk ?? null,
      windows: ml?.windows ?? 0,
      profileActive: profile?.status === "active",
      stepUpActive: !!trust?.stepUpUntil && trust.stepUpUntil > new Date(),
    },
  };
}

type EventType = Decision | "score" | "stepup_ok" | "stepup_failed" | "typing_failed";

export function logRiskEvent(e: { userId: string; sessionId: string; type: EventType; tier?: Tier; risk?: number | null; route?: string }) {
  return prisma.riskEvent
    .create({ data: { ...e, tier: e.tier ?? null, risk: e.risk ?? null, route: e.route ?? null } })
    .catch((err) => console.error("[trust] RiskEvent write failed:", err.message));
}

// Revoke the Better Auth session (deny / too many failed step-ups). Other sessions in the browser survive.
export async function revokeSession(sessionId: string) {
  await prisma.session.deleteMany({ where: { id: sessionId } });
  await prisma.sessionTrust.deleteMany({ where: { sessionId } });
}

// reason is a code; /login maps it to text (never echo free text from the URL). No reason: /login shows nothing.
const logout = (reason?: "stepup_failed", message = "Unauthorized") =>
  createError({ statusCode: 401, statusMessage: message, data: { action: "logout", reason } });

// Gate a sensitive route. Returns the session on allow; throws 403 {action:"step_up"} or 401 {action:"logout"}.
export async function requireTrust(event: H3Event, tier: Tier) {
  const auth = await requireSession(event);
  const { user, session } = auth;
  const { input } = await loadTrust(user.id, session.id, true);
  const decision = decide(input, tier);
  await logRiskEvent({ userId: user.id, sessionId: session.id, type: decision, tier, risk: input.risk, route: event.path });

  if (decision === "deny") {
    await revokeSession(session.id);
    throw logout(); // silent on purpose: an impostor learns nothing about why they were signed out
  }
  if (decision === "step_up") {
    // Collect the phrase typing from here on; a failure only means the prompt judges by TOTP alone.
    await mlChallengeStart(user.id, session.id).catch((err) => console.error("[trust] challenge start failed:", err.message));
    throw createError({
      statusCode: 403,
      statusMessage: "Verification required",
      data: { action: "step_up", tier, challengeId: randomUUID() },
    });
  }
  return auth;
}

// Judge the step-up phrase typing before the code (ARCHITECTURE.md 5.3b). Foreign typing revokes the session
// silently, like a deny. Returns whether the typing passed, which also lets the step-up teach ML.
export async function checkStepUpTyping(userId: string, sessionId: string): Promise<boolean> {
  const result = await mlChallengeResult(userId, sessionId).catch(() => null);
  const verdict = judgeTyping(result);
  if (verdict === "retry") {
    throw createError({ statusCode: 400, statusMessage: "Type the phrase shown above, then enter your code.", data: { action: "type_phrase" } });
  }
  if (verdict === "fail") {
    await logRiskEvent({ userId, sessionId, type: "typing_failed", risk: result?.risk ?? null });
    await revokeSession(sessionId);
    throw logout();
  }
  return verdict === "pass";
}

// Record a step-up attempt. Success opens the 60 s window and, when ML had already scored the session, tells it
// the recent windows are genuine. A step-up forced by missing telemetry (e.g. a SIM swap right after sign-in) is
// passed with the same TOTP used to sign in, so its windows prove nothing and could be an attacker's.
export async function recordStepUp(userId: string, sessionId: string, ok: boolean, typingPassed = false) {
  if (ok) {
    const stepUpUntil = new Date(Date.now() + STEP_UP_TTL_MS);
    await prisma.sessionTrust.upsert({
      where: { sessionId },
      create: { sessionId, userId, stepUpUntil, failedStepUp: 0 },
      update: { stepUpUntil, failedStepUp: 0 },
    });
    await logRiskEvent({ userId, sessionId, type: "stepup_ok" });
    const ml = await mlRisk(sessionId).catch(() => null);
    if (typingPassed || (ml && ml.windows >= MIN_WINDOWS)) {
      mlFeedback({ userId, sessionId, label: "genuine" }).catch((err) => console.error("[trust] ML feedback failed:", err.message));
    }
    return { stepUpUntil, attemptsLeft: MAX_STEP_UP_FAILURES };
  }
  const trust = await prisma.sessionTrust.upsert({
    where: { sessionId },
    create: { sessionId, userId, failedStepUp: 1 },
    update: { failedStepUp: { increment: 1 } },
  });
  await logRiskEvent({ userId, sessionId, type: "stepup_failed" });
  const attemptsLeft = Math.max(0, MAX_STEP_UP_FAILURES - trust.failedStepUp);
  if (!attemptsLeft) {
    await revokeSession(sessionId);
    throw logout("stepup_failed", "Signed out after too many incorrect verification codes.");
  }
  return { stepUpUntil: null, attemptsLeft };
}
