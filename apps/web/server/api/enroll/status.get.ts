// Enrollment progress for the signed-in user: stored profile status plus live window count from ML.
import { ENROLL_MIN_WINDOWS, ENROLL_TARGET_WINDOWS } from "../../lib/enroll";
import { mlUserStatus } from "../../lib/ml";
import { prisma } from "../../lib/prisma";
import { requireSession } from "../../lib/session";

export default defineEventHandler(async (event) => {
  const { user } = await requireSession(event);
  const profile = await prisma.biometricProfile.findUnique({ where: { userId: user.id } });
  const ml = await mlUserStatus(user.id).catch(() => null);
  return {
    status: profile?.status ?? "none",
    modelVersion: profile?.modelVersion ?? 0,
    windowCount: profile?.windowCount ?? 0,
    // "enrolling" in the DB but not at ML means ML restarted and lost the in-memory buffer.
    enrolling: ml?.enrolling ?? false,
    windows: ml?.enrollWindows ?? 0,
    min: ENROLL_MIN_WINDOWS,
    target: ENROLL_TARGET_WINDOWS,
    mlAvailable: ml !== null,
  };
});
