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
  <div v-if="data" class="max-w-3xl">
    <PageHeader :back="{ to: '/security', label: 'Security' }" title="SIM swap / eSIM transfer" subtitle="The old SIM stops working as soon as the new one is active." />

    <div class="notice mb-5 border border-amber-200 bg-amber-50 text-amber-900">
      <Icon name="alert" :size="18" class="mt-px" />
      <span>If someone on the phone asked you to do this, stop. Nimbus never asks customers to move their SIM.</span>
    </div>

    <Card>
      <form class="space-y-6" @submit.prevent="submit">
        <label class="label">Line
          <select v-model="form.lineId" class="input">
            <option v-for="l in data.lines" :key="l.id" :value="l.id">{{ l.nickname }} · {{ l.phone }} · {{ l.deviceName }} (SIM ••{{ l.simIccidLast4 }})</option>
          </select>
        </label>

        <fieldset>
          <legend class="label mb-2">New SIM type</legend>
          <div class="grid gap-3 sm:grid-cols-2">
            <label
              v-for="k in [{ v: 'esim', t: 'eSIM', d: 'Activate on a new device' }, { v: 'sim', t: 'Physical SIM card', d: 'Insert a new card' }]"
              :key="k.v"
              class="flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition"
              :class="form.kind === k.v ? 'border-nimbus bg-nimbus-50/60 shadow-focus' : 'border-ink-line hover:border-nimbus-200'"
            >
              <input v-model="form.kind" type="radio" :value="k.v" class="mt-1 h-4 w-4 accent-nimbus" />
              <span><span class="block text-sm font-semibold">{{ k.t }}</span><span class="block text-xs text-ink-muted">{{ k.d }}</span></span>
            </label>
          </div>
        </fieldset>

        <label v-if="form.kind === 'sim'" class="label">SIM card number (ICCID)
          <input v-model="form.iccid" inputmode="numeric" required placeholder="89…" class="input font-mono" />
        </label>

        <label class="label">New device name
          <input v-model="form.deviceName" required maxlength="60" placeholder="e.g. Nimbus Phone 13" class="input" />
        </label>

        <div class="flex flex-wrap items-center gap-4 border-t border-ink-line pt-5">
          <button :disabled="busy" class="btn-primary">
            {{ busy ? "Working…" : form.kind === "esim" ? "Transfer to eSIM" : "Activate SIM" }}
          </button>
          <Notice :msg="msg" />
        </div>
      </form>
    </Card>
  </div>
</template>
