// Re-learn the profile from scratch (demo tooling; first enrollment starts on its own, see lib/enroll.ts).
// Replacing an active profile needs step-up (principle 5). Training happens automatically once ML has enough.
import { requireEnrollableUser, startEnrollment } from "../../lib/enroll";

export default defineEventHandler(async (event) => {
  const user = await requireEnrollableUser(event);
  await startEnrollment(user.id).catch(() => {
    throw createError({ statusCode: 502, statusMessage: "ML service unavailable" });
  });
  return { ok: true };
});
