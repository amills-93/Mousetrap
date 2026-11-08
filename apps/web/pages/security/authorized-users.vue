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
  <div v-if="data" class="max-w-3xl space-y-5">
    <PageHeader :back="{ to: '/security', label: 'Security' }" title="Authorized users" subtitle="Authorized users can make changes and get account information from Nimbus support." />

    <Card title="Current authorized users">
      <ul class="-mx-6 divide-y divide-ink-line border-t border-ink-line">
        <li v-for="a in data.authorizedUsers" :key="a.id" class="flex items-center gap-3 px-6 py-3.5 text-sm">
          <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-nimbus-50 font-semibold text-nimbus">{{ a.name.charAt(0).toUpperCase() }}</span>
          <span class="min-w-0 flex-1"><span class="block font-medium">{{ a.name }}</span><span class="block truncate text-ink-muted">{{ a.email }}</span></span>
          <span class="shrink-0 text-xs text-ink-muted">Added {{ shortDate(a.createdAt) }}</span>
        </li>
        <li v-if="!data.authorizedUsers.length" class="px-6 py-4 text-sm text-ink-muted">No authorized users yet.</li>
      </ul>
    </Card>

    <Card title="Add an authorized user">
      <form class="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" @submit.prevent="add">
        <label class="label">Full name<input v-model="form.name" required maxlength="80" class="input" /></label>
        <label class="label">Email<input v-model="form.email" type="email" required class="input" /></label>
        <button class="btn-primary"><Icon name="plus" :size="16" />Add</button>
      </form>
      <div class="mt-4"><Notice :msg="msg" /></div>
    </Card>
  </div>
</template>
