<script setup lang="ts">
// Biometric enrollment (ARCHITECTURE.md 7.3, 8.4). The collector is already running; while enrolling, ML files
// this user's windows into the enrollment buffer. What the user types here never leaves the browser.
type Status = {
  status: "none" | "enrolling" | "active";
  enrolling: boolean;
  windows: number;
  min: number;
  target: number;
  modelVersion: number;
  windowCount: number;
  mlAvailable: boolean;
};

const { $collector } = useNuxtApp();
const status = ref<Status | null>(null);
const error = ref("");
const busy = ref(false);

async function load() {
  try {
    status.value = await $fetch<Status>("/api/enroll/status");
  } catch (e: any) {
    error.value = e?.data?.statusMessage || "Could not load enrollment status";
  }
}

let poll: ReturnType<typeof setInterval> | undefined;
watch(
  () => status.value?.enrolling,
  (on) => {
    clearInterval(poll);
    if (on) poll = setInterval(load, 2000);
  },
);
onMounted(load);
onBeforeUnmount(() => clearInterval(poll));

const phase = computed(() => {
  const s = status.value;
  if (!s) return "loading";
  if (s.status === "active") return "done";
  return s.enrolling ? "collecting" : "consent";
});
const pct = computed(() => (status.value ? Math.min(100, (status.value.windows / status.value.target) * 100) : 0));
const canFinish = computed(() => !!status.value && status.value.windows >= status.value.min);

async function start() {
  busy.value = true;
  error.value = "";
  try {
    await $fetch("/api/enroll/start", { method: "POST" });
    await load();
  } catch (e: any) {
    error.value = e?.data?.statusMessage || "Could not start enrollment";
  } finally {
    busy.value = false;
  }
}

async function finish() {
  busy.value = true;
  error.value = "";
  try {
    $collector.flush(); // send the last few seconds before training
    await new Promise((r) => setTimeout(r, 1000));
    await $fetch("/api/enroll/finish", { method: "POST" });
    await load();
  } catch (e: any) {
    error.value = e?.data?.statusMessage || "Could not finish enrollment";
  } finally {
    busy.value = false;
  }
}

// --- Typing exercise: compared locally only, for the user's benefit.
const PASSAGE =
  "Nimbus keeps your lines connected wherever you go. Check your usage, pay your bill, and manage every device on your plan from one place. Your account is protected by how you type and move, not just by your password.";
const typed = ref("");
const typedOk = computed(() => {
  let n = 0;
  while (n < typed.value.length && typed.value[n] === PASSAGE[n]) n++;
  return n;
});

// --- Click-target exercise: hit the dot, it jumps somewhere else.
const target = reactive({ x: 50, y: 50, hits: 0 });
function hit() {
  target.hits++;
  target.x = 8 + Math.random() * 84;
  target.y = 10 + Math.random() * 80;
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <h1 class="text-2xl font-semibold text-nimbus">Behavioral security</h1>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <p v-if="status && !status.mlAvailable" class="text-sm text-amber-700">The scoring service is unreachable right now.</p>

    <p v-if="phase === 'loading'" class="text-sm text-gray-500">Loading…</p>

    <Card v-else-if="phase === 'done'" title="You're enrolled">
      <p class="text-sm text-gray-600">
        Your behavioral profile is active (model v{{ status!.modelVersion }}, trained on {{ status!.windowCount }} samples).
        Sensitive actions now check that it's really you at the keyboard.
      </p>
      <NuxtLink to="/" class="mt-4 inline-block rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">Back to overview</NuxtLink>
    </Card>

    <Card v-else-if="phase === 'consent'" title="Before you start">
      <div class="text-sm text-gray-700 space-y-2">
        <p>This is a demo. To learn how you use the portal, Nimbus records <strong>timing and motion only</strong>:</p>
        <ul class="list-disc pl-5 space-y-1">
          <li>how long keys are held and the gaps between them, and a coarse key type (letter, digit, backspace…)</li>
          <li>mouse and touch movement, clicks, and scrolling</li>
        </ul>
        <p>We never record which keys you press or anything you type. The exercise takes about a minute.</p>
      </div>
      <button :disabled="busy" class="mt-4 rounded bg-nimbus text-white px-4 py-2 text-sm font-medium disabled:opacity-50" @click="start">
        I agree, start enrollment
      </button>
    </Card>

    <template v-else>
      <Card>
        <div class="flex items-center justify-between text-sm mb-2">
          <span class="font-medium">Progress</span>
          <span class="text-gray-500">{{ status!.windows }} / {{ status!.target }} samples</span>
        </div>
        <div class="h-3 rounded-full bg-gray-100 overflow-hidden">
          <div class="h-full bg-nimbus-accent transition-all" :style="{ width: pct + '%' }" />
        </div>
        <div class="mt-4 flex items-center gap-3">
          <button :disabled="!canFinish || busy" class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium disabled:opacity-50" @click="finish">
            {{ busy ? "Training…" : "Finish enrollment" }}
          </button>
          <span class="text-xs text-gray-500">
            {{ canFinish ? (pct >= 100 ? "Ready." : "You can finish now; more samples make it more accurate.") : `At least ${status!.min} samples needed.` }}
          </span>
        </div>
      </Card>

      <Card title="1. Type this passage">
        <p class="text-sm text-gray-600 leading-relaxed">
          <span class="text-nimbus">{{ PASSAGE.slice(0, typedOk) }}</span><span>{{ PASSAGE.slice(typedOk) }}</span>
        </p>
        <!-- Not part of any form and never sent; the collector sees only key timing. -->
        <textarea v-model="typed" rows="4" autocomplete="off" autocorrect="off" spellcheck="false" placeholder="Start typing here…"
          class="mt-3 w-full rounded border border-gray-300 px-3 py-2 text-sm" />
        <button v-if="typedOk >= PASSAGE.length" class="mt-2 text-sm text-nimbus hover:underline" @click="typed = ''">Nice. Type it again</button>
      </Card>

      <Card title="2. Click the targets">
        <p class="text-sm text-gray-600 -mt-2 mb-3">Click (or tap) each dot as it appears. Hits: {{ target.hits }}</p>
        <div class="relative h-72 rounded-lg bg-gray-50 ring-1 ring-black/5 select-none">
          <button
            aria-label="Target"
            class="absolute h-8 w-8 -ml-4 -mt-4 rounded-full bg-nimbus-accent ring-4 ring-nimbus/20 hover:scale-110 transition-transform"
            :style="{ left: target.x + '%', top: target.y + '%' }"
            @click="hit"
          />
        </div>
      </Card>
    </template>
  </div>
</template>
