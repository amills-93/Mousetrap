<script setup lang="ts">
// DEMO_MODE-only panel: the server's risk view of this session (top) and exactly what the collector captures
// and sends (below). Client-only (see app.vue). Displays /api/risk as returned; makes no decisions itself.
import type { CollectorEvent } from "@mousetrap-auth/collector";

type Tier = "view" | "standard" | "elevated" | "critical";
type Decision = "allow" | "step_up" | "deny";
interface RiskView {
  risk: number | null;
  windows: number;
  components: Record<string, number>;
  bot: number;
  thresholds: Record<Tier, { stepUp: number; deny: number }>;
  decisions: Record<Tier, Decision>;
  criticalRisk: number;
  mlAvailable: boolean;
  profileActive: boolean;
  stepUpActive: boolean;
  locked: boolean;
}

const { $collector: collector, $collectorDebug: debug } = useNuxtApp();

const riskView = ref<RiskView | null>(null);
const riskError = ref(false);
let riskTimer: ReturnType<typeof setInterval>;
async function pollRisk() {
  if (!collector.running) {
    riskView.value = null;
    return;
  }
  try {
    riskView.value = await $fetch<RiskView>("/api/risk");
    riskError.value = false;
  } catch {
    riskError.value = true;
  }
}
onMounted(() => {
  pollRisk();
  riskTimer = setInterval(pollRisk, 2000);
});
onBeforeUnmount(() => clearInterval(riskTimer));

const TIER_LABELS: Record<Tier, string> = { view: "view", standard: "standard", elevated: "elevated", critical: "critical" };
const DECISION_CLASS = { allow: "text-emerald-400", step_up: "text-amber-300", deny: "text-red-400" } as const;
const DECISION_TEXT = { allow: "allow", step_up: "step-up", deny: "deny" } as const;

const meter = computed(() => {
  const r = riskView.value;
  if (!r) return null;
  const tiers = (Object.keys(r.thresholds) as Tier[]).filter((t) => r.thresholds[t].stepUp <= 1);
  const lowStepUp = Math.min(...tiers.map((t) => r.thresholds[t].stepUp));
  const lowDeny = Math.min(...tiers.map((t) => r.thresholds[t].deny));
  // Color bands come from the server's thresholds; the decision text comes from the server's decisions.
  const level = r.risk === null ? "none" : r.risk >= lowDeny ? "red" : r.risk >= lowStepUp ? "amber" : "green";
  const critical = r.decisions.critical;
  const status = critical === "allow" ? "SIM swap allowed" : critical === "step_up" ? "SIM swap would require step-up" : "SIM swap blocked";
  let reason = "";
  if (r.locked) reason = "session locked";
  else if (r.stepUpActive) reason = "recently verified";
  else if (!r.profileActive) reason = "not enrolled";
  else if (!r.mlAvailable) reason = "ML unavailable";
  else if (r.criticalRisk !== r.risk) reason = `warming up: judged as ${r.criticalRisk.toFixed(2)}`;
  return {
    risk: r.risk,
    pct: Math.round(Math.min(1, Math.max(0, r.risk ?? 0)) * 100),
    level,
    status,
    reason,
    critical,
    windows: r.windows,
    components: Object.entries(r.components) as [string, number][],
    bot: r.bot,
    tiers: tiers.map((t) => ({ tier: t, ...r.thresholds[t], decision: r.decisions[t] })),
  };
});

const LEVEL_BG = { green: "bg-emerald-400", amber: "bg-amber-300", red: "bg-red-500", none: "bg-gray-500" } as const;
const dotClass = computed(() => {
  void tick.value; // collector.running is not reactive
  if (!collector.running) return "bg-gray-500";
  return meter.value ? LEVEL_BG[meter.value.level] : "bg-emerald-400 animate-pulse";
});

