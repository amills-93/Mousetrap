// The customer's answer to the scam pause (ARCHITECTURE.md 7.5). "cancel": someone asked them to do it, so the
// action is dropped. "hold": they are doing it themselves, so it can go ahead after the hold period.
import { z } from "zod";
import { prisma } from "../../lib/prisma";
import { readInput, requireSession } from "../../lib/session";
import { logRiskEvent, pauseHoldMs } from "../../lib/trust";

const Input = z.object({ choice: z.enum(["cancel", "hold"]) });

export default defineEventHandler(async (event) => {
  const { user, session } = await requireSession(event);
  const { choice } = await readInput(event, Input);
  const id = getRouterParam(event, "id") ?? "";
  const hold = await prisma.scamHold.findFirst({ where: { id, userId: user.id, sessionId: session.id, status: "pending" } });
  if (!hold) throw createError({ statusCode: 404, statusMessage: "Nothing to confirm" });

  const releaseAt = choice === "hold" ? new Date(Date.now() + pauseHoldMs()) : null;
  await prisma.scamHold.update({ where: { id }, data: { status: choice === "hold" ? "held" : "cancelled", releaseAt } });
  await logRiskEvent({ userId: user.id, sessionId: session.id, type: choice === "hold" ? "pause_held" : "pause_reported", tier: "critical", route: hold.route });
  return { status: choice === "hold" ? "held" : "cancelled", releaseAt };
});
