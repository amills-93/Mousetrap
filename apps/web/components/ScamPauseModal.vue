<script setup lang="ts">
// Scam pause (ARCHITECTURE.md 7.5): shown instead of a critical change when the session looks like someone is
// being talked through it. Opened by trustedFetch(). It names no signals on purpose: a scammer on the call would
// learn what to avoid. The safe answer is the prominent one.
const state = usePauseState();
const yesBtn = ref<HTMLButtonElement | null>(null);
watch(
  () => state.value.open,
  async (open) => {
    if (open) {
      await nextTick();
      yesBtn.value?.focus();
    }
  },
);
</script>

<template>
  <div v-if="state.open" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" @keydown.esc="finishPause('cancel')">
    <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl" role="alertdialog" aria-modal="true" aria-labelledby="pause-title" aria-describedby="pause-body">
      <h2 id="pause-title" class="text-lg font-semibold text-nimbus">Is someone asking you to do this?</h2>
      <div id="pause-body" class="mt-2 space-y-2 text-sm text-gray-700">
        <p>
          Scammers pose as Nimbus support, your bank, or the police, and talk people through moving their number,
          changing their SIM, or reading out a transfer PIN.
        </p>
        <p class="font-medium text-gray-900">Nimbus will never call, text, or email asking you to do this, or for a code or PIN.</p>
        <p>If you are on the phone with someone about this right now, hang up and call us on the number on the back of your bill.</p>
      </div>
      <div class="mt-5 flex flex-col gap-2">
        <button ref="yesBtn" type="button" class="rounded-lg bg-nimbus px-4 py-2 text-sm font-medium text-white" @click="finishPause('cancel')">
          Yes, someone asked me to. Stop it.
        </button>
        <button type="button" class="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100" @click="finishPause('hold')">
          No, I'm doing this myself. Hold it for {{ holdDuration(state.holdMs) }}.
        </button>
      </div>
    </div>
  </div>
</template>
