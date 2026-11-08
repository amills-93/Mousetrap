// Train the user's model from the collected enrollment windows and activate the profile.
import { requireEnrollableUser } from "../../lib/enroll";
import { mlEnrollFinish } from "../../lib/ml";
import { prisma } from "../../lib/prisma";

export default defineEventHandler(async (event) => {
  const user = await requireEnrollableUser(event);
  const res = await mlEnrollFinish(user.id).catch(() => {
    throw createError({ statusCode: 502, statusMessage: "ML service unavailable" });
  });
  if (!res.ok) throw createError({ statusCode: 400, statusMessage: res.error ?? "Enrollment incomplete" });
  const profile = await prisma.biometricProfile.upsert({
    where: { userId: user.id },
    create: { userId: user.id, status: "active", windowCount: res.windowCount, modelVersion: res.modelVersion ?? 1 },
    update: { status: "active", windowCount: res.windowCount, modelVersion: res.modelVersion ?? 1 },
  });
  return { status: profile.status, windowCount: profile.windowCount, modelVersion: profile.modelVersion };
});
