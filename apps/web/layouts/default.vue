<script setup lang="ts">
const { demoMode } = useRuntimeConfig().public;
const NAV = [
  { to: "/", label: "Overview" },
  { to: "/lines", label: "Lines" },
  { to: "/billing", label: "Billing" },
  { to: "/profile", label: "Profile" },
  { to: "/security", label: "Security" },
  ...(demoMode ? [{ to: "/admin/risk", label: "Risk console (demo)" }] : []),
];
const route = useRoute();
const active = (to: string) => (to === "/" ? route.path === "/" : route.path.startsWith(to));
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <header class="bg-nimbus text-white">
      <div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <NuxtLink to="/"><NimbusLogo /></NuxtLink>
        <AccountSwitcher />
      </div>
      <nav class="max-w-5xl mx-auto px-4 flex gap-1 overflow-x-auto">
        <NuxtLink
          v-for="n in NAV"
          :key="n.to"
          :to="n.to"
          class="px-3 py-2 text-sm whitespace-nowrap border-b-2"
          :class="active(n.to) ? 'border-nimbus-accent text-white' : 'border-transparent text-white/70 hover:text-white'"
        >
          {{ n.label }}
        </NuxtLink>
      </nav>
    </header>
    <main class="max-w-5xl mx-auto px-4 py-8">
      <slot />
    </main>
  </div>
</template>
