// Vue adapter. Structural types only, so the package stays dependency-free (no `vue` import).
// Usage: app.use(collectorPlugin, { router, endpoint: "/api/telemetry" }), then start()/stop() around auth.

import { createCollector, type Collector, type CollectorOptions } from "../core.js";

interface RouterLike {
  afterEach(guard: (to: { path: string }) => void): () => void;
}

interface AppLike {
  provide(key: string | symbol, value: unknown): unknown;
  config: { globalProperties: Record<string, unknown> };
}

export const COLLECTOR_KEY = Symbol.for("mousetrap-collector");

// Report every route change as an "nv" event. Returns the unsubscribe function.
export function trackRoutes(collector: Collector, router: RouterLike): () => void {
  return router.afterEach((to) => collector.setRoute(to.path));
}

export const collectorPlugin = {
  install(app: AppLike, opts: CollectorOptions & { router?: RouterLike } = {}) {
    const collector = createCollector(opts);
    if (opts.router) trackRoutes(collector, opts.router);
    app.provide(COLLECTOR_KEY, collector);
    app.config.globalProperties.$collector = collector;
  },
};

export { createCollector, type Collector, type CollectorOptions };
