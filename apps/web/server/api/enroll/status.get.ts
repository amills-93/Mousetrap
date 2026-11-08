// Enrollment progress for the signed-in user: stored profile status plus live window counts from ML.
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
    enrolling: ml?.enrolling ?? false,
    windows: ml?.enrollWindows ?? 0,
    keyWindows: ml?.enrollKeyWindows ?? 0,
    target: ml?.enrollTarget ?? 0,
    keyTarget: ml?.enrollKeyTarget ?? 0,
    mlAvailable: ml !== null,
  };
});
