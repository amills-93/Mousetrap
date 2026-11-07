// Turn autopay on or off. Tier: elevated.
import { z } from "zod";
import { prisma } from "../../../lib/prisma";
import { requireAccount, readInput } from "../../../lib/session";

const Input = z.object({ enabled: z.boolean() });

export default defineEventHandler(async (event) => {
  const { account } = await requireAccount(event);
  // TODO(Stage 7): await requireTrust(event, "elevated");
  const { enabled } = await readInput(event, Input);

  await prisma.customerAccount.update({ where: { id: account.id }, data: { autopay: enabled } });
  return { ok: true, autopay: enabled };
});
