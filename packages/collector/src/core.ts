// Collector core (ARCHITECTURE.md section 6). Framework-agnostic, zero dependencies.
// Captures timing and motion only: KeyboardEvent.code is hashed and classified, KeyboardEvent.key and
// input values are never read.

import type { CollectorEvent, KeyClass, TelemetryBatch } from "./schema.js";

export interface CollectorOptions {
  endpoint?: string; // default "/api/telemetry"
  flushMs?: number; // default 3000
  maxBatch?: number; // default 200
  mouseThrottleMs?: number; // default 20 (~50 Hz)
  // Observability hooks (e.g. a dev overlay). They see exactly what is sent, nothing more.
  onEvent?: (e: CollectorEvent) => void;
  onBatch?: (info: BatchInfo) => void;
}

export interface BatchInfo {
  seq: number;
  events: number;
  kinds: Partial<Record<CollectorEvent["k"], number>>;
  synthetic: number;
  bytes: number;
  transport: "fetch" | "beacon";
  status?: number; // HTTP status (fetch only); 0 on network error
  ms?: number; // round-trip time (fetch only)
  response?: Response;
}

export interface Collector {
  start(): void;
  stop(): void;
  flush(): Promise<void>; // settles once this and every earlier in-flight batch has been answered
  setRoute(path: string): void;
  readonly running: boolean;
}

const now = () => Math.round(performance.now() * 10) / 10;

export function keyClass(code: string): KeyClass {
  if (code.startsWith("Key")) return "letter";
  if (code.startsWith("Digit") || /^Numpad\d$/.test(code)) return "digit";
  if (code === "Space") return "space";
  if (code === "Backspace") return "backspace";
  if (code === "Enter" || code === "NumpadEnter") return "enter";
  if (/^(Shift|Control|Alt|Meta|CapsLock)/.test(code)) return "modifier";
  if (/^(Arrow|Page)/.test(code) || ["Tab", "Home", "End", "Escape"].includes(code)) return "nav";
  return "other";
}

// FNV-1a over KeyboardEvent.code, folded to 16 bits. Stable per physical key, only used for pairing.
export function codeHash(code: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < code.length; i++) {
    h ^= code.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return ((h >>> 16) ^ h) & 0xffff;
}

// Element kind for focus events: tag plus input type / ARIA role. Never the value, name, or id.
function focusRole(el: EventTarget | null): string {
  if (!(el instanceof Element)) return "other";
  const tag = el.tagName.toLowerCase();
  if (tag === "input") return `input:${(el as HTMLInputElement).type || "text"}`;
  const role = el.getAttribute("role");
  return role ? `${tag}:${role}` : tag;
}

