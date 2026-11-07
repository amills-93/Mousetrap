<template>
  <div class="min-h-screen bg-gray-50">
    <header class="bg-nimbus text-white">
      <div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <nav class="flex items-center gap-6">
          <NuxtLink to="/" class="font-semibold text-lg">Nimbus Mobile</NuxtLink>
          <NuxtLink to="/" class="text-sm text-white/80 hover:text-white">Overview</NuxtLink>
          <NuxtLink to="/security" class="text-sm text-white/80 hover:text-white">Security</NuxtLink>
        </nav>
        <AccountSwitcher />
      </div>
    </header>
    <main class="max-w-5xl mx-auto px-4 py-8">
      <slot />
    </main>
  </div>
</template>
