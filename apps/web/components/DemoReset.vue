<script setup lang="ts">
// DEMO_MODE only: clears locks, holds and behavioral risk for every account (server/api/admin/reset.post.ts).
const route = useRoute();
const busy = ref(false);
const failed = ref(false);

async function reset() {
  if (!confirm("Reset the demo? This clears step-up locks, scam holds, risk scores and inboxes for every account.")) return;
  busy.value = true;
  failed.value = false;
  try {
    await $fetch("/api/admin/reset", { method: "POST" });
    reloadTo(route.fullPath); // fresh client state (inbox, overlay, collector)
  } catch {
    failed.value = true;
    busy.value = false;
  }
}
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition disabled:opacity-60"
    :class="failed ? 'bg-rose-500/15 text-rose-300 hover:bg-rose-500/25' : 'bg-white/10 text-nimbus-100 hover:bg-white/15'"
    :disabled="busy"
    :title="failed ? 'Reset failed, try again' : 'Clear locks and behavioral risk for every account'"
    @click="reset"
  >
    <Icon name="reset" :size="14" />{{ busy ? "Resetting…" : failed ? "Retry reset" : "Reset demo" }}
  </button>
</template>
