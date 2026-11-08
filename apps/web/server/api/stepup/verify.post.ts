// Step-up verification (ARCHITECTURE.md 5.3, 5.4). Uses Better Auth's own TOTP check against the active
// session, so the user's existing authenticator entry works; with a session it creates no new session and
// applies no sign-in lockout, so failures are counted here in SessionTrust (3 strikes revoke the session).
import { z } from "zod";
import { auth } from "../../lib/auth";
import { readInput, requireSession } from "../../lib/session";
import { recordStepUp } from "../../lib/trust";

const Input = z.object({ code: z.string().trim().regex(/^\d{6}$/, "Enter the 6-digit code") });

export default defineEventHandler(async (event) => {
  const { user, session } = await requireSession(event);
  const { code } = await readInput(event, Input);
  const ok = await auth.api
    .verifyTOTP({ body: { code }, headers: event.headers })
    .then(() => true)
    .catch(() => false);
  const result = await recordStepUp(user.id, session.id, ok);
  if (!ok) {
    throw createError({
      statusCode: 400,
      statusMessage: `Incorrect code. ${result.attemptsLeft} attempt${result.attemptsLeft === 1 ? "" : "s"} left.`,
      data: { attemptsLeft: result.attemptsLeft },
    });
  }
  return { ok: true, stepUpUntil: result.stepUpUntil };
});
