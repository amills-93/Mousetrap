<script setup lang="ts">
const { data, refresh } = await useAccount();
const form = reactive({
  lineId: data.value?.lines[0]?.id ?? "",
  kind: "esim" as "esim" | "sim",
  iccid: "",
  deviceName: "",
});
const msg = ref<{ ok: boolean; text: string } | null>(null);
const busy = ref(false);

async function submit() {
  busy.value = true;
  const body = form.kind === "sim" ? { ...form, iccid: form.iccid.replace(/\s/g, "") } : { lineId: form.lineId, kind: form.kind, deviceName: form.deviceName };
  const err = await accountAction("/api/account/security/sim-swap", body);
  busy.value = false;
  msg.value = err ? { ok: false, text: err } : { ok: true, text: "Done. Your line is now active on the new SIM." };
  if (!err) {
    form.iccid = form.deviceName = "";
    await refresh();
  }
}
</script>

<template>
  <div v-if="data" class="space-y-6 max-w-2xl">
    <div>
      <NuxtLink to="/security" class="text-sm text-gray-500 hover:underline">← Security</NuxtLink>
      <h1 class="text-2xl font-semibold text-nimbus mt-1">SIM swap / eSIM transfer</h1>
      <p class="text-sm text-gray-500">The old SIM stops working as soon as the new one is active.</p>
    </div>

    <Card>
      <form class="space-y-4" @submit.prevent="submit">
        <label class="block text-sm">Line
          <select v-model="form.lineId" class="mt-1 w-full rounded border border-gray-300 px-3 py-2 bg-white">
            <option v-for="l in data.lines" :key="l.id" :value="l.id">{{ l.nickname }} · {{ l.phone }} · {{ l.deviceName }} (SIM ••{{ l.simIccidLast4 }})</option>
          </select>
        </label>

        <fieldset class="text-sm">
          <legend class="mb-1">New SIM type</legend>
          <div class="flex gap-4">
            <label class="flex items-center gap-2"><input v-model="form.kind" type="radio" value="esim" class="accent-nimbus" /> eSIM (new device)</label>
            <label class="flex items-center gap-2"><input v-model="form.kind" type="radio" value="sim" class="accent-nimbus" /> Physical SIM card</label>
          </div>
        </fieldset>

        <label v-if="form.kind === 'sim'" class="block text-sm">SIM card number (ICCID)
          <input v-model="form.iccid" inputmode="numeric" required placeholder="89…" class="mt-1 w-full rounded border border-gray-300 px-3 py-2 font-mono" />
        </label>

        <label class="block text-sm">New device name
          <input v-model="form.deviceName" required maxlength="60" placeholder="e.g. Nimbus Phone 13" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
        </label>

        <button :disabled="busy" class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium disabled:opacity-50">
          {{ form.kind === "esim" ? "Transfer to eSIM" : "Activate SIM" }}
        </button>
        <p v-if="msg" class="text-sm" :class="msg.ok ? 'text-green-700' : 'text-red-600'">{{ msg.text }}</p>
      </form>
    </Card>
  </div>
</template>
