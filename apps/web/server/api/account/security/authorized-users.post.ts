// Add an authorized user to the account. Tier: critical.
import { z } from "zod";
import { prisma } from "../../../lib/prisma";
import { requireAccount, readInput } from "../../../lib/session";
import { requireTrust } from "../../../lib/trust";

const MAX_AUTHORIZED_USERS = 5;

const Input = z.object({
  name: z.string().trim().min(1, "Name is required").max(80),
  email: z.string().trim().toLowerCase().email("Enter a valid email"),
});

export default defineEventHandler(async (event) => {
  await requireTrust(event, "critical");
  const { account } = await requireAccount(event);
  const input = await readInput(event, Input);

  const existing = await prisma.authorizedUser.count({ where: { accountId: account.id } });
  if (existing >= MAX_AUTHORIZED_USERS) throw createError({ statusCode: 409, statusMessage: `Limit is ${MAX_AUTHORIZED_USERS} authorized users` });

  const created = await prisma.authorizedUser.create({ data: { ...input, accountId: account.id } });
  return { ok: true, id: created.id };
});
