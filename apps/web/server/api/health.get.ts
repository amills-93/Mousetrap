import { prisma } from "../lib/prisma";

export default defineEventHandler(async () => {
  const { mlUrl } = useRuntimeConfig();

  const db = await prisma.$queryRaw`SELECT 1`.then(() => true, () => false);
  const ml = await $fetch(`${mlUrl}/healthz`, { timeout: 1000 }).then(() => true, () => false);

  return { db, ml };
});
