<script setup lang="ts">
const props = defineProps<{ used: number; allowance: number; big?: boolean }>();
const pct = computed(() => Math.min(100, Math.round((props.used / props.allowance) * 100)));
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between gap-2">
      <span :class="big ? 'font-display text-2xl font-semibold tabular-nums' : 'text-sm font-medium tabular-nums'">
        {{ used.toFixed(1) }}<span class="ml-1 font-sans text-xs font-normal text-ink-muted">of {{ allowance }} GB</span>
      </span>
      <span class="text-xs tabular-nums" :class="pct >= 90 ? 'font-medium text-amber-700' : 'text-ink-muted'">{{ pct }}%</span>
    </div>
    <div class="mt-2 h-2 overflow-hidden rounded-full bg-ink-wash" role="meter" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100" :aria-label="`${pct}% of high-speed data used`">
      <div class="h-full rounded-full transition-[width] duration-700" :class="pct >= 90 ? 'bg-amber-500' : 'bg-nimbus'" :style="{ width: pct + '%' }" />
    </div>
  </div>
</template>
