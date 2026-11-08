<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string }>();
</script>

<template>
  <section class="card">
    <header v-if="title || $slots.action" class="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 v-if="title" class="text-lg font-semibold text-ink">{{ title }}</h2>
        <p v-if="subtitle" class="mt-0.5 text-sm text-ink-muted">{{ subtitle }}</p>
      </div>
      <slot name="action" />
    </header>
    <slot />
  </section>
</template>
