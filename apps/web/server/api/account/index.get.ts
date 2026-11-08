// Everything the portal pages render, for the signed-in user only. Tier: view.
// The port-out PIN is deliberately excluded; it is revealed via POST /api/account/security/port-pin.
import { prisma } from "../../lib/prisma";
import { requireAccount } from "../../lib/session";
import { PLANS, planFor } from "../../lib/plans";

export default defineEventHandler(async (event) => {
  const { session, account } = await requireAccount(event);

  const [lines, bills, authorizedUsers] = await Promise.all([
    prisma.line.findMany({ where: { accountId: account.id }, orderBy: { phone: "asc" } }),
    prisma.bill.findMany({ where: { accountId: account.id }, orderBy: { dueDate: "desc" } }),
    prisma.authorizedUser.findMany({ where: { accountId: account.id }, orderBy: { createdAt: "asc" } }),
  ]);

  const billRows = bills.map((b) => ({ id: b.id, period: b.period, amount: Number(b.amount), dueDate: b.dueDate, paid: b.paid }));

  return {
    user: { name: session.user.name, email: session.user.email },
    account: {
      accountNumber: account.accountNumber,
      autopay: account.autopay,
      address: { street: account.street, city: account.city, state: account.state, zip: account.zip },
    },
    lines: lines.map((l) => ({
      id: l.id,
      phone: l.phone,
      nickname: l.nickname,
      plan: l.plan,
      deviceName: l.deviceName,
      simIccidLast4: l.simIccid.slice(-4),
      dataUsedGb: l.dataUsedGb,
      dataAllowanceGb: planFor(l.plan).dataGb,
    })),
    bills: billRows,
    balanceDue: Math.round(billRows.filter((b) => !b.paid).reduce((sum, b) => sum + b.amount, 0) * 100) / 100,
    authorizedUsers: authorizedUsers.map((a) => ({ id: a.id, name: a.name, email: a.email, createdAt: a.createdAt })),
    plans: PLANS,
  };
});
