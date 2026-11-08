<script setup lang="ts">
// DEMO_MODE-only panel showing exactly what the collector captures and sends. Client-only (see app.vue).
import type { CollectorEvent } from "@mousetrap-auth/collector";

const { $collector: collector, $collectorDebug: debug } = useNuxtApp();

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
      <span class="h-2 w-2 rounded-full" :class="view.running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'" />
      telemetry
    </button>

    <div v-else class="w-80 max-w-[calc(100vw-1.5rem)] rounded-lg bg-gray-900/90 shadow-xl ring-1 ring-white/10 backdrop-blur">
      <div class="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <span class="flex items-center gap-2 font-semibold">
          <span class="h-2 w-2 rounded-full" :class="view.running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'" />
          Mousetrap telemetry
        </span>
        <span class="flex items-center gap-3 text-gray-400">
          <span>{{ view.running ? `${view.pending} pending` : "stopped" }}</span>
          <button class="hover:text-white" title="Collapse" @click="open = false">✕</button>
        </span>
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
