// Gathers the inputs decide() needs for a session: ML risk, biometric profile, and step-up state.
import { mlRisk, type MlRisk } from "./ml";
import type { TrustInput } from "./policy";
import { prisma } from "./prisma";

export async function loadTrust(userId: string, sessionId: string): Promise<{ input: TrustInput; ml: MlRisk | null }> {
  const [ml, profile, trust] = await Promise.all([
    mlRisk(sessionId).catch(() => null),
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
