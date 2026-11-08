// Where the signed-in user is in sign-up (pages/signup.vue): login created, customer account created,
// authenticator verified. Lets an abandoned sign-up resume at the right step after the next sign-in.
import { prisma } from "../../lib/prisma";
import { requireSession } from "../../lib/session";

export default defineEventHandler(async (event) => {
  const { user } = await requireSession(event);
  const account = await prisma.customerAccount.findUnique({ where: { userId: user.id }, select: { id: true } });
  const hasAccount = !!account;
  const twoFactor = !!user.twoFactorEnabled;
  return { name: user.name, hasAccount, twoFactor, complete: hasAccount && twoFactor };
});
