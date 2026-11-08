// DEMO_MODE only: deliver a text to the signed-in customer, so judges can try their own wording live.
import { z } from "zod";
import { receive } from "../../lib/messages";
import { readInput, requireSession } from "../../lib/session";

const Input = z.object({
  sender: z.string().trim().min(1).max(40),
  body: z.string().trim().min(1, "Type a message").max(600),
});

export default defineEventHandler(async (event) => {
  if (!useRuntimeConfig().public.demoMode) throw createError({ statusCode: 404, statusMessage: "Not found" });
  const { user } = await requireSession(event);
  const { sender, body } = await readInput(event, Input);
  const m = await receive(user.id, sender, body);
  return { id: m.id, verdict: m.verdict };
});