const open = ref(true);
const tick = ref(0); // re-read the plain debug object a few times a second, not once per event
let timer: ReturnType<typeof setInterval>;
onMounted(() => {
  try {
    open.value = localStorage.getItem("mousetrap-overlay") !== "closed";
  } catch {}
  timer = setInterval(() => tick.value++, 150);
});
onBeforeUnmount(() => clearInterval(timer));
watch(open, (v) => {
  try {
    localStorage.setItem("mousetrap-overlay", v ? "open" : "closed");
  } catch {}
});

const view = computed(() => {
  void tick.value;
  const t = debug.totals;
  const sum = (...ks: (keyof typeof t)[]) => ks.reduce((n, k) => n + (t[k] ?? 0), 0);
  return {
    running: collector.running,
    pending: debug.pending,
    groups: [
      ["keys", sum("kd", "ku")],
      ["mouse", sum("mm", "md", "mu")],
      ["touch", sum("ts", "tm", "te")],
      ["wheel", sum("wh")],
      ["focus", sum("fc")],
      ["nav", sum("nv")],
      ["synthetic", sum("synthetic")],
    ] as const,
    recent: debug.recent.map(describe),
    batches: debug.batches.map((b) => ({ ...b })),
    trail: debug.trail.map((p) => `${p.x},${p.y}`).join(" "),
    vw: window.innerWidth,
    vh: window.innerHeight,
  };
});

function describe(e: CollectorEvent): string {
  switch (e.k) {
    case "kd":
    case "ku":
      return `${e.k}  ${e.kc.padEnd(9)} #${e.code_hash.toString(16).padStart(4, "0")}`;
    case "mm":
      return `mm  ${e.x},${e.y}`;
    case "md":
    case "mu":
      return `${e.k}  ${e.x},${e.y} btn${e.b}`;
    case "ts":
    case "tm":
    case "te":
      return `${e.k}  id${e.id} ${e.x},${e.y} r${e.r}${e.f ? ` f${e.f}` : ""}`;
    case "wh":
      return `wh  dy ${e.dy}`;
    case "fc":
      return `fc  ${e.role}`;
    case "nv":
      return `nv  ${e.route}`;
  }
}

const statusClass = (s?: number) =>
  s === undefined ? "text-gray-400" : s >= 200 && s < 300 ? "text-emerald-400" : "text-red-400";
</script>

