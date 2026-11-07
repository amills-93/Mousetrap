// Reveal the port-out PIN. POST (not GET) because revealing it is a sensitive action. Tier: critical.
import { requireAccount } from "../../../lib/session";

export default defineEventHandler(async (event) => {
  const { account } = await requireAccount(event);
  // TODO(Stage 7): await requireTrust(event, "critical");
  return { portPin: account.portPin };
});
