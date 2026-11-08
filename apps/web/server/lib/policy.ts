// Trust policy (ARCHITECTURE.md 7.4). decide() is pure: /api/risk and requireTrust (Stage 7) both call it,
// so the overlay's meter and enforcement can never disagree. Keep this file free of Nuxt auto-imports.

export const TIERS = ["view", "standard", "elevated", "critical"] as const;
export type Tier = (typeof TIERS)[number];
export type Decision = "allow" | "step_up" | "pause" | "deny";
export type Thresholds = Record<Tier, { stepUp: number; deny: number }>;

const DEFAULT_THRESHOLDS: Thresholds = {
  view: { stepUp: 1.01, deny: 1.01 }, // never blocks
  standard: { stepUp: 0.75, deny: 0.95 },
  elevated: { stepUp: 0.55, deny: 0.9 },
  critical: { stepUp: 0.35, deny: 0.8 },
};

export const MIN_WINDOWS = 3;
export const UNKNOWN_RISK = 0.6; // ML down or too little telemetry: forces step-up on elevated/critical (principle 4)

let cached: { raw: string; thresholds: Thresholds } | undefined;

// POLICY_THRESHOLDS_JSON overrides any subset, e.g. {"critical":{"stepUp":0.3}}. Invalid JSON is ignored.
export function thresholds(raw = process.env.POLICY_THRESHOLDS_JSON ?? ""): Thresholds {
  const hit = cached;
  if (hit && hit.raw === raw) return hit.thresholds;
  const out = structuredClone(DEFAULT_THRESHOLDS);
  if (raw.trim()) {
    try {
      const parsed = JSON.parse(raw) as Partial<Record<Tier, Partial<{ stepUp: number; deny: number }>>>;
      for (const tier of TIERS) {
        for (const k of ["stepUp", "deny"] as const) {
          const v = parsed?.[tier]?.[k];
          if (typeof v === "number" && Number.isFinite(v)) out[tier][k] = v;
        }
      }
    } catch {
      console.error("[policy] POLICY_THRESHOLDS_JSON is not valid JSON; using defaults");
    }
  }
  cached = { raw, thresholds: out };
  return out;
}

export interface TrustInput {
  risk: number | null; // session EWMA from ML; null when ML is unreachable
  windows: number; // windows ML has scored this session
  profileActive: boolean; // BiometricProfile.status === "active"
  stepUpActive: boolean; // SessionTrust.stepUpUntil > now
  coaching: number; // coachingScore().score: does this look like someone being talked through it?
  holdReleased: boolean; // a scam hold on this action has run its course (set per route by requireTrust)
}

// Coaching signals (ARCHITECTURE.md 7.5): ML counts them (coaching.py), this turns them into a 0..1 score with
// reasons for the overlay and /admin/risk. Hand-set rules, not a trained model: there is no data on coached users.
export interface CoachingSignals {
  pastes: number; // pastes into inputs, last 3 min
  tabSwitches: number; // left the page 1.5 s+ and came back, last 3 min
  longPauses: number; // 10 s+ silent pauses, last 3 min
  chunkedDigits: number; // gaps between spaced digit groups, last 3 min
  navs: number; // route changes this session
}

export const PAUSE_AT = 0.5;
export const FRESH_SESSION_MS = 5 * 60 * 1000;

export function coachingScore(c: CoachingSignals | null | undefined, sessionAgeMs: number): { score: number; reasons: string[] } {
  if (!c) return { score: 0, reasons: [] };
  const parts: [number, string][] = [];
  if (c.tabSwitches) parts.push([0.3 * Math.min(c.tabSwitches, 2), `left the page and came back ${c.tabSwitches}x`]);
  if (c.pastes) parts.push([0.3, "pasted into a field"]);
  if (c.chunkedDigits >= 2) parts.push([0.25, "digits entered in spaced groups"]);
  if (c.longPauses) parts.push([0.15, "long silent pause"]);
  if (sessionAgeMs < FRESH_SESSION_MS && c.navs <= 2) parts.push([0.2, "went straight here after signing in"]);
  const score = Math.min(1, parts.reduce((s, [w]) => s + w, 0));
  return { score: Math.round(score * 100) / 100, reasons: parts.map(([, r]) => r) };
}

// The risk the thresholds are compared against, after the unknown-risk rule (7.4 step 4).
export function effectiveRisk(input: TrustInput, tier: Tier): number {
  if (input.risk === null || input.windows < MIN_WINDOWS) {
    return tier === "elevated" || tier === "critical" ? UNKNOWN_RISK : 0;
  }
  return input.risk;
}

// 7.4 steps 2-5 plus the threshold comparison, with no side effects.
export function decide(input: TrustInput, tier: Tier, t: Thresholds = thresholds()): Decision {
  const risk = effectiveRisk(input, tier);
  // Deny wins even inside the step-up window: a fresh code does not excuse behavior that keeps looking foreign.
  if (input.profileActive && risk >= t[tier].deny) return "deny";
  // Someone being talked through a critical change is usually the real owner, so step-up would not stop it: warn
  // and hold instead (7.5). Needs no profile, and a recent step-up does not skip it.
  if (tier === "critical" && input.coaching >= PAUSE_AT && !input.holdReleased) return "pause";
  if (!input.profileActive) return input.stepUpActive || tier !== "critical" ? "allow" : "step_up";
  if (input.stepUpActive) return "allow";
  if (risk >= t[tier].stepUp) return "step_up";
  return "allow";
}

// Step-up typing challenge (ARCHITECTURE.md 5.3b). Mean keys risk of the phrase windows at or above this fails.
export const TYPING_MAX_RISK = 0.5;
// Log-only for now: on the Stage 5 data the free-text keys model fails the owner's own live typing 43-60% of the
// time at 0.5 and does not separate a second person, so a "fail" is recorded but changes nothing, and a "pass"
// earns no trust. Flip this once a phrase-specific model separates people.
export const TYPING_ENFORCE = false;

export interface TypingResult {
  keysModeled: boolean;
  started: boolean;
  windows: number;
  risk: number | null;
}

// skip: nothing to judge (ML down, or no keystroke model): TOTP alone decides, as before.
// retry: no phrase typing reached ML yet. fail: the typing does not look like the owner.
export function judgeTyping(r: TypingResult | null, max = TYPING_MAX_RISK): "pass" | "skip" | "retry" | "fail" {
  if (!r || !r.keysModeled) return "skip";
  if (!r.started || r.windows === 0 || r.risk === null) return "retry";
  return r.risk >= max ? "fail" : "pass";
}

export function decideAll(input: TrustInput, t: Thresholds = thresholds()): Record<Tier, Decision> {
  return Object.fromEntries(TIERS.map((tier) => [tier, decide(input, tier, t)])) as Record<Tier, Decision>;
}
