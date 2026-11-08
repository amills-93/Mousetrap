<script setup lang="ts">
// Texts with scam verdicts (ARCHITECTURE.md 7.6). The server classifies; this page only shows the result.
type Msg = {
  id: string;
  sender: string;
  body: string;
  receivedAt: string;
  verdict: "scam" | "suspicious" | "ok";
  scamProbability: number;
  categoryLabel: string | null;
  advice: string | null;
  redFlags: { id: string; label: string }[];
  customerVerdict: "reported" | "not_scam" | null;
};

const { demoMode } = useRuntimeConfig().public;
const { data: messages, refresh } = await useFetch<Msg[]>("/api/messages", { key: "messages" });
const open = ref<string | null>(null);

const ago = (d: string) => {
  const m = Math.round((Date.now() - new Date(d).getTime()) / 60_000);
  return m < 1 ? "now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};
// The model's confidence in words: honest about the band, without a false-precision percentage up front.
const confidence = (p: number) => (p >= 0.9 ? "very likely" : p >= 0.5 ? "likely" : "possibly");

async function feedback(m: Msg, action: "report" | "not_scam") {
  await $fetch(`/api/messages/${m.id}`, { method: "POST", body: { action } });
  await refresh();
}

// Demo: deliver your own text and see it screened.
const sender = ref("(555) 555-0199");
const body = ref("");
const sending = ref(false);
const sendErr = ref("");
async function simulate() {
  sending.value = true;
  sendErr.value = "";
  try {
    const r = await $fetch<{ id: string }>("/api/messages/simulate", { method: "POST", body: { sender: sender.value, body: body.value } });
    body.value = "";
    await refresh();
    open.value = r.id;
  } catch (e: any) {
    sendErr.value = e?.data?.statusMessage || "Could not deliver";
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-nimbus">Messages</h1>
      <p class="mt-1 text-sm text-gray-600">
        Nimbus Scam Shield checks incoming texts for scams. In this demo the texts are synthetic. On a real phone the check
        would run on the device and Nimbus would never see your messages.
      </p>
    </div>

    <Card v-if="demoMode" title="Demo: receive a text">
      <form class="flex flex-col gap-2 sm:flex-row" @submit.prevent="simulate">
        <input v-model="sender" aria-label="Sender" class="rounded-lg border border-gray-300 px-3 py-2 text-sm sm:w-44" />
        <input v-model="body" aria-label="Message text" placeholder="Type any message…" class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        <button :disabled="sending || !body.trim()" class="rounded-lg bg-nimbus px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {{ sending ? "Checking…" : "Receive" }}
        </button>
      </form>
      <p v-if="sendErr" class="mt-2 text-sm text-red-600">{{ sendErr }}</p>
    </Card>

    <ul class="divide-y rounded-xl border border-gray-200 bg-white">
      <li v-for="m in messages ?? []" :key="m.id" class="p-4">
        <button class="flex w-full items-start gap-3 text-left" :aria-expanded="open === m.id" @click="open = open === m.id ? null : m.id">
          <span
            class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
            :class="m.customerVerdict === 'not_scam' || m.verdict === 'ok' ? 'bg-gray-300' : m.verdict === 'scam' ? 'bg-red-500' : 'bg-amber-400'"
            aria-hidden="true"
          />
          <span class="min-w-0 flex-1">
            <span class="flex items-baseline justify-between gap-2">
              <span class="font-medium">{{ m.sender }}</span>
              <span class="shrink-0 text-xs text-gray-500">{{ ago(m.receivedAt) }}</span>
            </span>
            <span class="mt-0.5 block text-sm text-gray-700" :class="open === m.id ? '' : 'line-clamp-2'">{{ m.body }}</span>
            <span v-if="m.verdict !== 'ok' && m.customerVerdict !== 'not_scam'" class="mt-1 inline-block rounded px-1.5 py-0.5 text-xs font-medium"
              :class="m.verdict === 'scam' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'">
              {{ m.verdict === "scam" ? `Scam ${confidence(m.scamProbability)}` : "Be careful" }}<template v-if="m.categoryLabel"> · {{ m.categoryLabel }}</template>
            </span>
            <span v-if="m.customerVerdict === 'reported'" class="ml-1 text-xs text-gray-500">Reported</span>
          </span>
        </button>

        <div v-if="open === m.id && m.verdict !== 'ok'" class="ml-5 mt-3 rounded-lg p-3 text-sm" :class="m.verdict === 'scam' ? 'bg-red-50' : 'bg-amber-50'">
          <p v-if="m.advice" class="font-medium text-gray-900">{{ m.advice }}</p>
          <ul v-if="m.redFlags.length" class="mt-2 list-disc space-y-0.5 pl-5 text-gray-700">
            <li v-for="f in m.redFlags" :key="f.id">{{ f.label }}</li>
          </ul>
          <p class="mt-2 text-xs text-gray-500">
            Scam Shield is {{ Math.round(m.scamProbability * 100) }}% confident. It can be wrong, so check with Nimbus directly if unsure.
          </p>
          <div v-if="!m.customerVerdict" class="mt-3 flex gap-2">
            <button class="rounded-lg bg-nimbus px-3 py-1.5 text-xs font-medium text-white" @click="feedback(m, 'report')">Report scam</button>
            <button class="rounded-lg px-3 py-1.5 text-xs text-gray-600 hover:bg-white" @click="feedback(m, 'not_scam')">It's not a scam</button>
          </div>
        </div>
      </li>
      <li v-if="messages && !messages.length" class="p-4 text-sm text-gray-500">No messages.</li>
    </ul>
  </div>
</template>
