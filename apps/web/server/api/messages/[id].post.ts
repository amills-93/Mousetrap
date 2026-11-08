// Customer feedback on a verdict: "report" (it is a scam) or "not_scam" (the filter was wrong). Recorded only;
// a "not_scam" message stops counting toward the scam-contact signal (7.5).
import { z } from "zod";
import { prisma } from "../../lib/prisma";
import { readInput, requireSession } from "../../lib/session";

const Input = z.object({ action: z.enum(["report", "not_scam"]) });

export default defineEventHandler(async (event) => {
  const { user } = await requireSession(event);
  const { action } = await readInput(event, Input);
  const id = getRouterParam(event, "id") ?? "";
  const { count } = await prisma.message.updateMany({
    where: { id, userId: user.id },
    data: { customerVerdict: action === "report" ? "reported" : "not_scam" },
  });
  if (!count) throw createError({ statusCode: 404, statusMessage: "Message not found" });
  return { ok: true };
});
