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
  <div v-if="state.open" class="scrim" @keydown.esc="finishPause('cancel')">
    <div class="dialog max-w-lg overflow-hidden" role="alertdialog" aria-modal="true" aria-labelledby="pause-title" aria-describedby="pause-body">
      <div class="relative overflow-hidden bg-violet-950 px-7 py-7 text-white sm:px-8">
        <svg viewBox="0 0 200 200" class="pointer-events-none absolute -right-16 -top-16 h-56 w-56 text-white/[0.07]" aria-hidden="true">
          <circle v-for="r in [40, 80, 120]" :key="r" cx="160" cy="40" :r="r" fill="none" stroke="currentColor" stroke-width="14" />
        </svg>
        <p class="relative flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-violet-200">
          <Icon name="shield" :size="16" />Paused for your safety
        </p>
        <h2 id="pause-title" class="relative mt-3 text-2xl font-semibold leading-tight">Is someone asking you to do this?</h2>
      </div>
      <div class="px-7 pb-7 pt-6 sm:px-8">
        <div id="pause-body" class="space-y-3 text-sm leading-relaxed text-ink-soft">
          <p>
            Scammers pose as Nimbus support, your bank, or the police, and talk people through moving their number,
            changing their SIM, or reading out a transfer PIN.
          </p>
          <p class="rounded-xl bg-violet-50 px-4 py-3 font-semibold text-violet-950">Nimbus will never call, text, or email asking you to do this, or for a code or PIN.</p>
          <p>If you are on the phone with someone about this right now, hang up and call us on the number on the back of your bill.</p>
        </div>
        <div class="mt-6 flex flex-col gap-2">
          <button ref="yesBtn" type="button" class="btn-primary !py-3 text-[15px]" @click="finishPause('cancel')">
            Yes, someone asked me to. Stop it.
          </button>
          <button type="button" class="btn-secondary" @click="finishPause('hold')">
            No, I'm doing this myself. Hold it for {{ holdDuration(state.holdMs) }}.
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
