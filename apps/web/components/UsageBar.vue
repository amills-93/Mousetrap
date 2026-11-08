<script setup lang="ts">
const props = defineProps<{ used: number; allowance: number }>();
const pct = computed(() => Math.min(100, Math.round((props.used / props.allowance) * 100)));
</script>

<template>
  <div>
    <div class="flex justify-between text-xs text-gray-500">
      <span>{{ used.toFixed(1) }} GB used</span>
      <span>{{ allowance }} GB high-speed</span>
    </div>
    <div class="mt-1 h-2 rounded-full bg-gray-200 overflow-hidden">
      <div class="h-full rounded-full" :class="pct >= 90 ? 'bg-amber-500' : 'bg-nimbus-accent'" :style="{ width: pct + '%' }" />
    </div>
  </div>
</template>
