// Vanilla adapter for non-framework pages:
//   <script type="module" src="/collector/vanilla.js" data-mousetrap data-endpoint="/api/telemetry"></script>
// Auto-starts, reports the initial path and history navigations. Exposes window.mousetrapCollector.

import { createCollector, type Collector } from "../core.js";

declare global {
  interface Window {
    mousetrapCollector?: Collector;
  }
}

export function autoStart(script: HTMLScriptElement | null = document.currentScript as HTMLScriptElement | null): Collector {
  const ds = script?.dataset ?? {};
  const collector = createCollector({
    endpoint: ds.endpoint,
    flushMs: ds.flushMs ? Number(ds.flushMs) : undefined,
  });
  collector.start();
  collector.setRoute(location.pathname);

  const report = () => collector.setRoute(location.pathname);
  for (const method of ["pushState", "replaceState"] as const) {
    const original = history[method];
    history[method] = function (this: History, ...args: Parameters<History["pushState"]>) {
      original.apply(this, args);
      report();
    };
  }
  window.addEventListener("popstate", report);

  window.mousetrapCollector = collector;
  return collector;
}

// Module scripts have no document.currentScript; fall back to locating our own tag.
if (typeof window !== "undefined" && !window.mousetrapCollector) {
  autoStart(
    (document.currentScript as HTMLScriptElement | null) ??
      document.querySelector<HTMLScriptElement>("script[data-mousetrap]"),
  );
}
