<script setup lang="ts">
// multiSession: the accounts signed in on THIS browser (one entry per user).
const { data: session } = await useAuthSession();
const open = ref(false);
const deviceSessions = ref<{ session: { token: string }; user: { id: string; name: string; email: string } }[]>([]);

async function load() {
  const { data } = await authClient.multiSession.listDeviceSessions();
  deviceSessions.value = data ?? [];
}

async function toggle() {
  open.value = !open.value;
  if (open.value) await load();
}

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
</script>

<template>
  <div v-if="session" class="relative">
    <button class="flex items-center gap-2 rounded px-3 py-1.5 hover:bg-white/10" @click="toggle">
      <span class="h-7 w-7 rounded-full bg-nimbus-accent text-nimbus font-semibold grid place-items-center">
        {{ session.user.name.charAt(0).toUpperCase() }}
      </span>
      <span class="text-sm">{{ session.user.email }}</span>
    </button>

    <div v-if="open" class="absolute right-0 mt-2 w-72 rounded-lg bg-white text-gray-800 shadow-lg ring-1 ring-black/5 z-10">
      <ul class="py-1">
        <li v-for="d in deviceSessions" :key="d.session.token">
          <button
            class="w-full text-left px-4 py-2 hover:bg-gray-50 flex justify-between items-center"
            :disabled="d.user.id === session.user.id"
            @click="switchTo(d.session.token)"
          >
            <span>
              <span class="block text-sm font-medium">{{ d.user.name }}</span>
              <span class="block text-xs text-gray-500">{{ d.user.email }}</span>
            </span>
            <span v-if="d.user.id === session.user.id" class="text-xs text-nimbus">active</span>
          </button>
        </li>
      </ul>
      <div class="border-t py-1 text-sm">
        <NuxtLink to="/login" class="block px-4 py-2 hover:bg-gray-50" @click="open = false">Add another account</NuxtLink>
        <button class="block w-full text-left px-4 py-2 hover:bg-gray-50" @click="signOutCurrent">Sign out {{ session.user.name }}</button>
        <button class="block w-full text-left px-4 py-2 hover:bg-gray-50 text-red-600" @click="signOutAll">Sign out all accounts</button>
      </div>
    </div>
  </div>
</template>
