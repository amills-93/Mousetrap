// Current session's risk plus the server's decision for every tier (ARCHITECTURE.md 7.3). The DevOverlay only
// displays this; it never compares risk to thresholds itself (principle 1).
import { decideAll, effectiveRisk, thresholds } from "../lib/policy";
import { requireSession } from "../lib/session";
import { loadTrust } from "../lib/trust";

export default defineEventHandler(async (event) => {
  const { user, session } = await requireSession(event);
  const { input, ml } = await loadTrust(user.id, session.id);
  const t = thresholds();
  return {
    risk: ml?.risk ?? null,
    windows: input.windows,
    lastUpdated: ml?.lastUpdated ?? null,
    components: ml?.components ?? {},
    bot: ml?.bot ?? 0,
    thresholds: t,
    decisions: decideAll(input, t),
    // Why a decision may not follow the bar: what critical actions are judged on right now.
    criticalRisk: effectiveRisk(input, "critical"),
    mlAvailable: ml !== null,
    profileActive: input.profileActive,
    stepUpActive: input.stepUpActive,
  };
});