function uuid(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function createCollector(opts: CollectorOptions = {}): Collector {
  const endpoint = opts.endpoint ?? "/api/telemetry";
  const flushMs = opts.flushMs ?? 3000;
  const maxBatch = opts.maxBatch ?? 200;
  const throttleMs = opts.mouseThrottleMs ?? 20;

  const pageId = uuid();
  let seq = 0;
  let events: CollectorEvent[] = [];
  let synthetic = 0;
  let lastMove = -Infinity;
  const lastTouchMove = new Map<number, number>(); // touch id -> last tm time
  let timer: ReturnType<typeof setInterval> | undefined;
  let running = false;
  const inflight = new Set<Promise<void>>();

  function push(e: CollectorEvent) {
    events.push(e);
    opts.onEvent?.(e);
    if (events.length >= maxBatch) flush();
  }

  // Untrusted (script-dispatched) events are counted for bot detection, never recorded.
  function trusted(e: Event): boolean {
    if (e.isTrusted) return true;
    synthetic++;
    return false;
  }

  function takeBatch(transport: BatchInfo["transport"]): { body: string; info: BatchInfo } | null {
    if (events.length === 0 && synthetic === 0) return null;
    const kinds: BatchInfo["kinds"] = {};
    for (const e of events) kinds[e.k] = (kinds[e.k] ?? 0) + 1;
    const batch: TelemetryBatch = {
      v: 1,
      pageId,
      seq: ++seq,
      vw: window.innerWidth,
      vh: window.innerHeight,
      events,
    };
    if (synthetic) batch.synthetic = synthetic;
    const body = JSON.stringify(batch);
    const info: BatchInfo = { seq: batch.seq, events: events.length, kinds, synthetic, bytes: body.length, transport };
    events = [];
    synthetic = 0;
    return { body, info };
  }

  function flush(): Promise<void> {
    const taken = takeBatch("fetch");
    if (taken) send(taken);
    return Promise.all(inflight).then(() => {});
  }

  function send(taken: { body: string; info: BatchInfo }) {
    const started = performance.now();
    const done = (status: number, response?: Response) =>
      opts.onBatch?.({ ...taken.info, status, ms: Math.round(performance.now() - started), response });
    const p: Promise<void> = fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: taken.body,
      keepalive: true,
    })
      .then((r) => done(r.status, r), () => done(0)) // best effort; the server treats missing telemetry as risk
      .finally(() => inflight.delete(p));
    inflight.add(p);
  }

  // pagehide: sendBeacon survives unload. text/plain keeps it a CORS-simple request.
  function beacon() {
    const taken = takeBatch("beacon");
    if (!taken) return;
    navigator.sendBeacon(endpoint, new Blob([taken.body], { type: "text/plain" }));
    opts.onBatch?.(taken.info);
  }

  const onKey = (e: KeyboardEvent) => {
    if (!trusted(e) || e.repeat) return;
    push({ k: e.type === "keydown" ? "kd" : "ku", t: now(), kc: keyClass(e.code), code_hash: codeHash(e.code) });
  };
  // Mouse goes through pointer events filtered to pointerType "mouse": on touch screens the browser also
  // fires emulated mouse events after a tap, which would otherwise pollute the mouse modality.
  // Pen input is ignored for now.
  const onMove = (e: PointerEvent) => {
    if (e.pointerType !== "mouse" || !trusted(e)) return;
    const t = now();
    if (t - lastMove < throttleMs) return;
    lastMove = t;
    push({ k: "mm", t, x: Math.round(e.clientX), y: Math.round(e.clientY) });
  };
  const onButton = (e: PointerEvent) => {
    if (e.pointerType !== "mouse" || !trusted(e)) return;
    push({ k: e.type === "pointerdown" ? "md" : "mu", t: now(), x: Math.round(e.clientX), y: Math.round(e.clientY), b: e.button });
  };
  // Touch uses TouchEvents, not pointer events: pointer streams are cancelled once the browser starts
  // scrolling, and swipes/scrolls are most of the touch signal. One event per changed touch point.
  // r = contact radius in px, f = force 0..1 (0 where the hardware doesn't report it).
  const onTouch = (e: TouchEvent) => {
    if (!trusted(e)) return;
    const t = now();
    const k = e.type === "touchstart" ? "ts" : e.type === "touchmove" ? "tm" : "te";
    for (const p of Array.from(e.changedTouches)) {
      const id = p.identifier & 0xffff;
      if (k === "tm") {
        if (t - (lastTouchMove.get(id) ?? -Infinity) < throttleMs) continue;
        lastTouchMove.set(id, t);
      } else if (k === "te") {
        lastTouchMove.delete(id);
      }
      push({
        k, t, id,
        x: Math.round(p.clientX),
        y: Math.round(p.clientY),
        r: Math.round(Math.max(p.radiusX || 0, p.radiusY || 0) * 10) / 10,
        f: Math.round((p.force || 0) * 1000) / 1000,
      });
    }
  };
  const onWheel = (e: WheelEvent) => {
    if (!trusted(e)) return;
    push({ k: "wh", t: now(), dy: Math.round(e.deltaY) });
  };
  const onFocus = (e: FocusEvent) => {
    if (!trusted(e)) return;
    push({ k: "fc", t: now(), role: focusRole(e.target) });
  };
  const onHidden = () => {
    if (document.visibilityState === "hidden") beacon();
  };

  const listeners: [EventTarget, string, EventListener][] = [
    [window, "keydown", onKey as EventListener],
    [window, "keyup", onKey as EventListener],
    [window, "pointermove", onMove as EventListener],
    [window, "pointerdown", onButton as EventListener],
    [window, "pointerup", onButton as EventListener],
    [window, "touchstart", onTouch as EventListener],
    [window, "touchmove", onTouch as EventListener],
    [window, "touchend", onTouch as EventListener],
    [window, "touchcancel", onTouch as EventListener],
    [window, "wheel", onWheel as EventListener],
    [window, "focusin", onFocus as EventListener],
    [window, "pagehide", beacon],
    [document, "visibilitychange", onHidden],
  ];

  return {
    get running() {
      return running;
    },
    start() {
      if (running) return;
      running = true;
      for (const [target, type, fn] of listeners) target.addEventListener(type, fn, { capture: true, passive: true });
      timer = setInterval(flush, flushMs);
    },
    // Drops anything buffered: after sign-out there is no session to attribute it to.
    stop() {
      if (!running) return;
      running = false;
      for (const [target, type, fn] of listeners) target.removeEventListener(type, fn, { capture: true });
      clearInterval(timer);
      events = [];
      synthetic = 0;
    },
    flush,
    setRoute(path: string) {
      if (running) push({ k: "nv", t: now(), route: path });
    },
  };
}
