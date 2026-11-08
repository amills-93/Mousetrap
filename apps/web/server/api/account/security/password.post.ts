// Change password through Better Auth (verifies the current password). Tier: critical.
import { z } from "zod";
import { auth } from "../../../lib/auth";
import { readInput } from "../../../lib/session";
import { requireTrust } from "../../../lib/trust";

const Input = z.object({
  currentPassword: z.string().min(1, "Enter your current password"),
  newPassword: z.string().min(8, "New password must be at least 8 characters").max(128),
  revokeOtherSessions: z.boolean().default(false),
});

export default defineEventHandler(async (event) => {
  await requireTrust(event, "critical");
  const body = await readInput(event, Input);

  try {
    // asResponse so Better Auth's Set-Cookie (new session when revoking others) reaches the browser.
    const res = await auth.api.changePassword({ body, headers: event.headers, asResponse: true });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw createError({ statusCode: res.status, statusMessage: err.message || "Could not change password" });
    }
    for (const c of res.headers.getSetCookie()) appendResponseHeader(event, "set-cookie", c);
    return { ok: true };
  } catch (e) {
    if (isError(e)) throw e;
    throw createError({ statusCode: 400, statusMessage: "Could not change password" });
  }
});
