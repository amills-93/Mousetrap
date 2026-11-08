// Runs the behavioral collector only while signed in and off public pages (ARCHITECTURE.md 6.2).
import { createCollector, trackRoutes, type BatchInfo } from "@mousetrap-auth/collector/vue";
import type { CollectorEvent } from "@mousetrap-auth/collector";

const PUBLIC_ROUTES = new Set(["/login"]);

// What the dev overlay shows. Plain (non-reactive) on purpose: events arrive at up to ~100/s, and the
// overlay re-reads this on its own timer instead of re-rendering per event.
export interface CollectorDebug {
  pending: number;
  totals: Partial<Record<CollectorEvent["k"] | "synthetic", number>>;
  recent: CollectorEvent[]; // newest first
  trail: { x: number; y: number }[]; // recent mouse/touch positions, oldest first
  batches: (Omit<BatchInfo, "response"> & { buffered?: number })[]; // newest first
}

function debugHooks(debug: CollectorDebug) {
  return {
    onEvent(e: CollectorEvent) {
      debug.pending++;
      debug.totals[e.k] = (debug.totals[e.k] ?? 0) + 1;
      debug.recent.unshift(e);
      if (debug.recent.length > 8) debug.recent.pop();
      if (e.k === "mm" || e.k === "tm" || e.k === "ts") {
        debug.trail.push({ x: e.x, y: e.y });
        if (debug.trail.length > 120) debug.trail.shift();
      }
    },
    onBatch({ response, ...info }: BatchInfo) {
      debug.pending = 0;
      if (info.synthetic) debug.totals.synthetic = (debug.totals.synthetic ?? 0) + info.synthetic;
      const row: CollectorDebug["batches"][number] = { ...info };
      debug.batches.unshift(row);
      if (debug.batches.length > 6) debug.batches.pop();
      if (response?.ok) response.json().then((b) => (row.buffered = b?.buffered), () => {});
    },
  };
}

export default defineNuxtPlugin(() => {
  const router = useRouter();
  const session = authClient.useSession();
  const debug: CollectorDebug = { pending: 0, totals: {}, recent: [], trail: [], batches: [] };
  const collector = createCollector({
    endpoint: "/api/telemetry",
    ...(useRuntimeConfig().public.demoMode ? debugHooks(debug) : {}),
  });
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
        debug.pending = 0;
      }
    },
    { immediate: true },
  );

  return { provide: { collector, collectorDebug: debug } };
});
