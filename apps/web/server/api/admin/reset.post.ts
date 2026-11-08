// DEMO_MODE only: put every account back to a clean slate between demo runs. Clears step-up windows and failure
// counts, TOTP lockouts, scam holds, risk events, the inboxes (refilled with fresh timestamps on the next visit),
// and ML's per-session risk and coaching state. Sessions, users and trained behavioral models are kept.
import { mlDemoReset } from "../../lib/ml";
import { prisma } from "../../lib/prisma";
import { requireSession } from "../../lib/session";

export default defineEventHandler(async (event) => {
  if (!useRuntimeConfig().public.demoMode) throw createError({ statusCode: 404, statusMessage: "Not found" });
  await requireSession(event);

  await prisma.$transaction([
    prisma.sessionTrust.deleteMany(),
    prisma.scamHold.deleteMany(),
    prisma.riskEvent.deleteMany(),
    prisma.message.deleteMany(),
    prisma.twoFactor.updateMany({ data: { failedVerificationCount: 0, lockedUntil: null } }),
  ]);
  const ml = await mlDemoReset()
    .then(() => true)
    .catch((err) => {
      console.error("[reset] ML reset failed:", err.message);
      return false;
    });
  return { ok: true, ml };
});
