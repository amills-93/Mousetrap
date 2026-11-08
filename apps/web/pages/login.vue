<script setup lang="ts">
definePageMeta({ layout: false });

const route = useRoute();
const step = ref<"password" | "totp">("password");
const email = ref("");
const password = ref("");
const code = ref("");
const error = ref("");
const busy = ref(false);

const { data: session } = await useAuthSession();

// Set by signedOut() after too many failed step-ups. A risk deny passes no reason, so the page says nothing.
const SIGNED_OUT: Record<string, string> = {
  stepup_failed: "You were signed out after too many incorrect verification codes.",
};
const signedOutReason = computed(() => SIGNED_OUT[String(route.query.reason)] ?? "");

// Only allow same-site relative redirects.
const redirectTo = computed(() => {
  const r = route.query.redirect;
  return typeof r === "string" && r.startsWith("/") && !r.startsWith("//") ? r : "/";
});

async function submitPassword() {
  error.value = "";
  busy.value = true;
  const { data, error: err } = await authClient.signIn.email({ email: email.value, password: password.value });
  busy.value = false;
  if (err) return (error.value = err.message || "Sign-in failed");
  if (data && "twoFactorRedirect" in data && data.twoFactorRedirect) {
    step.value = "totp";
    return;
  }
  // Only a login without an authenticator signs in here; that is an unfinished sign-up, so resume it.
  const status = await $fetch("/api/signup/status").catch(() => null);
  reloadTo(status && !status.complete ? "/signup" : redirectTo.value);
}

async function submitTotp() {
  error.value = "";
  busy.value = true;
  const { error: err } = await authClient.twoFactor.verifyTotp({ code: code.value.trim() });
  busy.value = false;
  if (err) return (error.value = err.message || "Invalid code");
  reloadTo(redirectTo.value);
}
</script>

<template>
  <main class="flex min-h-screen flex-col lg:flex-row">
    <section class="relative flex flex-col justify-between gap-10 overflow-hidden bg-nimbus-950 px-6 py-8 text-white sm:px-12 lg:w-[46%] lg:py-14">
      <svg viewBox="0 0 400 400" class="pointer-events-none absolute -bottom-40 -right-40 h-[36rem] w-[36rem] text-white/[0.04]" aria-hidden="true">
        <circle v-for="r in [60, 120, 180]" :key="r" cx="200" cy="200" :r="r" fill="none" stroke="currentColor" stroke-width="24" />
      </svg>
      <NimbusLogo />
      <div class="relative hidden max-w-md lg:block">
        <h1 class="font-display text-5xl font-semibold leading-[1.05] tracking-tight">Your number stays yours.</h1>
        <p class="mt-4 text-base leading-relaxed text-nimbus-200">
          Nimbus watches for the signs of SIM-swap fraud and phone scams, and steps in before your line moves.
        </p>
      </div>
      <ul class="relative hidden space-y-3 text-sm text-nimbus-200 lg:block">
        <li v-for="f in ['Extra checks only when something looks off', 'Scam Shield screens incoming texts', 'Timing and motion only, never what you type']" :key="f" class="flex items-center gap-3">
          <span class="grid h-6 w-6 place-items-center rounded-full bg-white/10 text-nimbus-accent"><Icon name="check" :size="14" /></span>{{ f }}
        </li>
      </ul>
    </section>

    <section class="flex flex-1 items-center justify-center px-6 py-12">
      <div class="w-full max-w-sm">
        <Transition mode="out-in" enter-from-class="opacity-0 translate-x-2" enter-active-class="transition duration-200" leave-to-class="opacity-0 -translate-x-2" leave-active-class="transition duration-150">
          <div :key="step">
            <span v-if="step === 'totp'" class="mb-5 grid h-12 w-12 place-items-center rounded-2xl bg-nimbus-50 text-nimbus"><Icon name="lock" :size="24" /></span>
            <h2 class="text-3xl font-semibold">{{ step === "password" ? "Sign in" : "Two-step verification" }}</h2>
            <p v-if="session && step === 'password'" class="mt-2 text-sm text-ink-muted">
              Signed in as {{ session.user.email }}. Sign in below to add another account, or
              <NuxtLink to="/" class="link">go back to the portal</NuxtLink>.
            </p>
            <p v-else class="mt-2 text-sm text-ink-muted">
              <template v-if="step === 'password'">Welcome back. New to Nimbus? <NuxtLink to="/signup" class="link">Create an account</NuxtLink></template>
              <template v-else>Enter the 6-digit code from your authenticator app.</template>
            </p>

            <p v-if="signedOutReason" class="notice-err mt-5" role="alert"><Icon name="alert" :size="18" class="mt-px" />{{ signedOutReason }}</p>

            <form v-if="step === 'password'" class="mt-8 space-y-5" @submit.prevent="submitPassword">
              <label class="label">Email
                <input v-model="email" type="email" autocomplete="username" required class="input" />
              </label>
              <label class="label">Password
                <input v-model="password" type="password" autocomplete="current-password" required class="input" />
              </label>
              <button :disabled="busy" class="btn-primary w-full !py-3 text-[15px]">{{ busy ? "Signing in…" : "Continue" }}</button>
            </form>

            <form v-else class="mt-8 space-y-5" @submit.prevent="submitTotp">
              <label class="label">Authentication code
                <input v-model="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required autofocus placeholder="000000" class="input text-center font-display text-2xl tracking-[0.5em]" />
              </label>
              <button :disabled="busy" class="btn-primary w-full !py-3 text-[15px]">{{ busy ? "Verifying…" : "Verify" }}</button>
              <button type="button" class="btn-ghost w-full" @click="step = 'password'; code = ''"><Icon name="back" :size="16" />Back</button>
            </form>

            <p v-if="error" class="notice-err mt-5" role="alert"><Icon name="alert" :size="18" class="mt-px" />{{ error }}</p>
          </div>
        </Transition>

        <p class="mt-10 text-center text-xs leading-relaxed text-ink-muted">
          Demo portal with a fictional carrier and fictional data. To help protect your account, Nimbus looks at how you
          type and move (timing and motion only, never what you type).
        </p>
      </div>
    </section>
  </main>
</template>
