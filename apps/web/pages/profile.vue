<script setup lang="ts">
const { data, refresh } = await useAccount();
const form = reactive({
  name: data.value?.user.name ?? "",
  email: data.value?.user.email ?? "",
  ...(data.value?.account.address ?? { street: "", city: "", state: "", zip: "" }),
});
const msg = ref<{ ok: boolean; text: string } | null>(null);

async function save() {
  const err = await accountAction("/api/account/profile", form, "PATCH");
  msg.value = err ? { ok: false, text: err } : { ok: true, text: "Profile saved" };
  if (err) return;
  // Name/email also appear in the header (from the session), so reload when they change.
  const identityChanged = form.email.trim().toLowerCase() !== data.value?.user.email || form.name.trim() !== data.value?.user.name;
  if (identityChanged) reloadTo("/profile");
  else await refresh();
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <h1 class="text-2xl font-semibold text-nimbus">Profile</h1>
    <Card>
      <form class="grid gap-4 sm:grid-cols-2" @submit.prevent="save">
        <label class="text-sm sm:col-span-2">Full name
          <input v-model="form.name" required maxlength="80" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
        </label>
        <label class="text-sm sm:col-span-2">Email
          <input v-model="form.email" type="email" required class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
        </label>
        <label class="text-sm sm:col-span-2">Street address
          <input v-model="form.street" maxlength="120" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
        </label>
        <label class="text-sm">City
          <input v-model="form.city" maxlength="60" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
        </label>
        <div class="grid grid-cols-2 gap-4">
          <label class="text-sm">State
            <input v-model="form.state" maxlength="30" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
          </label>
          <label class="text-sm">ZIP
            <input v-model="form.zip" inputmode="numeric" maxlength="10" class="mt-1 w-full rounded border border-gray-300 px-3 py-2" />
          </label>
        </div>
        <div class="sm:col-span-2 flex items-center gap-4">
          <button class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">Save changes</button>
          <span v-if="msg" class="text-sm" :class="msg.ok ? 'text-green-700' : 'text-red-600'">{{ msg.text }}</span>
        </div>
      </form>
    </Card>
  </div>
</template>
