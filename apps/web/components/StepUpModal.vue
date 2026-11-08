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
  <div v-if="state.open" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" @keydown.esc="finishStepUp(false)">
    <form
      class="w-full max-w-sm rounded-xl bg-white p-6 shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="stepup-title"
      @submit.prevent="submit"
    >
      <h2 id="stepup-title" class="text-lg font-semibold text-nimbus">Confirm it's you</h2>
      <p class="mt-1 text-sm text-gray-600">
        This action needs an extra check. Type the phrase below, then enter the 6-digit code from your authenticator app.
      </p>
      <label class="mt-4 block text-sm text-gray-700" for="stepup-phrase">
        Type: <span class="font-medium text-gray-900">{{ phrase }}</span>
      </label>
      <input
        id="stepup-phrase"
        ref="phraseInput"
        v-model="typed"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-nimbus focus:outline-none focus:ring-2 focus:ring-nimbus-accent"
        @paste.prevent
        @drop.prevent
        @keydown.enter.prevent="input?.focus()"
      />
      <input
        ref="input"
        v-model="code"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        pattern="\d{6}"
        placeholder="123456"
        class="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-center text-xl tracking-[0.4em] focus:border-nimbus focus:outline-none focus:ring-2 focus:ring-nimbus-accent"
      />
      <p v-if="error" class="mt-2 text-sm text-red-600" role="alert">{{ error }}</p>
      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100" @click="finishStepUp(false)">Cancel</button>
        <button type="submit" :disabled="busy || !phraseDone || code.trim().length !== 6" class="rounded-lg bg-nimbus px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {{ busy ? "Verifying…" : "Verify" }}
        </button>
      </div>
    </form>
  </div>
</template>
