// Seed: 3 fictional users (ARCHITECTURE.md section 11), each with a CustomerAccount, lines, 6 months of bills,
// and TOTP enabled. Idempotent: re-running deletes and recreates the demo users.
//
// TOTP secrets are derived from BETTER_AUTH_SECRET + email, so they stay the same across reseeds
// (your authenticator app keeps working) but are not committed to the repo.
//
// Run: docker compose run --rm seed   (or on host: pnpm --filter web db:seed with DATABASE_URL/BETTER_AUTH_SECRET set)
import { createHmac } from "node:crypto";
import { symmetricEncrypt } from "better-auth/crypto";
import qrcode from "qrcode-terminal";
import { auth } from "../server/lib/auth";
import { prisma } from "../server/lib/prisma";

const PASSWORD = "Password123!";
const ISSUER = "Nimbus Mobile Demo";
const PLANS = ["Nimbus Unlimited", "Nimbus Essentials", "Nimbus Basic"];

const USERS = [
  {
    email: "alex@nimbus.demo",
    name: "Alex Rivera",
    lines: [
      { nickname: "Alex", plan: PLANS[0], deviceName: "Nimbus Phone 12", dataUsedGb: 18.4 },
      { nickname: "Tablet", plan: PLANS[1], deviceName: "Slate Tab 8", dataUsedGb: 3.1 },
    ],
  },
  {
    email: "jordan@nimbus.demo",
    name: "Jordan Lee",
    lines: [
      { nickname: "Jordan", plan: PLANS[0], deviceName: "Nimbus Phone 12 Pro", dataUsedGb: 27.9 },
      { nickname: "Casey", plan: PLANS[1], deviceName: "Nimbus Phone 11", dataUsedGb: 9.6 },
      { nickname: "Kid's phone", plan: PLANS[2], deviceName: "Nimbus Phone Mini", dataUsedGb: 1.2 },
    ],
  },
  {
    email: "sam@nimbus.demo",
    name: "Sam Patel",
    lines: [
      { nickname: "Sam", plan: PLANS[1], deviceName: "Nimbus Phone 11", dataUsedGb: 12.0 },
      { nickname: "Work", plan: PLANS[0], deviceName: "Nimbus Phone 12", dataUsedGb: 22.5 },
      { nickname: "Watch", plan: PLANS[2], deviceName: "Nimbus Watch 3", dataUsedGb: 0.4 },
      { nickname: "Hotspot", plan: PLANS[1], deviceName: "Nimbus Hotspot", dataUsedGb: 31.7 },
    ],
  },
];

const PLAN_PRICE: Record<string, number> = { "Nimbus Unlimited": 70, "Nimbus Essentials": 50, "Nimbus Basic": 30 };

// RFC 4648 base32, no padding (what authenticator apps expect in otpauth URIs).
function base32(bytes: Uint8Array): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = 0, value = 0, out = "";
  for (const b of bytes) {
    value = (value << 8) | b;
    bits += 8;
    while (bits >= 5) {
      out += alphabet[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) out += alphabet[(value << (5 - bits)) & 31];
  return out;
}

async function resetUser(email: string) {
  const existing = await prisma.user.findUnique({ where: { email } });
  if (!existing) return;
  const userId = existing.id;
  const account = await prisma.customerAccount.findUnique({ where: { userId } });
  if (account) {
    await prisma.line.deleteMany({ where: { accountId: account.id } });
    await prisma.bill.deleteMany({ where: { accountId: account.id } });
    await prisma.customerAccount.delete({ where: { id: account.id } });
  }
  await prisma.biometricProfile.deleteMany({ where: { userId } });
  await prisma.sessionTrust.deleteMany({ where: { userId } });
  await prisma.stepUpFactor.deleteMany({ where: { userId } });
  await prisma.riskEvent.deleteMany({ where: { userId } });
  await prisma.user.delete({ where: { id: userId } }); // cascades sessions, accounts, twoFactor
}

async function main() {
  const authSecret = process.env.BETTER_AUTH_SECRET;
  if (!authSecret) throw new Error("BETTER_AUTH_SECRET must be set (it encrypts the TOTP secrets)");
  const ctx = await auth.$context;

  const printed: { email: string; uri: string }[] = [];

  for (const [i, u] of USERS.entries()) {
    await resetUser(u.email);

    const { user } = await auth.api.signUpEmail({ body: { email: u.email, password: PASSWORD, name: u.name } });
    await prisma.session.deleteMany({ where: { userId: user.id } }); // drop the auto sign-in session

    // TOTP, stored exactly as the twoFactor plugin stores a verified secret: the raw secret string is
    // the HMAC key (as UTF-8), encrypted with the auth secret.
    const totpSecret = createHmac("sha256", authSecret).update(`totp:${u.email}`).digest("hex").slice(0, 32);
    await prisma.twoFactor.create({
      data: {
        id: crypto.randomUUID(),
        userId: user.id,
        secret: await symmetricEncrypt({ key: ctx.secretConfig, data: totpSecret }),
        backupCodes: await symmetricEncrypt({ key: ctx.secretConfig, data: "[]" }),
        verified: true,
      },
    });
    await prisma.user.update({ where: { id: user.id }, data: { twoFactorEnabled: true, emailVerified: true } });

    const uri =
      `otpauth://totp/${encodeURIComponent(ISSUER)}:${encodeURIComponent(u.email)}?` +
      new URLSearchParams({ secret: base32(new TextEncoder().encode(totpSecret)), issuer: ISSUER, digits: "6", period: "30" });
    printed.push({ email: u.email, uri });

    // Fictional account data: NM- account numbers, 555-01xx numbers, 8999-prefixed ICCIDs.
    const n = i + 1;
    const account = await prisma.customerAccount.create({
      data: {
        userId: user.id,
        accountNumber: `NM-${String(100200300 + n * 111).padStart(9, "0")}`,
        portPin: String(400000 + n * 1357).slice(0, 6),
        autopay: n === 2,
        lines: {
          create: u.lines.map((l, j) => ({
            ...l,
            phone: `(214) 555-01${String(n * 10 + j).padStart(2, "0")}`,
            simIccid: `8999${String(n).padStart(2, "0")}${String(j + 1).padStart(2, "0")}${"0".repeat(10)}${n}${j}`,
          })),
        },
      },
    });

    const monthly = u.lines.reduce((sum, l) => sum + PLAN_PRICE[l.plan], 0);
    const now = new Date();
    await prisma.bill.createMany({
      data: Array.from({ length: 6 }, (_, k) => {
        const due = new Date(now.getFullYear(), now.getMonth() - k, 21);
        return {
          accountId: account.id,
          period: due.toLocaleString("en-US", { month: "long", year: "numeric" }),
          amount: (monthly + 12.37 + k * 0.5).toFixed(2),
          dueDate: due,
          paid: k > 0, // current month is due
        };
      }),
    });

    await prisma.biometricProfile.create({ data: { userId: user.id, status: "none" } });
  }

  console.log(`\nSeeded ${USERS.length} users. Password for all: ${PASSWORD}\n`);
  for (const p of printed) {
    console.log(`${p.email}\n${p.uri}`);
    qrcode.generate(p.uri, { small: true });
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
