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
  <div class="space-y-5">
    <PageHeader title="Security" subtitle="Protect your line from SIM-swap and account takeover." />

    <div class="grid gap-5 sm:grid-cols-2">
      <NuxtLink to="/security/sim" class="card-link group flex items-start gap-4">
        <span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-nimbus-50 text-nimbus"><Icon name="sim" :size="22" /></span>
        <span class="min-w-0 flex-1">
          <span class="block font-semibold">SIM swap / eSIM transfer</span>
          <span class="mt-0.5 block text-sm text-ink-muted">Move a line to a new SIM card or device.</span>
        </span>
        <Icon name="arrow" class="mt-1 text-nimbus transition group-hover:translate-x-0.5" />
      </NuxtLink>
      <NuxtLink to="/security/authorized-users" class="card-link group flex items-start gap-4">
        <span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-nimbus-50 text-nimbus"><Icon name="users" :size="22" /></span>
        <span class="min-w-0 flex-1">
          <span class="block font-semibold">Authorized users</span>
          <span class="mt-0.5 block text-sm text-ink-muted">People who can manage this account.</span>
        </span>
        <Icon name="arrow" class="mt-1 text-nimbus transition group-hover:translate-x-0.5" />
      </NuxtLink>
    </div>

    <div class="grid gap-5 md:grid-cols-2">
      <Card title="Change password">
        <form class="space-y-4" @submit.prevent="changePassword">
          <label class="label">Current password
            <input v-model="pw.currentPassword" type="password" autocomplete="current-password" required class="input" />
          </label>
          <label class="label">New password
            <input v-model="pw.newPassword" type="password" autocomplete="new-password" placeholder="8+ characters" minlength="8" required class="input" />
          </label>
          <label class="flex items-center gap-2 text-sm text-ink-soft">
            <input v-model="pw.revokeOtherSessions" type="checkbox" class="h-4 w-4 accent-nimbus" /> Sign out other devices
          </label>
          <button class="btn-primary">Update password</button>
          <Notice :msg="pwMsg" />
        </form>
      </Card>

      <Card title="Port-out PIN" subtitle="You'll need this PIN to move your number to another carrier.">
        <div class="flex items-center gap-3 rounded-xl bg-ink-wash px-4 py-5">
          <Icon name="key" :size="22" class="text-ink-muted" />
          <p class="font-display text-3xl font-semibold tabular-nums tracking-[0.3em]" :class="pin ? 'text-ink' : 'text-ink-muted'">{{ pin ?? "••••••" }}</p>
        </div>
        <button v-if="!pin" class="btn-secondary mt-4" @click="revealPin"><Icon name="lock" :size="16" />Reveal PIN</button>
        <p v-else class="mt-4 text-xs text-ink-muted">Hidden again in 30 seconds. Never read this PIN to anyone who calls you.</p>
        <p v-if="pinErr" class="notice-err mt-3" role="alert"><Icon name="alert" :size="18" class="mt-px" />{{ pinErr }}</p>
      </Card>
    </div>

    <Card title="Signed-in devices" :subtitle="`Every place ${session?.user.email} is signed in. Revoking a session signs that browser out.`">
      <p v-if="sessionsErr" class="notice-err" role="alert">{{ sessionsErr }}</p>
      <ul class="-mx-6 divide-y divide-ink-line border-t border-ink-line">
        <li v-for="s in sessions" :key="s.id" class="flex items-center gap-4 px-6 py-3.5">
          <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ink-wash text-ink-muted"><Icon name="monitor" /></span>
          <div class="min-w-0 flex-1">
            <p class="flex items-center gap-2 text-sm font-medium">
              <span class="truncate">{{ s.userAgent || "Unknown device" }}</span>
              <span v-if="s.token === session?.session.token" class="badge shrink-0 bg-cyan-50 text-cyan-800">This browser</span>
            </p>
            <p class="text-xs text-ink-muted">IP {{ s.ipAddress || "unknown" }} · signed in {{ new Date(s.createdAt).toLocaleString() }}</p>
          </div>
          <button class="btn-danger shrink-0 !px-3 !py-1.5" @click="revoke(s)">Revoke</button>
        </li>
        <li v-if="!sessions.length && !sessionsErr" class="px-6 py-4 text-sm text-ink-muted">Loading…</li>
      </ul>
    </Card>
  </div>
</template>
