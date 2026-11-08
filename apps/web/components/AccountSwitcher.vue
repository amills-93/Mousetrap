<script setup lang="ts">
// multiSession: the accounts signed in on THIS browser (one entry per user).
// `up` opens the menu above the trigger (sidebar footer); `compact` shows only the avatar (mobile bar).
defineProps<{ up?: boolean; compact?: boolean }>();
const { data: session } = await useAuthSession();
const open = ref(false);
const root = ref<HTMLElement | null>(null);
const deviceSessions = ref<{ session: { token: string }; user: { id: string; name: string; email: string } }[]>([]);

async function load() {
  const { data } = await authClient.multiSession.listDeviceSessions();
  deviceSessions.value = data ?? [];
}

async function toggle() {
  open.value = !open.value;
  if (open.value) await load();
}

function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false;
}
onMounted(() => document.addEventListener("click", onDocClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocClick));

async function switchTo(sessionToken: string) {
  await authClient.multiSession.setActive({ sessionToken });
  reloadTo("/");
}

// Signs out only the active account; Better Auth promotes the next device session if there is one.
async function signOutCurrent() {
  if (!session.value) return;
  await authClient.multiSession.revoke({ sessionToken: session.value.session.token });
  reloadTo("/");
}

// signOut() with multiSession revokes every account on this browser.
async function signOutAll() {
  await authClient.signOut();
  reloadTo("/login");
}

const initial = (name: string) => name.charAt(0).toUpperCase();
</script>

<template>
  <div v-if="session" ref="root" class="relative" @keydown.esc="open = false">
    <button
      class="flex w-full items-center gap-3 rounded-xl p-2 text-left transition hover:bg-white/5"
      :aria-expanded="open"
      aria-haspopup="menu"
      :aria-label="compact ? `Account: ${session.user.email}` : undefined"
      @click="toggle"
    >
      <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-nimbus-accent font-semibold text-nimbus-950">
        {{ initial(session.user.name) }}
      </span>
      <span v-if="!compact" class="min-w-0 flex-1">
        <span class="block truncate text-sm font-medium text-white">{{ session.user.name }}</span>
        <span class="block truncate text-xs text-nimbus-300">{{ session.user.email }}</span>
      </span>
      <Icon v-if="!compact" name="chevron" :size="16" class="text-nimbus-400 transition" :class="open ? (up ? '' : 'rotate-180') : up ? 'rotate-180' : ''" />
    </button>

    <Transition enter-from-class="opacity-0 scale-95" enter-active-class="transition duration-150" leave-to-class="opacity-0" leave-active-class="transition duration-100">
      <div
        v-if="open"
        role="menu"
        class="absolute z-50 w-72 origin-top-right overflow-hidden rounded-2xl bg-white text-ink shadow-modal ring-1 ring-black/5"
        :class="up ? 'bottom-full left-0 mb-2 origin-bottom-left' : 'right-0 top-full mt-2'"
      >
        <p class="px-4 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Accounts on this browser</p>
        <ul class="px-1.5 pb-1.5">
          <li v-for="d in deviceSessions" :key="d.session.token">
            <button
              role="menuitem"
              class="flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left hover:bg-ink-wash disabled:cursor-default disabled:hover:bg-transparent"
              :disabled="d.user.id === session.user.id"
              @click="switchTo(d.session.token)"
            >
              <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-nimbus-50 text-sm font-semibold text-nimbus">{{ initial(d.user.name) }}</span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium">{{ d.user.name }}</span>
                <span class="block truncate text-xs text-ink-muted">{{ d.user.email }}</span>
              </span>
              <Icon v-if="d.user.id === session.user.id" name="check" :size="16" class="text-nimbus" label="Active" />
            </button>
          </li>
        </ul>
        <div class="border-t border-ink-line p-1.5 text-sm">
          <NuxtLink to="/login" role="menuitem" class="flex items-center gap-2.5 rounded-xl px-2.5 py-2 hover:bg-ink-wash" @click="open = false">
            <Icon name="plus" :size="16" class="text-ink-muted" />Add another account
          </NuxtLink>
          <button role="menuitem" class="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left hover:bg-ink-wash" @click="signOutCurrent">
            <Icon name="logout" :size="16" class="text-ink-muted" />Sign out {{ session.user.name }}
          </button>
          <button role="menuitem" class="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-rose-700 hover:bg-rose-50" @click="signOutAll">
            <Icon name="logout" :size="16" />Sign out all accounts
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
