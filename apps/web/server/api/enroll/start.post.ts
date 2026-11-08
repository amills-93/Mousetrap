// Begin enrollment: ML starts routing this user's windows to a fresh enrollment buffer.
import { requireEnrollableUser } from "../../lib/enroll";
import { mlEnrollStart } from "../../lib/ml";
import { prisma } from "../../lib/prisma";

export default defineEventHandler(async (event) => {
  const user = await requireEnrollableUser(event);
  await mlEnrollStart(user.id).catch(() => {
    throw createError({ statusCode: 502, statusMessage: "ML service unavailable" });
  });
  await prisma.biometricProfile.upsert({
    where: { userId: user.id },
    create: { userId: user.id, status: "enrolling" },
    update: { status: "enrolling", windowCount: 0 },
  });
  return { ok: true };
});
