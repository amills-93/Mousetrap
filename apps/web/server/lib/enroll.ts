// Shared enrollment constants and guards (ARCHITECTURE.md 8.4, principle 5).
import type { H3Event } from "h3";
import { prisma } from "./prisma";
import { requireSession } from "./session";

export const ENROLL_MIN_WINDOWS = 20; // ML refuses to train below this
export const ENROLL_TARGET_WINDOWS = 40;

export async function requireEnrollableUser(event: H3Event) {
  const { user } = await requireSession(event);
  const profile = await prisma.biometricProfile.findUnique({ where: { userId: user.id } });
  // Principle 5: an active template must not be replaced from an unverified session.
  // TODO(Stage 7): allow re-enrollment behind requireTrust(event, "critical") instead of refusing.
  if (profile?.status === "active") {
    throw createError({ statusCode: 409, statusMessage: "Already enrolled. Re-enrollment needs step-up verification." });
  }
  return user;
}
