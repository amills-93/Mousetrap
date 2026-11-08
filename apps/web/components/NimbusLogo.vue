<!-- Original Nimbus mark: a cloud with two signal arcs. -->
<script setup lang="ts">
defineProps<{ compact?: boolean }>();
</script>

<template>
  <span class="inline-flex items-center gap-2.5">
    <svg viewBox="0 0 40 28" class="h-7 w-10" aria-hidden="true">
      <path d="M11 24h18a7 7 0 0 0 .9-13.94A9 9 0 0 0 12.6 8.2 8 8 0 0 0 11 24z" fill="currentColor" />
      <path d="M19 18a3 3 0 0 1 4.2 0" stroke="#22C3E6" stroke-width="2.2" stroke-linecap="round" fill="none" />
      <path d="M16.2 15.2a7 7 0 0 1 9.8 0" stroke="#22C3E6" stroke-width="2.2" stroke-linecap="round" fill="none" />
    </svg>
    <span class="font-display text-lg font-semibold tracking-tight">Nimbus<span v-if="!compact" class="font-medium text-nimbus-accent"> Mobile</span></span>
  </span>
</template>
