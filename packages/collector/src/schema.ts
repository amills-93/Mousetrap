// Event schema v1 (ARCHITECTURE.md section 6.1). Timing and motion only; never key values or input values.

export type KeyClass =
  | "letter" | "digit" | "space" | "backspace" | "enter" | "modifier" | "nav" | "other";

export type CollectorEvent =
  | { k: "kd"; t: number; kc: KeyClass; code_hash: number } // keydown
  | { k: "ku"; t: number; kc: KeyClass; code_hash: number } // keyup
  | { k: "mm"; t: number; x: number; y: number } // mousemove, throttled
  | { k: "md"; t: number; x: number; y: number; b: number } // mousedown
  | { k: "mu"; t: number; x: number; y: number; b: number } // mouseup
  | { k: "wh"; t: number; dy: number } // wheel
  | { k: "ts"; t: number; id: number; x: number; y: number; r: number; f: number } // touchstart
  | { k: "tm"; t: number; id: number; x: number; y: number; r: number; f: number } // touchmove, throttled per touch
  | { k: "te"; t: number; id: number; x: number; y: number; r: number; f: number } // touchend / touchcancel
  | { k: "fc"; t: number; role: string } // focus change: element role/type, never value
  | { k: "nv"; t: number; route: string }; // route change

export interface TelemetryBatch {
  v: 1;
  pageId: string;
  seq: number;
  vw: number;
  vh: number; // viewport size for normalizing coordinates
  synthetic?: number; // count of ignored untrusted events
  events: CollectorEvent[];
}
