// The signed-in customer's inbox, newest first, with scam verdicts (ARCHITECTURE.md 7.6). Tier: view.
import { ensureInbox } from "../../lib/messages";
import { prisma } from "../../lib/prisma";
import { requireSession } from "../../lib/session";

export default defineEventHandler(async (event) => {
  const { user } = await requireSession(event);
  await ensureInbox(user.id);
  const rows = await prisma.message.findMany({ where: { userId: user.id }, orderBy: { receivedAt: "desc" }, take: 50 });
  return rows.map((m) => ({
    id: m.id,
    sender: m.sender,
    body: m.body,
    receivedAt: m.receivedAt,
    verdict: m.verdict,
    scamProbability: m.scamProbability,
    categoryLabel: m.categoryLabel,
    advice: m.advice,
    redFlags: JSON.parse(m.redFlags) as { id: string; label: string }[],
    customerVerdict: m.customerVerdict,
  }));
});
