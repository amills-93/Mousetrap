<script setup lang="ts">
// Core Better Auth session list: every session of the CURRENT user, across all browsers/devices.
const { data: session } = await useAuthSession();

type DeviceRow = { id: string; token: string; userAgent?: string | null; ipAddress?: string | null; createdAt: string | Date };
const sessions = ref<DeviceRow[]>([]);
const error = ref("");

async function load() {
  const { data, error: err } = await authClient.listSessions();
  if (err) error.value = err.message || "Could not load sessions";
  sessions.value = (data ?? []) as DeviceRow[];
}

async function revoke(row: DeviceRow) {
  await authClient.revokeSession({ token: row.token });
  if (row.token === session.value?.session.token) return reloadTo("/login");
  await load();
}

onMounted(load);
</script>

<template>
  <section>
    <h1 class="text-2xl font-semibold text-nimbus">Security</h1>
    <h2 class="mt-8 text-lg font-medium">Signed-in devices</h2>
    <p class="text-sm text-gray-500">Every place {{ session?.user.email }} is signed in. Revoking a session signs that browser out.</p>
    <p v-if="error" class="mt-4 text-sm text-red-600">{{ error }}</p>

    <div class="mt-4 bg-white rounded-xl shadow divide-y">
      <div v-for="s in sessions" :key="s.id" class="p-4 flex items-center justify-between gap-4">
        <div class="min-w-0">
          <p class="text-sm font-medium truncate">
            {{ s.userAgent || "Unknown device" }}
            <span v-if="s.token === session?.session.token" class="ml-2 text-xs rounded bg-nimbus-accent/20 text-nimbus px-2 py-0.5">this browser</span>
          </p>
          <p class="text-xs text-gray-500">
            IP {{ s.ipAddress || "unknown" }} · signed in {{ new Date(s.createdAt).toLocaleString() }} · risk —
          </p>
        </div>
        <button class="text-sm text-red-600 hover:underline shrink-0" @click="revoke(s)">Revoke</button>
      </div>
      <p v-if="!sessions.length" class="p-4 text-sm text-gray-500">Loading…</p>
    </div>
  </section>
</template>
