<script setup lang="ts">
const route = useRoute();
const { data, refresh } = await useAccount();
const line = computed(() => data.value?.lines.find((l) => l.id === route.params.id));
if (!line.value) throw createError({ statusCode: 404, statusMessage: "Line not found" });

const nickname = ref(line.value.nickname);
const plan = ref(line.value.plan);
const msg = ref<{ ok: boolean; text: string } | null>(null);
const busy = ref(false);

async function save(body: { nickname?: string; plan?: string }, okText: string) {
  busy.value = true;
  const err = await accountAction(`/api/account/lines/${route.params.id}`, body, "PATCH");
  busy.value = false;
  msg.value = err ? { ok: false, text: err } : { ok: true, text: okText };
  if (!err) await refresh();
}
</script>

<template>
  <div v-if="line && data" class="max-w-3xl">
    <PageHeader :back="{ to: '/lines', label: 'Lines' }" :title="line.nickname" :subtitle="`${line.phone} · ${line.deviceName} · SIM ••${line.simIccidLast4}`" />

    <div class="space-y-5">
      <Notice :msg="msg" />

      <Card title="Usage this cycle"><UsageBar :used="line.dataUsedGb" :allowance="line.dataAllowanceGb" big /></Card>

      <Card title="Rename line">
        <form class="flex flex-col gap-3 sm:flex-row" @submit.prevent="save({ nickname }, 'Line renamed')">
          <label class="sr-only" for="nickname">Line name</label>
          <input id="nickname" v-model="nickname" maxlength="40" required class="input !mt-0 flex-1" />
          <button :disabled="busy" class="btn-primary">Save</button>
        </form>
      </Card>

      <Card title="Change plan">
        <form class="space-y-3" @submit.prevent="save({ plan }, 'Plan updated')">
          <label
            v-for="p in data.plans"
            :key="p.name"
            class="flex cursor-pointer items-center justify-between gap-4 rounded-xl border px-4 py-3.5 transition"
            :class="plan === p.name ? 'border-nimbus bg-nimbus-50/60 shadow-focus' : 'border-ink-line hover:border-nimbus-200'"
          >
            <span class="flex items-center gap-3">
              <input v-model="plan" type="radio" :value="p.name" class="h-4 w-4 accent-nimbus" />
              <span>
                <span class="font-semibold">{{ p.name }}</span>
                <span v-if="p.name === line.plan" class="badge ml-2 bg-ink-wash text-ink-muted">Current</span>
                <span class="block text-xs text-ink-muted">{{ p.dataGb }} GB high-speed data</span>
              </span>
            </span>
            <span class="font-display font-semibold tabular-nums">{{ money(p.price) }}<span class="font-sans text-xs font-normal text-ink-muted">/mo</span></span>
          </label>
          <button :disabled="busy || plan === line.plan" class="btn-primary">Change plan</button>
        </form>
      </Card>
    </div>
  </div>
</template>
