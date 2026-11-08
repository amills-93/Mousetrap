// Passive enrollment (ARCHITECTURE.md 8.4, principle 5). A user without an active profile is enrolled from
// normal portal use: their first telemetry batch starts enrollment at ML, and once ML reports enough windows
// the model is trained and the profile activated. Nothing is shown to the user.
import type { H3Event } from "h3";
import { mlEnrollFinish, mlEnrollStart, type MlIngest } from "./ml";
import { prisma } from "./prisma";
import { requireSession } from "./session";
import { requireTrust } from "./trust";

export async function startEnrollment(userId: string) {
  await mlEnrollStart(userId);
  await prisma.biometricProfile.upsert({
    where: { userId },
    create: { userId, status: "enrolling" },
    update: { status: "enrolling", windowCount: 0 },
  });
}

async function finishEnrollment(userId: string) {
  const res = await mlEnrollFinish(userId);
  if (!res.ok) throw new Error(res.error ?? "enrollment incomplete");
  const data = { status: "active", windowCount: res.windowCount, modelVersion: res.modelVersion ?? 1 };
  await prisma.biometricProfile.upsert({ where: { userId }, create: { userId, ...data }, update: data });
  console.log(`[enroll] ${userId} active: v${data.modelVersion}, ${data.windowCount} windows`);
}

const busy = new Set<string>(); // one start/finish per user at a time (several tabs or sessions may report)

// Called after every ingest with ML's view of the user. Fire-and-forget: never delays or fails telemetry.
export async function passiveEnroll(userId: string, ml: MlIngest) {
  if ((ml.enrolled && !ml.enrolling) || busy.has(userId)) return;
  busy.add(userId);
  try {
    if (ml.enrollReady) await finishEnrollment(userId);
    else if (!ml.enrolling) {
      // No model and not enrolling: a new user. An active profile is never replaced passively (principle 5).
      const profile = await prisma.biometricProfile.findUnique({ where: { userId } });
      if (profile?.status !== "active") await startEnrollment(userId);
    }
  } catch (err) {
    console.error(`[enroll] ${userId}:`, (err as Error).message);
  } finally {
    busy.delete(userId);
  }
}

export async function requireEnrollableUser(event: H3Event) {
  const { user } = await requireSession(event);
  const profile = await prisma.biometricProfile.findUnique({ where: { userId: user.id } });
  // Principle 5: an active template is only replaced from a verified session.
  if (profile?.status === "active") await requireTrust(event, "critical");
  return user;
}
