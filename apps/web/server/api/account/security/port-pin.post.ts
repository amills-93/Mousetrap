// Reveal the port-out PIN. POST (not GET) because revealing it is a sensitive action. Tier: critical.
import { requireAccount } from "../../../lib/session";
import { requireTrust } from "../../../lib/trust";

export default defineEventHandler(async (event) => {
  await requireTrust(event, "critical");
  const { account } = await requireAccount(event);
  return { portPin: account.portPin };
});
