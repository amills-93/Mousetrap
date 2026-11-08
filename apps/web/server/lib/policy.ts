// Trust policy (ARCHITECTURE.md 7.4). decide() is pure: /api/risk and requireTrust (Stage 7) both call it,
// so the overlay's meter and enforcement can never disagree. Keep this file free of Nuxt auto-imports.

export const TIERS = ["view", "standard", "elevated", "critical"] as const;
export type Tier = (typeof TIERS)[number];
export type Decision = "allow" | "step_up" | "deny";
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
  if (input.stepUpActive) return "allow";
  if (!input.profileActive) return tier === "critical" ? "step_up" : "allow";
  const risk = effectiveRisk(input, tier);
  if (risk >= t[tier].deny) return "deny";
  if (risk >= t[tier].stepUp) return "step_up";
  return "allow";
}

export function decideAll(input: TrustInput, t: Thresholds = thresholds()): Record<Tier, Decision> {
  return Object.fromEntries(TIERS.map((tier) => [tier, decide(input, tier, t)])) as Record<Tier, Decision>;
}
