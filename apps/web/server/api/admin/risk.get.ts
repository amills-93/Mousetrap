// Demo-only live view of every active session (ARCHITECTURE.md 7.3). Off unless DEMO_MODE=true.
import { decide, thresholds } from "../../lib/policy";
import { prisma } from "../../lib/prisma";
import { requireSession } from "../../lib/session";
import { loadTrust } from "../../lib/trust";

const short = (id: string) => id.slice(0, 8);

export default defineEventHandler(async (event) => {
  if (!useRuntimeConfig().public.demoMode) throw createError({ statusCode: 404, statusMessage: "Not found" });
  await requireSession(event);

  const sessions = await prisma.session.findMany({
    where: { expiresAt: { gt: new Date() } },
    include: { user: { select: { id: true, email: true } } },
    orderBy: { createdAt: "desc" },
    take: 25,
  });
  const ids = sessions.map((s) => s.id);
  const [events, trusts] = await Promise.all([
    prisma.riskEvent.findMany({ where: { sessionId: { in: ids } }, orderBy: { createdAt: "desc" }, take: 500 }),
    prisma.sessionTrust.findMany({ where: { sessionId: { in: ids } } }),
  ]);
  const trustBy = new Map(trusts.map((t) => [t.sessionId, t]));

  const rows = await Promise.all(
    sessions.map(async (s) => {
      const { input, ml, coaching } = await loadTrust(s.userId, s.id, { sessionCreatedAt: s.createdAt });
      const mine = events.filter((e) => e.sessionId === s.id);
      return {
        id: short(s.id),
        email: s.user.email,
        userAgent: s.userAgent,
        ipAddress: s.ipAddress,
        createdAt: s.createdAt,
        risk: ml?.risk ?? null,
        windows: input.windows,
        components: ml?.components ?? {},
        bot: ml?.bot ?? 0,
        critical: decide(input, "critical"),
        coaching,
        profileActive: input.profileActive,
        stepUpUntil: trustBy.get(s.id)?.stepUpUntil ?? null,
        failedStepUp: trustBy.get(s.id)?.failedStepUp ?? 0,
        // Oldest first for the timeline.
        events: mine
          .slice(0, 200)
          .reverse()
          .map((e) => ({ type: e.type, tier: e.tier, risk: e.risk, route: e.route, at: e.createdAt })),
      };
    }),
  );
  return { sessions: rows, critical: thresholds().critical, mlAvailable: rows.length === 0 || rows.some((r) => r.risk !== null) };
});
