<script setup lang="ts">
const { data, refresh } = await useAccount();
const form = reactive({
  name: data.value?.user.name ?? "",
  email: data.value?.user.email ?? "",
  ...(data.value?.account.address ?? { street: "", city: "", state: "", zip: "" }),
});
const msg = ref<{ ok: boolean; text: string } | null>(null);
const busy = ref(false);

async function save() {
  busy.value = true;
  const err = await accountAction("/api/account/profile", form, "PATCH");
  busy.value = false;
  msg.value = err ? { ok: false, text: err } : { ok: true, text: "Profile saved" };
  if (err) return;
  // Name/email also appear in the header (from the session), so reload when they change.
  const identityChanged = form.email.trim().toLowerCase() !== data.value?.user.email || form.name.trim() !== data.value?.user.name;
  if (identityChanged) reloadTo("/profile");
  else await refresh();
}
</script>

<template>
  <div class="max-w-3xl">
    <PageHeader title="Profile" subtitle="Your contact details and service address." />
    <form class="space-y-5" @submit.prevent="save">
      <Card title="Contact">
        <div class="grid gap-4 sm:grid-cols-2">
          <label class="label">Full name<input v-model="form.name" required maxlength="80" autocomplete="name" class="input" /></label>
          <label class="label">Email<input v-model="form.email" type="email" required autocomplete="email" class="input" /></label>
        </div>
      </Card>
      <Card title="Service address">
        <div class="grid gap-4 sm:grid-cols-6">
          <label class="label sm:col-span-6">Street address<input v-model="form.street" maxlength="120" autocomplete="street-address" class="input" /></label>
          <label class="label sm:col-span-3">City<input v-model="form.city" maxlength="60" autocomplete="address-level2" class="input" /></label>
          <label class="label sm:col-span-1">State<input v-model="form.state" maxlength="30" autocomplete="address-level1" class="input" /></label>
          <label class="label sm:col-span-2">ZIP<input v-model="form.zip" inputmode="numeric" maxlength="10" autocomplete="postal-code" class="input" /></label>
        </div>
      </Card>
      <div class="flex flex-wrap items-center gap-4">
        <button :disabled="busy" class="btn-primary">{{ busy ? "Saving…" : "Save changes" }}</button>
        <Notice :msg="msg" />
      </div>
    </form>
  </div>
</template>
