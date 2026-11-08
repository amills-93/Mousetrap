<script setup lang="ts">
const { data: session } = await useAuthSession();

// --- Change password
const pw = reactive({ currentPassword: "", newPassword: "", revokeOtherSessions: true });
const pwMsg = ref<{ ok: boolean; text: string } | null>(null);
async function changePassword() {
  const err = await accountAction("/api/account/security/password", pw);
  pwMsg.value = err ? { ok: false, text: err } : { ok: true, text: "Password changed" };
  if (!err) {
    pw.currentPassword = pw.newPassword = "";
    await loadSessions();
  }
}

// --- Port-out PIN (revealed on demand, hidden again after 30 s)
const pin = ref<string | null>(null);
const pinErr = ref("");
let pinTimer: ReturnType<typeof setTimeout> | undefined;
async function revealPin() {
  pinErr.value = "";
  try {
    pin.value = (await trustedFetch<{ portPin: string }>("/api/account/security/port-pin", { method: "POST" })).portPin;
    clearTimeout(pinTimer);
    pinTimer = setTimeout(() => (pin.value = null), 30_000);
  } catch (e: any) {
    pinErr.value =
      e instanceof StepUpCancelled ? "Verification cancelled." : e instanceof ActionPaused ? e.message : e?.data?.statusMessage || "Could not reveal PIN";
  }
}
onBeforeUnmount(() => clearTimeout(pinTimer));

// --- Signed-in devices: every session of the CURRENT user, across all browsers (core Better Auth list).
type DeviceRow = { id: string; token: string; userAgent?: string | null; ipAddress?: string | null; createdAt: string | Date };
const sessions = ref<DeviceRow[]>([]);
const sessionsErr = ref("");
async function loadSessions() {
  const { data, error } = await authClient.listSessions();
  sessionsErr.value = error ? error.message || "Could not load sessions" : "";
  sessions.value = (data ?? []) as DeviceRow[];
}
async function revoke(row: DeviceRow) {
  await authClient.revokeSession({ token: row.token });
  if (row.token === session.value?.session.token) return reloadTo("/login");
  await loadSessions();
}
onMounted(loadSessions);
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-semibold text-nimbus">Security</h1>

    <div class="grid gap-4 sm:grid-cols-2">
      <NuxtLink to="/security/sim" class="block">
        <Card>
          <p class="font-medium">SIM swap / eSIM transfer →</p>
          <p class="text-sm text-gray-500 mt-1">Move a line to a new SIM card or device.</p>
        </Card>
      </NuxtLink>
      <NuxtLink to="/security/authorized-users" class="block">
        <Card>
          <p class="font-medium">Authorized users →</p>
          <p class="text-sm text-gray-500 mt-1">People who can manage this account.</p>
        </Card>
      </NuxtLink>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <Card title="Change password">
        <form class="space-y-3" @submit.prevent="changePassword">
          <input v-model="pw.currentPassword" type="password" autocomplete="current-password" placeholder="Current password" required class="w-full rounded border border-gray-300 px-3 py-2" />
          <input v-model="pw.newPassword" type="password" autocomplete="new-password" placeholder="New password (8+ characters)" minlength="8" required class="w-full rounded border border-gray-300 px-3 py-2" />
          <label class="flex items-center gap-2 text-sm text-gray-600">
            <input v-model="pw.revokeOtherSessions" type="checkbox" class="accent-nimbus" /> Sign out other devices
          </label>
          <button class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">Update password</button>
          <p v-if="pwMsg" class="text-sm" :class="pwMsg.ok ? 'text-green-700' : 'text-red-600'">{{ pwMsg.text }}</p>
        </form>
      </Card>

      <Card title="Port-out PIN">
        <p class="text-sm text-gray-600">You'll need this PIN to move your number to another carrier.</p>
        <p class="mt-4 font-mono text-2xl tracking-[0.3em]">{{ pin ?? "••••••" }}</p>
        <button v-if="!pin" class="mt-4 rounded border border-nimbus text-nimbus px-4 py-2 text-sm font-medium" @click="revealPin">Reveal PIN</button>
        <p v-else class="mt-4 text-xs text-gray-500">Hidden again in 30 seconds.</p>
        <p v-if="pinErr" class="mt-2 text-sm text-red-600">{{ pinErr }}</p>
      </Card>
    </div>

    <Card title="Signed-in devices">
      <p class="text-sm text-gray-500 -mt-2 mb-3">Every place {{ session?.user.email }} is signed in. Revoking a session signs that browser out.</p>
      <p v-if="sessionsErr" class="text-sm text-red-600">{{ sessionsErr }}</p>
      <div class="divide-y">
        <div v-for="s in sessions" :key="s.id" class="py-3 flex items-center justify-between gap-4">
          <div class="min-w-0">
            <p class="text-sm font-medium truncate">
              {{ s.userAgent || "Unknown device" }}
              <span v-if="s.token === session?.session.token" class="ml-2 text-xs rounded bg-nimbus-accent/20 text-nimbus px-2 py-0.5">this browser</span>
            </p>
            <p class="text-xs text-gray-500">IP {{ s.ipAddress || "unknown" }} · signed in {{ new Date(s.createdAt).toLocaleString() }} · risk —</p>
          </div>
          <button class="text-sm text-red-600 hover:underline shrink-0" @click="revoke(s)">Revoke</button>
        </div>
        <p v-if="!sessions.length && !sessionsErr" class="py-3 text-sm text-gray-500">Loading…</p>
      </div>
    </Card>
  </div>
</template>
