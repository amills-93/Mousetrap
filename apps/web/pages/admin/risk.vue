<script setup lang="ts">
// Demo-only: every active session's live risk plus a decision timeline (ARCHITECTURE.md 7.3).
const { demoMode } = useRuntimeConfig().public;
if (!demoMode) throw createError({ statusCode: 404, statusMessage: "Not found", fatal: true });

type Row = {
  id: string;
  email: string;
  userAgent: string | null;
  ipAddress: string | null;
  risk: number | null;
  windows: number;
  components: Record<string, number>;
  bot: number;
  critical: "allow" | "step_up" | "pause" | "deny";
  coaching: { score: number; reasons: string[] };
  profileActive: boolean;
  stepUpUntil: string | null;
  failedStepUp: number;
  events: { type: string; tier: string | null; risk: number | null; route: string | null; at: string }[];
};

const data = ref<{ sessions: Row[]; critical: { stepUp: number; deny: number }; mlAvailable: boolean } | null>(null);
const selected = ref<string | null>(null);
let timer: ReturnType<typeof setInterval>;
async function load() {
  try {
    data.value = await $fetch("/api/admin/risk");
    if (!selected.value || !data.value.sessions.some((s) => s.id === selected.value)) {
      selected.value = data.value.sessions[0]?.id ?? null;
    }
  } catch {}
}
onMounted(() => {
  load();
  timer = setInterval(load, 2000);
});
onBeforeUnmount(() => clearInterval(timer));

const current = computed(() => data.value?.sessions.find((s) => s.id === selected.value) ?? null);

const DECISION = {
  allow: "bg-emerald-100 text-emerald-800",
  step_up: "bg-amber-100 text-amber-800",
  deny: "bg-red-100 text-red-800",
  pause: "bg-violet-100 text-violet-800",
  pause_reported: "bg-violet-100 text-violet-800",
  pause_held: "bg-violet-100 text-violet-800",
  stepup_ok: "bg-sky-100 text-sky-800",
  stepup_failed: "bg-red-100 text-red-800",
  typing_ok: "bg-sky-100 text-sky-800",
  typing_failed: "bg-red-100 text-red-800",
  score: "bg-gray-100 text-ink-soft",
} as Record<string, string>;
const LABEL: Record<string, string> = { allow: "allow", step_up: "step-up", pause: "pause", pause_reported: "reported scam", pause_held: "held", deny: "deny", stepup_ok: "verified", stepup_failed: "wrong code", typing_ok: "typing ok", typing_failed: "typing mismatch", score: "score" };

const riskClass = (r: number | null) => {
  const t = data.value?.critical;
  if (r === null || !t) return "text-ink-muted/70";
  return r >= t.deny ? "text-red-600" : r >= t.stepUp ? "text-amber-600" : "text-emerald-600";
};
const time = (d: string) => new Date(d).toLocaleTimeString("en-US", { hour12: false });
const browser = (ua: string | null) => (ua ? (ua.match(/(Firefox|Edg|Chrome|Safari)\/[\d.]+/)?.[0] ?? ua.slice(0, 30)) : "—");

// Score series for the sparkline: x = time, y = risk.
const chart = computed(() => {
  const ev = current.value?.events ?? [];
  const pts = ev.filter((e) => e.risk !== null).map((e) => ({ t: new Date(e.at).getTime(), r: e.risk as number, type: e.type }));
  if (pts.length < 2) return null;
  const t0 = pts[0].t;
  const span = Math.max(1, pts[pts.length - 1].t - t0);
  const x = (t: number) => ((t - t0) / span) * 600;
  const y = (r: number) => 120 - Math.min(1, r) * 120;
  return {
    line: pts.filter((p) => p.type === "score").map((p) => `${x(p.t).toFixed(1)},${y(p.r).toFixed(1)}`).join(" "),
    marks: pts.filter((p) => p.type !== "score").map((p) => ({ x: x(p.t), y: y(p.r), type: p.type })),
    y,
  };
});
const MARK_FILL: Record<string, string> = { allow: "#10b981", step_up: "#f59e0b", pause: "#8b5cf6", deny: "#ef4444" };
</script>

