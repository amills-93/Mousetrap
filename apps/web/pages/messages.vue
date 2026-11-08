<script setup lang="ts">
// Texts with scam verdicts (ARCHITECTURE.md 7.6). The server classifies; this page only shows the result.
const { demoMode } = useRuntimeConfig().public;
const { data: messages, refresh } = await useMessages();
const open = ref<string | null>(null);

const ago = (d: string) => {
  const m = Math.round((Date.now() - new Date(d).getTime()) / 60_000);
  return m < 1 ? "now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};
// The model's confidence in words: honest about the band, without a false-precision percentage up front.
const confidence = (p: number) => (p >= 0.9 ? "very likely" : p >= 0.5 ? "likely" : "possibly");
// What the row shows: a dismissed flag reads as an ordinary text.
const level = (m: InboxMessage) => (m.customerVerdict === "not_scam" || m.verdict === "ok" ? "ok" : m.verdict);
const LEVEL = {
  ok: { avatar: "bg-ink-wash text-ink-muted", chip: "", panel: "" },
  suspicious: { avatar: "bg-amber-100 text-amber-800", chip: "bg-amber-100 text-amber-900", panel: "border-amber-200 bg-amber-50" },
  scam: { avatar: "bg-rose-100 text-rose-700", chip: "bg-rose-100 text-rose-800", panel: "border-rose-200 bg-rose-50" },
} as const;

async function feedback(m: InboxMessage, action: "report" | "not_scam") {
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
  <div class="space-y-5">
    <PageHeader
      title="Messages"
      subtitle="Nimbus Scam Shield checks incoming texts for scams. In this demo the texts are synthetic. On a real phone the check would run on the device and Nimbus would never see your messages."
    />

    <Card v-if="demoMode" title="Demo: receive a text" subtitle="Type any message and see how Scam Shield screens it.">
      <form class="flex flex-col gap-3 sm:flex-row" @submit.prevent="simulate">
        <input v-model="sender" aria-label="Sender" class="input !mt-0 sm:w-44" />
        <input v-model="body" aria-label="Message text" placeholder="Type any message…" class="input !mt-0 flex-1" />
        <button :disabled="sending || !body.trim()" class="btn-primary">{{ sending ? "Checking…" : "Receive" }}</button>
      </form>
      <p v-if="sendErr" class="notice-err mt-3" role="alert">{{ sendErr }}</p>
    </Card>

    <ul class="overflow-hidden rounded-2xl border border-ink-line bg-white shadow-card">
      <li v-for="m in messages ?? []" :key="m.id" class="border-b border-ink-line last:border-b-0">
        <button
          class="flex w-full items-start gap-4 px-5 py-4 text-left transition hover:bg-ink-wash/60"
          :class="open === m.id ? 'bg-ink-wash/60' : ''"
          :aria-expanded="open === m.id"
          @click="open = open === m.id ? null : m.id"
        >
          <span class="grid h-10 w-10 shrink-0 place-items-center rounded-full" :class="LEVEL[level(m)].avatar">
            <Icon :name="level(m) === 'ok' ? 'chat' : 'alert'" :size="18" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="flex items-baseline justify-between gap-2">
              <span class="font-semibold">{{ m.sender }}</span>
              <span class="shrink-0 text-xs text-ink-muted">{{ ago(m.receivedAt) }}</span>
            </span>
            <span class="mt-0.5 block text-sm text-ink-soft" :class="open === m.id ? '' : 'line-clamp-2'">{{ m.body }}</span>
            <span class="mt-2 flex flex-wrap items-center gap-2">
              <span v-if="level(m) !== 'ok'" class="badge" :class="LEVEL[level(m)].chip">
                {{ m.verdict === "scam" ? `Scam ${confidence(m.scamProbability)}` : "Be careful" }}<template v-if="m.categoryLabel"> · {{ m.categoryLabel }}</template>
              </span>
              <span v-if="m.customerVerdict === 'reported'" class="badge bg-ink-wash text-ink-muted"><Icon name="check" :size="12" />Reported</span>
            </span>
          </span>
        </button>

        <div v-if="open === m.id && m.verdict !== 'ok'" class="px-5 pb-5 sm:pl-[4.75rem]">
          <div class="rounded-xl border p-4 text-sm" :class="LEVEL[m.verdict].panel">
            <p v-if="m.advice" class="font-semibold text-ink">{{ m.advice }}</p>
            <ul v-if="m.redFlags.length" class="mt-3 space-y-1.5 text-ink-soft">
              <li v-for="f in m.redFlags" :key="f.id" class="flex items-start gap-2"><Icon name="alert" :size="16" class="mt-0.5 text-ink-muted" />{{ f.label }}</li>
            </ul>
            <p class="mt-3 text-xs text-ink-muted">
              Scam Shield is {{ Math.round(m.scamProbability * 100) }}% confident. It can be wrong, so check with Nimbus directly if unsure.
            </p>
            <div v-if="!m.customerVerdict" class="mt-4 flex flex-wrap gap-2">
              <button class="btn-primary !py-2 text-xs" @click="feedback(m, 'report')">Report scam</button>
              <button class="btn-secondary !py-2 text-xs" @click="feedback(m, 'not_scam')">It's not a scam</button>
            </div>
          </div>
        </div>
      </li>
      <li v-if="messages && !messages.length" class="px-5 py-10 text-center text-sm text-ink-muted">No messages.</li>
    </ul>
  </div>
</template>
