// Sign-up step: create the new user's CustomerAccount with one line (pages/signup.vue). Create-only: a user
// who already has an account gets 409, so this can never change existing account data and needs no trust tier.
// All generated identifiers are fictional: NM- account numbers, (214) 555-01xx numbers, 8999-prefixed ICCIDs.
import { randomInt } from "node:crypto";
import { z } from "zod";
import { PLAN_NAMES, planFor } from "../../lib/plans";
import { prisma } from "../../lib/prisma";
import { readInput, requireSession } from "../../lib/session";

const Input = z.object({
  street: z.string().trim().min(1, "Street address is required").max(120),
  unit: z.string().trim().max(30).default(""),
  city: z.string().trim().min(1, "City is required").max(60),
  state: z.string().trim().regex(/^[A-Z]{2}$/, "Choose a state"),
  zip: z.string().trim().regex(/^\d{5}(-\d{4})?$/, "ZIP must be 5 digits"),
  plan: z.enum(PLAN_NAMES),
  nickname: z.string().trim().min(1, "Give the line a name").max(30),
  portPin: z
    .string()
    .regex(/^\d{6}$/, "PIN must be 6 digits")
    .refine((p) => !/^(\d)\1{5}$/.test(p) && !"0123456789".includes(p) && !"9876543210".includes(p), "Choose a less guessable PIN"),
});

const digits = (n: number) => Array.from({ length: n }, () => randomInt(10)).join("");

async function freeAccountNumber() {
  for (;;) {
    const accountNumber = `NM-${digits(9)}`;
    if (!(await prisma.customerAccount.findUnique({ where: { accountNumber } }))) return accountNumber;
  }
}

export default defineEventHandler(async (event) => {
  const { user } = await requireSession(event);
  const { unit, plan, nickname, portPin, street, ...address } = await readInput(event, Input);
  if (await prisma.customerAccount.findUnique({ where: { userId: user.id } })) {
    throw createError({ statusCode: 409, statusMessage: "This login already has an account" });
  }

  const now = new Date();
  const firstDue = new Date(now.getFullYear(), now.getMonth() + 1, 21);
  await prisma.customerAccount.create({
    data: {
      userId: user.id,
      accountNumber: await freeAccountNumber(),
      portPin,
      street: unit ? `${street}, ${unit}` : street,
      ...address,
      lines: {
        create: {
          nickname,
          plan,
          deviceName: "Nimbus Phone 12",
          phone: `(214) 555-01${digits(2)}`,
          simIccid: `8999${digits(15)}`,
        },
      },
      bills: {
        create: {
          period: firstDue.toLocaleString("en-US", { month: "long", year: "numeric" }),
          amount: planFor(plan).price.toFixed(2),
          dueDate: firstDue,
        },
      },
    },
  });
  return { ok: true };
});
