<script setup lang="ts">
// TOTP prompt for step-up (ARCHITECTURE.md 5.2-5.4). Opened by trustedFetch(); verifies via /api/stepup/verify.
const state = useStepUpState();
// Typed (not pasted) so ML can compare its keystroke timing with the owner's. The text itself is never sent.
const PHRASES = [
  "my phone plan stays with me",
  "nimbus keeps my number safe",
  "checking it is really me today",
  "the quick fox moves my line",
];
const phrase = ref(PHRASES[0]);
const typed = ref("");
const phraseDone = computed(() => typed.value.trim().length >= phrase.value.length - 2);
const code = ref("");
const error = ref("");
const busy = ref(false);
const input = ref<HTMLInputElement | null>(null);
const phraseInput = ref<HTMLInputElement | null>(null);

watch(
  () => state.value.open,
  async (open) => {
    if (!open) return;
    phrase.value = PHRASES[Math.floor(Math.random() * PHRASES.length)];
    typed.value = "";
    code.value = "";
    error.value = "";
    await nextTick();
    phraseInput.value?.focus();
  },
);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    await flushFirst(); // the phrase keystrokes must reach ML before the server judges them
    await $fetch("/api/stepup/verify", { method: "POST", body: { code: code.value.trim() } });
    finishStepUp(true);
  } catch (e: any) {
    const data = e?.data?.data ?? {};
    if (data.action === "logout") return signedOut(data.reason);
    error.value = e?.data?.statusMessage || "Could not verify the code";
    if (data.action === "type_phrase") {
      typed.value = "";
      return phraseInput.value?.focus();
    }
    code.value = "";
    input.value?.focus();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div v-if="state.open" class="scrim" @keydown.esc="finishStepUp(false)">
    <form class="dialog max-w-md p-7 sm:p-8" role="dialog" aria-modal="true" aria-labelledby="stepup-title" @submit.prevent="submit">
      <span class="grid h-12 w-12 place-items-center rounded-2xl bg-nimbus-50 text-nimbus"><Icon name="lock" :size="24" /></span>
      <h2 id="stepup-title" class="mt-5 text-2xl font-semibold">Confirm it's you</h2>
      <p class="mt-1.5 text-sm leading-relaxed text-ink-muted">
        This change needs an extra check. Type the phrase below, then enter the 6-digit code from your authenticator app.
      </p>

      <p class="mt-5 rounded-xl bg-ink-wash px-4 py-3 text-[15px] font-medium" aria-hidden="true">{{ phrase }}</p>
      <label class="label mt-4" for="stepup-phrase">Type the phrase<span class="sr-only">: {{ phrase }}</span></label>
      <input
        id="stepup-phrase"
        ref="phraseInput"
        v-model="typed"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        class="input"
        :class="phraseDone ? '!border-emerald-500' : ''"
        @paste.prevent
        @drop.prevent
        @keydown.enter.prevent="input?.focus()"
      />

      <label class="label mt-4" for="stepup-code">6-digit code</label>
      <input
        id="stepup-code"
        ref="input"
        v-model="code"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        pattern="\d{6}"
        placeholder="000000"
        class="input text-center font-display text-2xl tracking-[0.5em]"
      />
      <p v-if="error" class="notice-err mt-4" role="alert"><Icon name="alert" :size="18" class="mt-px" />{{ error }}</p>

      <div class="mt-7 flex justify-end gap-2">
        <button type="button" class="btn-ghost" @click="finishStepUp(false)">Cancel</button>
        <button type="submit" :disabled="busy || !phraseDone || code.trim().length !== 6" class="btn-primary min-w-[7rem]">
          {{ busy ? "Verifying…" : "Verify" }}
        </button>
      </div>
    </form>
  </div>
</template>
