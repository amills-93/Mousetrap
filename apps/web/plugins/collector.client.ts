// Runs the behavioral collector only while signed in and off public pages (ARCHITECTURE.md 6.2).
import { createCollector, trackRoutes } from "@mousetrap-auth/collector/vue";

const PUBLIC_ROUTES = new Set(["/login"]);

export default defineNuxtPlugin(() => {
  const router = useRouter();
  const session = authClient.useSession();
  const collector = createCollector({ endpoint: "/api/telemetry" });
  trackRoutes(collector, router);

  watch(
    () => [session.value.data?.session.id, router.currentRoute.value.path] as const,
    ([sessionId, path]) => {
      if (sessionId && !PUBLIC_ROUTES.has(path)) {
        if (!collector.running) {
          collector.start();
          collector.setRoute(path);
        }
      } else {
        collector.stop();
      }
    },
    { immediate: true },
  );

  return { provide: { collector } };
});
