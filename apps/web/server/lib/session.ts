import type { H3Event } from "h3";
import type { z } from "zod";
import { auth } from "./auth";
import { prisma } from "./prisma";

// Resolve the signed-in user from the Better Auth cookie. The client never names the user (principle 2).
export async function requireSession(event: H3Event) {
  const session = await auth.api.getSession({ headers: event.headers });
  if (!session) throw createError({ statusCode: 401, statusMessage: "Not signed in" });
  return session;
}

// The signed-in user's CustomerAccount. Every account route scopes its queries through this.
export async function requireAccount(event: H3Event) {
  const session = await requireSession(event);
  const account = await prisma.customerAccount.findUnique({ where: { userId: session.user.id } });
  if (!account) throw createError({ statusCode: 404, statusMessage: "No account for this user" });
  return { session, account };
}

// Validate a JSON body; 400 with the first issue's message on failure.
export async function readInput<S extends z.ZodType>(event: H3Event, schema: S): Promise<z.infer<S>> {
  const result = schema.safeParse(await readBody(event).catch(() => undefined));
  if (!result.success) {
    throw createError({ statusCode: 400, statusMessage: result.error.issues[0]?.message ?? "Invalid request" });
  }
  return result.data;
}
