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
  reloadTo(redirectTo.value);
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
  <main class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <div class="bg-white rounded-xl shadow p-8 max-w-sm w-full">
      <h1 class="text-2xl font-semibold text-nimbus">Nimbus Mobile</h1>
      <p v-if="signedOutReason" class="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{{ signedOutReason }}</p>
      <p v-if="session && step === 'password'" class="text-sm text-gray-500 mt-1">
        Signed in as {{ session.user.email }}. Sign in below to add another account.
        <NuxtLink to="/" class="text-nimbus underline">Back to portal</NuxtLink>
      </p>
      <p v-else class="text-sm text-gray-500 mt-1">
        {{ step === "password" ? "Sign in to your account" : "Enter the 6-digit code from your authenticator app" }}
      </p>

      <form v-if="step === 'password'" class="mt-6 space-y-4" @submit.prevent="submitPassword">
        <label class="block text-sm">
          Email
          <input v-model="email" type="email" autocomplete="username" required class="mt-1 w-full rounded border-gray-300 border px-3 py-2" />
        </label>
        <label class="block text-sm">
          Password
          <input v-model="password" type="password" autocomplete="current-password" required class="mt-1 w-full rounded border-gray-300 border px-3 py-2" />
        </label>
        <button :disabled="busy" class="w-full rounded bg-nimbus text-white py-2 font-medium disabled:opacity-50">Sign in</button>
      </form>

      <form v-else class="mt-6 space-y-4" @submit.prevent="submitTotp">
        <label class="block text-sm">
          Authentication code
          <input v-model="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required autofocus class="mt-1 w-full rounded border-gray-300 border px-3 py-2 tracking-widest text-center text-lg" />
        </label>
        <button :disabled="busy" class="w-full rounded bg-nimbus text-white py-2 font-medium disabled:opacity-50">Verify</button>
        <button type="button" class="w-full text-sm text-gray-500" @click="step = 'password'; code = ''">Back</button>
      </form>

      <p v-if="error" class="mt-4 text-sm text-red-600">{{ error }}</p>
    </div>
  </main>
</template>