<template>
  <div class="fixed bottom-3 left-3 z-50 font-mono text-[11px] leading-4 text-gray-200">
    <button
      v-if="!open"
      class="rounded-full bg-gray-900/90 px-3 py-1.5 shadow-lg ring-1 ring-white/10 flex items-center gap-2"
      @click="open = true"
    >
      <span class="h-2 w-2 rounded-full" :class="dotClass" />
      {{ meter?.risk != null ? `risk ${meter.risk.toFixed(2)}` : "telemetry" }}
    </button>

    <div v-else class="w-80 max-w-[calc(100vw-1.5rem)] rounded-lg bg-gray-900/90 shadow-xl ring-1 ring-white/10 backdrop-blur">
      <div class="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <span class="flex items-center gap-2 font-semibold">
          <span class="h-2 w-2 rounded-full" :class="dotClass" />
          Mousetrap
        </span>
        <span class="flex items-center gap-3 text-gray-400">
          <span>{{ view.running ? `${view.pending} pending` : "stopped" }}</span>
          <button class="hover:text-white" title="Collapse" @click="open = false">✕</button>
        </span>
      </div>

      <div class="px-3 py-2 border-b border-white/10">
        <template v-if="meter">
          <div class="flex items-baseline justify-between">
            <span class="text-gray-400">session risk</span>
            <span class="text-base font-semibold tabular-nums">{{ meter.risk != null ? meter.risk.toFixed(2) : "—" }}</span>
          </div>
          <div class="relative mt-1 h-2 rounded bg-white/10">
            <div class="absolute inset-y-0 left-0 rounded transition-all duration-500" :class="LEVEL_BG[meter.level]" :style="{ width: `${meter.pct}%` }" />
          </div>
          <div class="mt-2 space-y-0.5">
            <div v-for="t in meter.tiers" :key="t.tier" class="flex items-center gap-2">
              <span class="w-14 text-gray-400">{{ TIER_LABELS[t.tier] }}</span>
              <span class="relative h-1.5 flex-1 rounded bg-white/5">
                <span class="absolute -top-0.5 h-2.5 w-0.5 bg-amber-300" :style="{ left: `${t.stepUp * 100}%` }" :title="`step-up at ${t.stepUp}`" />
                <span class="absolute -top-0.5 h-2.5 w-0.5 bg-red-500" :style="{ left: `${Math.min(t.deny, 1) * 100}%` }" :title="`deny at ${t.deny}`" />
                <span v-if="meter.risk != null" class="absolute -top-1 h-3.5 w-px bg-white" :style="{ left: `${meter.pct}%` }" />
              </span>
              <span class="w-12 text-right" :class="DECISION_CLASS[t.decision]">{{ DECISION_TEXT[t.decision] }}</span>
            </div>
          </div>
          <p class="mt-2" :class="DECISION_CLASS[meter.critical]">
            {{ meter.status }}<span v-if="meter.reason" class="text-gray-400"> · {{ meter.reason }}</span>
          </p>
          <p class="mt-0.5 text-gray-400">
            {{ meter.windows }} windows
            <span v-for="[m, v] in meter.components" :key="m"> · {{ m }} {{ v.toFixed(2) }}</span>
            <span v-if="meter.bot" class="text-red-400"> · bot +{{ meter.bot.toFixed(1) }}</span>
          </p>
        </template>
        <p v-else-if="riskError" class="text-red-400">risk unavailable</p>
        <p v-else class="text-gray-500">{{ view.running ? "loading risk…" : "risk shown while signed in" }}</p>
      </div>

      <div class="px-3 py-2 flex flex-wrap gap-x-3 gap-y-1 border-b border-white/10">
        <span v-for="[label, n] in view.groups" :key="label" class="whitespace-nowrap" :class="label === 'synthetic' && n ? 'text-red-400' : ''">
          <span class="text-gray-400">{{ label }}</span> {{ n }}
        </span>
      </div>

      <div class="px-3 py-2 flex gap-3 border-b border-white/10">
        <svg :viewBox="`0 0 ${view.vw} ${view.vh}`" class="w-24 h-16 shrink-0 rounded bg-black/40" preserveAspectRatio="none">
          <polyline :points="view.trail" fill="none" stroke="#34d399" stroke-width="4" vector-effect="non-scaling-stroke" />
        </svg>
        <ul class="min-w-0 flex-1 overflow-hidden">
          <li v-for="(line, i) in view.recent" :key="i" class="truncate whitespace-pre" :class="i ? 'text-gray-400' : ''">{{ line }}</li>
          <li v-if="!view.recent.length" class="text-gray-500">no events yet</li>
        </ul>
      </div>

      <div class="px-3 py-2">
      <table class="w-full">
        <thead class="text-gray-500 text-left">
          <tr><th class="font-normal">seq</th><th class="font-normal">via</th><th class="font-normal">ev</th><th class="font-normal">bytes</th><th class="font-normal">http</th><th class="font-normal">ms</th><th class="font-normal">at ML</th></tr>
        </thead>
        <tbody>
          <tr v-for="b in view.batches" :key="b.seq">
            <td>#{{ b.seq }}</td>
            <td>{{ b.transport }}</td>
            <td>{{ b.events }}</td>
            <td>{{ b.bytes }}</td>
            <td :class="statusClass(b.status)">{{ b.status ?? "—" }}</td>
            <td>{{ b.ms ?? "—" }}</td>
            <td>{{ b.buffered ?? "—" }}</td>
          </tr>
          <tr v-if="!view.batches.length"><td colspan="7" class="text-gray-500">no batches yet (flush every 3 s)</td></tr>
        </tbody>
      </table>
      </div>

      <p class="px-3 pb-2 text-gray-500">Timing and motion only. Key values and input text are never captured.</p>
    </div>
  </div>
</template>
