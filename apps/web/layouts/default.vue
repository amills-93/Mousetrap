<script setup lang="ts">
const { demoMode } = useRuntimeConfig().public;
const { data: messages } = useMessages();
const flagged = computed(() => (messages.value ?? []).filter(needsReview).length);

const NAV = computed(() => [
  { to: "/", label: "Overview", icon: "home" as const },
  { to: "/lines", label: "Lines", icon: "phone" as const },
  { to: "/billing", label: "Billing", icon: "card" as const },
  { to: "/messages", label: "Messages", icon: "chat" as const, badge: flagged.value },
  { to: "/profile", label: "Profile", icon: "user" as const },
  { to: "/security", label: "Security", icon: "shield" as const },
]);
const route = useRoute();
const active = (to: string) => (to === "/" ? route.path === "/" : route.path.startsWith(to));
</script>

<template>
  <div class="min-h-screen lg:flex">
    <!-- Desktop: fixed ink sidebar -->
    <aside class="hidden w-64 shrink-0 flex-col bg-nimbus-950 px-4 py-6 text-nimbus-100 lg:sticky lg:top-0 lg:flex lg:h-screen">
      <NuxtLink to="/" class="px-2 text-white"><NimbusLogo /></NuxtLink>
      <nav class="mt-8 flex flex-col gap-0.5" aria-label="Main">
        <NuxtLink
          v-for="n in NAV"
          :key="n.to"
          :to="n.to"
          class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition"
          :class="active(n.to) ? 'bg-white/10 font-medium text-white' : 'text-nimbus-300 hover:bg-white/5 hover:text-white'"
          :aria-current="active(n.to) ? 'page' : undefined"
        >
          <Icon :name="n.icon" :size="18" :class="active(n.to) ? 'text-nimbus-accent' : 'text-nimbus-400 group-hover:text-nimbus-200'" />
          {{ n.label }}
          <span v-if="n.badge" class="ml-auto rounded-full bg-rose-500 px-2 text-[11px] font-semibold leading-5 text-white" :aria-label="`${n.badge} to review`">{{ n.badge }}</span>
        </NuxtLink>
      </nav>

      <div v-if="demoMode" class="mt-6 border-t border-white/10 pt-4">
        <p class="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-nimbus-400">Demo</p>
        <NuxtLink
          to="/admin/risk"
          class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition"
          :class="active('/admin') ? 'bg-white/10 font-medium text-white' : 'text-nimbus-300 hover:bg-white/5 hover:text-white'"
        >
          <Icon name="pulse" :size="18" :class="active('/admin') ? 'text-nimbus-accent' : 'text-nimbus-400'" />
          Risk console
        </NuxtLink>
      </div>

      <div class="mt-auto border-t border-white/10 pt-4">
        <AccountSwitcher up />
      </div>
    </aside>

    <!-- Mobile: top bar + scrollable tab strip -->
    <header class="sticky top-0 z-40 bg-nimbus-950 text-white lg:hidden">
      <div class="flex h-14 items-center justify-between px-4">
        <NuxtLink to="/"><NimbusLogo compact /></NuxtLink>
        <div class="flex items-center gap-2">
          <DemoReset v-if="demoMode" />
          <AccountSwitcher compact />
        </div>
      </div>
      <nav class="flex gap-1 overflow-x-auto px-2 pb-2" aria-label="Main">
        <NuxtLink
          v-for="n in [...NAV, ...(demoMode ? [{ to: '/admin/risk', label: 'Risk console', icon: 'pulse' as const, badge: 0 }] : [])]"
          :key="n.to"
          :to="n.to"
          class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-sm"
          :class="active(n.to) ? 'bg-white/15 text-white' : 'text-nimbus-300'"
        >
          {{ n.label }}
          <span v-if="n.badge" class="rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold leading-4 text-white">{{ n.badge }}</span>
        </NuxtLink>
      </nav>
    </header>

    <main class="min-w-0 flex-1">
      <!-- Desktop demo bar (the mobile header carries the same button) -->
      <div v-if="demoMode" class="sticky top-0 z-30 hidden h-12 items-center justify-end gap-3 bg-nimbus-950 px-8 lg:flex">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-nimbus-400">Demo mode</span>
        <DemoReset />
      </div>
      <div class="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:py-12">
        <slot />
      </div>
    </main>
  </div>
</template>
