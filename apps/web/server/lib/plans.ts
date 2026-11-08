// Fictional Nimbus plans. dataGb is the high-speed allowance shown in usage bars.
export const PLANS = [
  { name: "Nimbus Unlimited", price: 70, dataGb: 50 },
  { name: "Nimbus Essentials", price: 50, dataGb: 15 },
  { name: "Nimbus Basic", price: 30, dataGb: 5 },
] as const;

export type PlanName = (typeof PLANS)[number]["name"];
export const PLAN_NAMES = PLANS.map((p) => p.name) as [PlanName, ...PlanName[]];
export const planFor = (name: string) => PLANS.find((p) => p.name === name) ?? PLANS[PLANS.length - 1];
