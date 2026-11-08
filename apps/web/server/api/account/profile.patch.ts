// Edit name, email, and address. Tier: elevated.
import { z } from "zod";
import { prisma } from "../../lib/prisma";
import { requireAccount, readInput } from "../../lib/session";

const Input = z.object({
  name: z.string().trim().min(1, "Name is required").max(80),
  email: z.string().trim().toLowerCase().email("Enter a valid email"),
  street: z.string().trim().max(120),
  city: z.string().trim().max(60),
  state: z.string().trim().max(30),
  zip: z.string().trim().regex(/^(\d{5}(-\d{4})?)?$/, "ZIP must be 5 digits"),
});

export default defineEventHandler(async (event) => {
  const { session, account } = await requireAccount(event);
  // TODO(Stage 7): await requireTrust(event, "elevated");
  const { name, email, ...address } = await readInput(event, Input);

  if (email !== session.user.email) {
    const taken = await prisma.user.findUnique({ where: { email } });
    if (taken) throw createError({ statusCode: 409, statusMessage: "That email is already in use" });
  }

  // Demo scope: email changes apply immediately (no verification email is sent).
  await prisma.$transaction([
    prisma.user.update({ where: { id: session.user.id }, data: { name, email } }),
    prisma.customerAccount.update({ where: { id: account.id }, data: address }),
  ]);
  return { ok: true };
});
