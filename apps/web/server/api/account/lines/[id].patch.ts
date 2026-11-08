// Rename a line and/or change its plan. Tier: standard for a rename, critical when the plan changes.
import { z } from "zod";
import { prisma } from "../../../lib/prisma";
import { requireAccount, readInput } from "../../../lib/session";
import { requireTrust } from "../../../lib/trust";
import { PLAN_NAMES } from "../../../lib/plans";

const Input = z
  .object({
    nickname: z.string().trim().min(1, "Nickname is required").max(40).optional(),
    plan: z.enum(PLAN_NAMES, { message: "Unknown plan" }).optional(),
  })
  .refine((v) => v.nickname !== undefined || v.plan !== undefined, "Nothing to update");

export default defineEventHandler(async (event) => {
  const input = await readInput(event, Input);
  await requireTrust(event, input.plan !== undefined ? "critical" : "standard");
  const { account } = await requireAccount(event);

  const id = getRouterParam(event, "id")!;
  const { count } = await prisma.line.updateMany({ where: { id, accountId: account.id }, data: input });
  if (!count) throw createError({ statusCode: 404, statusMessage: "Line not found" });
  return { ok: true };
});
