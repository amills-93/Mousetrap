// Move a line to a new SIM (physical ICCID) or a new eSIM. Tier: critical.
import { randomInt } from "node:crypto";
import { z } from "zod";
import { prisma } from "../../../lib/prisma";
import { requireAccount, readInput } from "../../../lib/session";
import { requireTrust } from "../../../lib/trust";

const Input = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("sim"),
    lineId: z.string().min(1),
    deviceName: z.string().trim().min(1, "Device name is required").max(60),
    iccid: z.string().regex(/^89\d{17,18}$/, "ICCID must be 19-20 digits starting with 89"),
  }),
  z.object({
    kind: z.literal("esim"),
    lineId: z.string().min(1),
    deviceName: z.string().trim().min(1, "Device name is required").max(60),
  }),
]);

// Fictional eSIM profile: 8999 prefix is not a real issuer.
const fakeEsimIccid = () => "8999" + Array.from({ length: 15 }, () => randomInt(10)).join("");

export default defineEventHandler(async (event) => {
  await requireTrust(event, "critical");
  const { account } = await requireAccount(event);
  const input = await readInput(event, Input);

  const simIccid = input.kind === "sim" ? input.iccid : fakeEsimIccid();
  const { count } = await prisma.line.updateMany({
    where: { id: input.lineId, accountId: account.id },
    data: { simIccid, deviceName: input.deviceName },
  });
  if (!count) throw createError({ statusCode: 404, statusMessage: "Line not found" });
  return { ok: true, simIccidLast4: simIccid.slice(-4) };
});
