// Shared enrollment constants and guards (ARCHITECTURE.md 8.4, principle 5).
import type { H3Event } from "h3";
import { prisma } from "./prisma";
import { requireSession } from "./session";
import { requireTrust } from "./trust";

export const ENROLL_MIN_WINDOWS = 20; // ML refuses to train below this
export const ENROLL_TARGET_WINDOWS = 40;

export async function requireEnrollableUser(event: H3Event) {
  const { user } = await requireSession(event);
  const profile = await prisma.biometricProfile.findUnique({ where: { userId: user.id } });
  // Principle 5: an active template is only replaced from a verified session.
  if (profile?.status === "active") await requireTrust(event, "critical");
  return user;
}
