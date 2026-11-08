import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { twoFactor, multiSession } from "better-auth/plugins";
import { prisma } from "./prisma";

// BETTER_AUTH_SECRET and BETTER_AUTH_URL are read from process.env at runtime by Better Auth itself.
// Keep this file free of Nuxt auto-imports: the seed script and the Better Auth CLI import it directly.

// Set server-side by server/api/auth/[...all].ts; never trust a client-supplied X-Forwarded-For.
export const CLIENT_IP_HEADER = "x-mousetrap-client-ip";

export const auth = betterAuth({
  appName: "Nimbus Mobile Demo",
  database: prismaAdapter(prisma, { provider: "postgresql" }),
  emailAndPassword: { enabled: true },
  advanced: { ipAddress: { ipAddressHeaders: [CLIENT_IP_HEADER] } },
  plugins: [
    twoFactor({ issuer: "Nimbus Mobile Demo" }),
    multiSession({ maximumSessions: 5 }),
  ],
});

export type AuthSession = typeof auth.$Infer.Session;