<template>
  <div class="space-y-5">
    <PageHeader eyebrow="Demo only" title="Risk console" subtitle="Every active session's live risk and the policy's decisions.">
      <span class="badge bg-emerald-50 text-emerald-700"><span class="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />Live · every 2 s</span>
    </PageHeader>
    <p v-if="data && !data.mlAvailable" class="notice border border-amber-200 bg-amber-50 text-amber-900"><Icon name="alert" :size="18" class="mt-px" />ML service unreachable: critical actions require step-up.</p>

    <Card title="Active sessions">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-xs uppercase tracking-wider text-ink-muted">
            <tr>
              <th class="py-2 pr-3 font-medium">Session</th>
              <th class="py-2 pr-3 font-medium">User</th>
              <th class="py-2 pr-3 font-medium">Browser</th>
              <th class="py-2 pr-3 font-medium text-right">Risk</th>
              <th class="py-2 pr-3 font-medium text-right">Windows</th>
              <th class="py-2 pr-3 font-medium">Components</th>
              <th class="py-2 pr-3 font-medium">SIM swap</th>
              <th class="py-2 font-medium">Step-up</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in data?.sessions ?? []"
              :key="s.id"
              class="cursor-pointer border-t border-ink-line transition hover:bg-ink-wash/60"
              :class="s.id === selected ? 'bg-nimbus-50/70' : ''"
              @click="selected = s.id"
            >
              <td class="py-2.5 pr-3 font-mono text-xs">{{ s.id }}</td>
              <td class="py-2.5 pr-3">{{ s.email }}<span v-if="!s.profileActive" class="ml-1 text-xs text-ink-muted/70">(learning)</span></td>
              <td class="py-2.5 pr-3 text-ink-muted">{{ browser(s.userAgent) }}</td>
              <td class="py-2.5 pr-3 text-right font-mono font-semibold" :class="riskClass(s.risk)">{{ s.risk?.toFixed(2) ?? "—" }}</td>
              <td class="py-2.5 pr-3 text-right font-mono">{{ s.windows }}</td>
              <td class="py-2.5 pr-3 font-mono text-xs text-ink-soft">
                <span v-for="(v, k) in s.components" :key="k" class="mr-2">{{ k }} {{ v.toFixed(2) }}</span>
                <span v-if="s.bot" class="text-red-600">bot +{{ s.bot.toFixed(1) }}</span>
                <span v-if="s.coaching.score" class="text-violet-700" :title="s.coaching.reasons.join(', ')">coaching {{ s.coaching.score.toFixed(2) }}</span>
              </td>
              <td class="py-2.5 pr-3"><span class="badge" :class="DECISION[s.critical]">{{ LABEL[s.critical] }}</span></td>
              <td class="py-2.5 text-xs text-ink-muted">
                <span v-if="s.stepUpUntil && new Date(s.stepUpUntil) > new Date()">verified until {{ time(s.stepUpUntil) }}</span>
                <span v-if="s.failedStepUp" class="text-red-600"> {{ s.failedStepUp }} failed</span>
              </td>
            </tr>
            <tr v-if="data && !data.sessions.length"><td colspan="8" class="py-3 text-ink-muted">No active sessions.</td></tr>
          </tbody>
        </table>
      </div>
    </Card>

    <Card v-if="current" :title="`Timeline · ${current.email} · ${current.id}`">
      <svg v-if="chart" viewBox="-4 -4 608 128" class="h-40 w-full rounded-xl bg-ink-wash/60" preserveAspectRatio="none">
        <line x1="0" x2="600" :y1="chart.y(data!.critical.stepUp)" :y2="chart.y(data!.critical.stepUp)" stroke="#f59e0b" stroke-dasharray="4 4" stroke-width="1" vector-effect="non-scaling-stroke" />
        <line x1="0" x2="600" :y1="chart.y(data!.critical.deny)" :y2="chart.y(data!.critical.deny)" stroke="#ef4444" stroke-dasharray="4 4" stroke-width="1" vector-effect="non-scaling-stroke" />
        <polyline :points="chart.line" fill="none" stroke="#2B2D7C" stroke-width="2.5" vector-effect="non-scaling-stroke" />
        <circle v-for="(m, i) in chart.marks" :key="i" :cx="m.x" :cy="m.y" r="4" :fill="MARK_FILL[m.type] ?? '#6b7280'" />
      </svg>
      <p v-else class="text-sm text-ink-muted">Not enough scores yet for a chart.</p>
      <p class="mt-1 text-xs text-ink-muted">Line: session risk. Dashed: critical step-up ({{ data?.critical.stepUp }}) and deny ({{ data?.critical.deny }}). Dots: policy decisions.</p>

      <ul class="mt-4 max-h-80 space-y-1 overflow-y-auto text-sm">
        <li v-for="(e, i) in [...current.events].reverse().filter((e) => e.type !== 'score')" :key="i" class="flex items-center gap-3">
          <span class="w-20 font-mono text-xs text-ink-muted">{{ time(e.at) }}</span>
          <span class="badge w-24 justify-center" :class="DECISION[e.type]">{{ LABEL[e.type] ?? e.type }}</span>
          <span class="w-16 text-xs text-ink-muted">{{ e.tier ?? "" }}</span>
          <span class="w-12 text-right font-mono text-xs" :class="riskClass(e.risk)">{{ e.risk?.toFixed(2) ?? "—" }}</span>
          <span class="truncate font-mono text-xs text-ink-muted">{{ e.route ?? "" }}</span>
        </li>
        <li v-if="!current.events.some((e) => e.type !== 'score')" class="text-ink-muted">No decisions yet. Try a sensitive action.</li>
      </ul>
    </Card>
  </div>
</template>
