// Pay one open bill (demo: no real payment). Tier: elevated.
import { z } from "zod";
import { prisma } from "../../../lib/prisma";
import { requireAccount, readInput } from "../../../lib/session";

const Input = z.object({ billId: z.string().min(1) });

export default defineEventHandler(async (event) => {
  const { account } = await requireAccount(event);
  // TODO(Stage 7): await requireTrust(event, "elevated");
  const { billId } = await readInput(event, Input);

  const { count } = await prisma.bill.updateMany({ where: { id: billId, accountId: account.id, paid: false }, data: { paid: true } });
  if (!count) throw createError({ statusCode: 404, statusMessage: "No open bill with that id" });
  return { ok: true };
});
