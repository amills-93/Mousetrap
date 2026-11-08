<script setup lang="ts">
const { data, refresh } = await useAccount();
const form = reactive({ name: "", email: "" });
const msg = ref<{ ok: boolean; text: string } | null>(null);

async function add() {
  const err = await accountAction("/api/account/security/authorized-users", form);
  msg.value = err ? { ok: false, text: err } : { ok: true, text: `${form.name} can now manage this account` };
  if (!err) {
    form.name = form.email = "";
    await refresh();
  }
}
</script>

<template>
  <div v-if="data" class="space-y-6 max-w-2xl">
    <div>
      <NuxtLink to="/security" class="text-sm text-gray-500 hover:underline">← Security</NuxtLink>
      <h1 class="text-2xl font-semibold text-nimbus mt-1">Authorized users</h1>
      <p class="text-sm text-gray-500">Authorized users can make changes and get account information from Nimbus support.</p>
    </div>

    <Card title="Current authorized users">
      <ul class="divide-y">
        <li v-for="a in data.authorizedUsers" :key="a.id" class="py-3 flex justify-between text-sm">
          <span><span class="font-medium">{{ a.name }}</span> <span class="text-gray-500">{{ a.email }}</span></span>
          <span class="text-gray-500">added {{ shortDate(a.createdAt) }}</span>
        </li>
        <li v-if="!data.authorizedUsers.length" class="py-3 text-sm text-gray-500">No authorized users yet.</li>
      </ul>
    </Card>

    <Card title="Add an authorized user">
      <form class="grid gap-3 sm:grid-cols-[1fr_1fr_auto]" @submit.prevent="add">
        <input v-model="form.name" required maxlength="80" placeholder="Full name" class="rounded border border-gray-300 px-3 py-2" />
        <input v-model="form.email" type="email" required placeholder="Email" class="rounded border border-gray-300 px-3 py-2" />
        <button class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">Add</button>
      </form>
      <p v-if="msg" class="mt-3 text-sm" :class="msg.ok ? 'text-green-700' : 'text-red-600'">{{ msg.text }}</p>
    </Card>
  </div>
</template>
