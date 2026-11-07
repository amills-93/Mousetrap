<script setup lang="ts">
const route = useRoute();
const { data, refresh } = await useAccount();
const line = computed(() => data.value?.lines.find((l) => l.id === route.params.id));
if (!line.value) throw createError({ statusCode: 404, statusMessage: "Line not found" });

const nickname = ref(line.value.nickname);
const plan = ref(line.value.plan);
const msg = ref<{ ok: boolean; text: string } | null>(null);

async function save(body: { nickname?: string; plan?: string }, okText: string) {
  const err = await accountAction(`/api/account/lines/${route.params.id}`, body, "PATCH");
  msg.value = err ? { ok: false, text: err } : { ok: true, text: okText };
  if (!err) await refresh();
}
</script>

<template>
  <div v-if="line && data" class="space-y-6 max-w-2xl">
    <div>
      <NuxtLink to="/lines" class="text-sm text-gray-500 hover:underline">← Lines</NuxtLink>
      <h1 class="text-2xl font-semibold text-nimbus mt-1">{{ line.nickname }}</h1>
      <p class="text-sm text-gray-500">{{ line.phone }} · {{ line.deviceName }} · SIM ••{{ line.simIccidLast4 }}</p>
    </div>

    <Card title="Usage"><UsageBar :used="line.dataUsedGb" :allowance="line.dataAllowanceGb" /></Card>

    <Card title="Rename line">
      <form class="flex gap-2" @submit.prevent="save({ nickname }, 'Line renamed')">
        <input v-model="nickname" maxlength="40" required class="flex-1 rounded border border-gray-300 px-3 py-2" />
        <button class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">Save</button>
      </form>
    </Card>

    <Card title="Change plan">
      <form class="space-y-3" @submit.prevent="save({ plan }, 'Plan updated')">
        <label v-for="p in data.plans" :key="p.name" class="flex items-center justify-between rounded border px-4 py-3 cursor-pointer" :class="plan === p.name ? 'border-nimbus ring-1 ring-nimbus' : 'border-gray-200'">
          <span class="flex items-center gap-3">
            <input v-model="plan" type="radio" :value="p.name" class="accent-nimbus" />
            <span><span class="font-medium">{{ p.name }}</span><span class="block text-xs text-gray-500">{{ p.dataGb }} GB high-speed data</span></span>
          </span>
          <span class="text-sm">{{ money(p.price) }}/mo</span>
        </label>
        <button :disabled="plan === line.plan" class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium disabled:opacity-40">Change plan</button>
      </form>
    </Card>

    <p v-if="msg" class="text-sm" :class="msg.ok ? 'text-green-700' : 'text-red-600'">{{ msg.text }}</p>
  </div>
</template>
