<script setup lang="ts">
defineProps<{ title: string; subtitle?: string; back?: { to: string; label: string }; eyebrow?: string }>();
</script>

<template>
  <header class="mb-8 flex flex-wrap items-end justify-between gap-4">
    <div class="min-w-0">
      <NuxtLink v-if="back" :to="back.to" class="back-link mb-2"><Icon name="back" :size="16" />{{ back.label }}</NuxtLink>
      <p v-if="eyebrow" class="eyebrow mb-1">{{ eyebrow }}</p>
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-sub max-w-2xl">{{ subtitle }}</p>
    </div>
    <slot />
  </header>
</template>
