<script setup lang="ts">
// Multi-step sign-up. The login is created first, so every later step is typed inside a signed-in session
// and the collector's timing reaches passive enrollment (ARCHITECTURE.md 8.1) as a typing baseline. Only
// timing and key class are collected, never what is typed (principle 3). The last step pairs an authenticator.
import { renderSVG } from "uqr";

definePageMeta({ layout: false });

type Step = "login" | "address" | "line" | "sign" | "mfa" | "codes";
const STEPS: { id: Step; label: string }[] = [
  { id: "login", label: "Login" },
  { id: "address", label: "Address" },
  { id: "line", label: "Your line" },
  { id: "sign", label: "Agreement" },
  { id: "mfa", label: "Authenticator" },
];
const PLANS = [
  { name: "Nimbus Unlimited", price: 70, blurb: "50 GB high-speed, then unlimited" },
  { name: "Nimbus Essentials", price: 50, blurb: "15 GB high-speed data" },
  { name: "Nimbus Basic", price: 30, blurb: "5 GB, talk and text" },
];
const STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
const AGREEMENT = "I agree to the Nimbus service terms";

const step = ref<Step>("login");
const stepIndex = computed(() => STEPS.findIndex((s) => s.id === (step.value === "codes" ? "mfa" : step.value)));
const error = ref("");
const busy = ref(false);

const login = reactive({ name: "", email: "", password: "", confirm: "" });
const address = reactive({ street: "", unit: "", city: "", state: "TX", zip: "" });
const line = reactive({ plan: PLANS[0].name, nickname: "", pin: "", pinConfirm: "" });
const sign = reactive({ name: "", agreement: "" });
const mfa = reactive({ password: "", uri: "", code: "", backupCodes: [] as string[], copied: false });
const accountName = ref("");

const norm = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();
const nameSigned = computed(() => norm(sign.name) === norm(accountName.value));
const agreementSigned = computed(() => norm(sign.agreement) === norm(AGREEMENT));
const qrSvg = computed(() => (mfa.uri ? renderSVG(mfa.uri, { border: 1 }) : ""));
const manualKey = computed(() => {
  const secret = mfa.uri ? new URL(mfa.uri).searchParams.get("secret") ?? "" : "";
  return secret.replace(/(.{4})/g, "$1 ").trim();
});

// Resume an unfinished sign-up for the signed-in user; a finished account starts a fresh sign-up.
const { data: session } = await useAuthSession();
onMounted(async () => {
  if (!session.value) return;
  const status = await $fetch("/api/signup/status").catch(() => null);
  if (!status || status.complete) return;
  accountName.value = status.name;
  step.value = status.hasAccount ? "mfa" : "address";
});

function go(next: Step) {
  error.value = "";
  step.value = next;
}

function fail(err: unknown, fallback: string) {
  const e = err as { message?: string; data?: { statusMessage?: string }; statusMessage?: string };
  error.value = e?.data?.statusMessage || e?.statusMessage || e?.message || fallback;
}

async function submitLogin() {
  error.value = "";
  if (login.password !== login.confirm) return (error.value = "Passwords don't match");
  busy.value = true;
  const { error: err } = await authClient.signUp.email({ name: login.name.trim(), email: login.email.trim(), password: login.password });
  busy.value = false;
  if (err) return fail(err, "Couldn't create your login");
  accountName.value = login.name.trim();
  login.password = login.confirm = "";
  go("address");
}

function submitLine() {
  error.value = "";
  if (line.pin !== line.pinConfirm) return (error.value = "PINs don't match");
  go("sign");
}

async function submitSign() {
  if (!nameSigned.value || !agreementSigned.value) return (error.value = "Type your name and the statement exactly as shown");
  busy.value = true;
  error.value = "";
  try {
    await $fetch("/api/signup/account", {
      method: "POST",
      body: { ...address, plan: line.plan, nickname: line.nickname, portPin: line.pin },
    });
    line.pin = line.pinConfirm = "";
    go("mfa");
  } catch (err) {
    fail(err, "Couldn't create your account");
  } finally {
    busy.value = false;
  }
}

async function startMfa() {
  busy.value = true;
  error.value = "";
  const { data, error: err } = await authClient.twoFactor.enable({ password: mfa.password });
  busy.value = false;
  if (err || !data || !("totpURI" in data)) return fail(err, "Couldn't start authenticator setup");
  mfa.password = "";
  mfa.uri = data.totpURI;
  mfa.backupCodes = data.backupCodes;
}

async function verifyMfa() {
  busy.value = true;
  error.value = "";
  const { error: err } = await authClient.twoFactor.verifyTotp({ code: mfa.code.trim() });
  busy.value = false;
  if (err) return fail(err, "That code didn't match. Check the time on your phone and try the next one.");
  go("codes");
}

async function copyKey() {
  await navigator.clipboard?.writeText(manualKey.value.replace(/ /g, "")).catch(() => {});
  mfa.copied = true;
  setTimeout(() => (mfa.copied = false), 1500);
}
</script>

<template>
  <main class="flex min-h-screen flex-col lg:flex-row">
    <section class="relative flex flex-col justify-between gap-8 overflow-hidden bg-nimbus-950 px-6 py-8 text-white sm:px-12 lg:w-[40%] lg:py-14">
      <svg viewBox="0 0 400 400" class="pointer-events-none absolute -bottom-40 -right-40 h-[36rem] w-[36rem] text-white/[0.04]" aria-hidden="true">
        <circle v-for="r in [60, 120, 180]" :key="r" cx="200" cy="200" :r="r" fill="none" stroke="currentColor" stroke-width="24" />
      </svg>
      <NuxtLink to="/login" class="relative w-fit"><NimbusLogo /></NuxtLink>
      <div class="relative hidden max-w-md lg:block">
        <h1 class="font-display text-5xl font-semibold leading-[1.05] tracking-tight">Join Nimbus in a few minutes.</h1>
        <p class="mt-4 text-base leading-relaxed text-nimbus-200">
          Set up your login, your line, and your authenticator. Your number is protected from the first day.
        </p>
      </div>
      <ol class="relative flex gap-2 lg:flex-col lg:gap-3" aria-label="Sign-up progress">
        <li v-for="(s, i) in STEPS" :key="s.id" class="flex items-center gap-3 text-sm" :aria-current="i === stepIndex ? 'step' : undefined">
          <span
            class="grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold transition"
            :class="i < stepIndex ? 'bg-nimbus-accent text-nimbus-950' : i === stepIndex ? 'bg-white text-nimbus-950' : 'bg-white/10 text-nimbus-200'"
          >
            <Icon v-if="i < stepIndex" name="check" :size="14" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <span class="hidden lg:inline" :class="i === stepIndex ? 'font-medium text-white' : 'text-nimbus-200'">{{ s.label }}</span>
        </li>
      </ol>
    </section>

    <section class="flex flex-1 items-center justify-center px-6 py-12">
      <div class="w-full max-w-md">
        <Transition mode="out-in" enter-from-class="opacity-0 translate-x-2" enter-active-class="transition duration-200" leave-to-class="opacity-0 -translate-x-2" leave-active-class="transition duration-150">
          <div :key="step">
            <p class="eyebrow">Step {{ stepIndex + 1 }} of {{ STEPS.length }}</p>

            <!-- 1. Login -->
            <template v-if="step === 'login'">
              <h2 class="mt-1 text-3xl font-semibold">Create your login</h2>
              <p class="mt-2 text-sm text-ink-muted">
                Already with Nimbus? <NuxtLink to="/login" class="link">Sign in</NuxtLink>
              </p>
              <form class="mt-8 space-y-5" @submit.prevent="submitLogin">
                <label class="label">Full name
                  <input v-model="login.name" autocomplete="name" required maxlength="80" class="input" />
                </label>
                <label class="label">Email
                  <input v-model="login.email" type="email" autocomplete="email" required class="input" />
                </label>
                <div class="grid gap-5 sm:grid-cols-2">
                  <label class="label">Password
                    <input v-model="login.password" type="password" autocomplete="new-password" required minlength="8" class="input" />
                  </label>
                  <label class="label">Confirm password
                    <input v-model="login.confirm" type="password" autocomplete="new-password" required minlength="8" class="input" />
                  </label>
                </div>
                <p class="text-xs text-ink-muted">At least 8 characters.</p>
                <button :disabled="busy" class="btn-primary w-full !py-3 text-[15px]">{{ busy ? "Creating login…" : "Continue" }}<Icon v-if="!busy" name="arrow" :size="16" /></button>
              </form>
            </template>

            <!-- 2. Address -->
            <template v-else-if="step === 'address'">
              <h2 class="mt-1 text-3xl font-semibold">Service address</h2>
              <p class="mt-2 text-sm text-ink-muted">Where you'll mostly use your line. We use it for coverage and billing.</p>
              <form class="mt-8 space-y-5" @submit.prevent="go('line')">
                <label class="label">Street address
                  <input v-model="address.street" autocomplete="address-line1" required maxlength="120" class="input" />
                </label>
                <label class="label">Apartment, suite, unit <span class="font-normal text-ink-muted">(optional)</span>
                  <input v-model="address.unit" autocomplete="address-line2" maxlength="30" class="input" />
                </label>
                <div class="grid grid-cols-6 gap-4">
                  <label class="label col-span-6 sm:col-span-3">City
                    <input v-model="address.city" autocomplete="address-level2" required maxlength="60" class="input" />
                  </label>
                  <label class="label col-span-3 sm:col-span-1">State
                    <select v-model="address.state" autocomplete="address-level1" required class="input !px-2">
                      <option v-for="s in STATES" :key="s" :value="s">{{ s }}</option>
                    </select>
                  </label>
                  <label class="label col-span-3 sm:col-span-2">ZIP
                    <input v-model="address.zip" autocomplete="postal-code" inputmode="numeric" required pattern="\d{5}" maxlength="5" class="input" />
                  </label>
                </div>
                <button class="btn-primary w-full !py-3 text-[15px]">Continue<Icon name="arrow" :size="16" /></button>
              </form>
            </template>

            <!-- 3. Line -->
            <template v-else-if="step === 'line'">
              <h2 class="mt-1 text-3xl font-semibold">Set up your line</h2>
              <p class="mt-2 text-sm text-ink-muted">Pick a plan and protect your number. You can change your plan any time.</p>
              <form class="mt-8 space-y-5" @submit.prevent="submitLine">
                <fieldset class="space-y-2.5">
                  <legend class="label mb-1.5">Plan</legend>
                  <label
                    v-for="p in PLANS"
                    :key="p.name"
                    class="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition"
                    :class="line.plan === p.name ? 'border-nimbus bg-nimbus-50 shadow-focus' : 'border-ink-line hover:border-nimbus-200'"
                  >
                    <input v-model="line.plan" type="radio" name="plan" :value="p.name" class="sr-only" />
                    <span class="flex-1">
                      <span class="block text-sm font-semibold text-ink">{{ p.name }}</span>
                      <span class="block text-xs text-ink-muted">{{ p.blurb }}</span>
                    </span>
                    <span class="font-display text-lg font-semibold tabular-nums">${{ p.price }}<span class="text-xs font-normal text-ink-muted">/mo</span></span>
                  </label>
                </fieldset>
                <label class="label">Line name
                  <input v-model="line.nickname" required maxlength="30" placeholder="e.g. My phone" class="input" />
                </label>
                <div>
                  <div class="grid gap-4 sm:grid-cols-2">
                    <label class="label">Port-out PIN
                      <input v-model="line.pin" type="password" inputmode="numeric" autocomplete="off" required pattern="\d{6}" maxlength="6" class="input tracking-[0.3em]" />
                    </label>
                    <label class="label">Confirm PIN
                      <input v-model="line.pinConfirm" type="password" inputmode="numeric" autocomplete="off" required pattern="\d{6}" maxlength="6" class="input tracking-[0.3em]" />
                    </label>
                  </div>
                  <p class="mt-2 flex gap-2 text-xs text-ink-muted"><Icon name="shield" :size="16" class="shrink-0" />6 digits. Another carrier needs this PIN to move your number, which blocks most SIM-swap scams.</p>
                </div>
                <div class="flex gap-3">
                  <button type="button" class="btn-ghost" @click="go('address')"><Icon name="back" :size="16" />Back</button>
                  <button class="btn-primary flex-1 !py-3 text-[15px]">Continue<Icon name="arrow" :size="16" /></button>
                </div>
              </form>
            </template>

            <!-- 4. Agreement: a typed e-signature -->
            <template v-else-if="step === 'sign'">
              <h2 class="mt-1 text-3xl font-semibold">Review and sign</h2>
              <dl class="card mt-6 grid grid-cols-[auto,1fr] gap-x-6 gap-y-2 !p-5 text-sm">
                <dt class="text-ink-muted">Plan</dt><dd class="font-medium">{{ line.plan }} · {{ line.nickname }}</dd>
                <dt class="text-ink-muted">Address</dt>
                <dd class="font-medium">{{ address.street }}<template v-if="address.unit">, {{ address.unit }}</template>, {{ address.city }}, {{ address.state }} {{ address.zip }}</dd>
                <dt class="text-ink-muted">Monthly</dt><dd class="font-medium">${{ PLANS.find((p) => p.name === line.plan)?.price }} plus taxes</dd>
              </dl>
              <form class="mt-6 space-y-5" @submit.prevent="submitSign">
                <label class="label">Type your full name to sign
                  <input v-model="sign.name" autocomplete="off" spellcheck="false" required :placeholder="accountName" class="input font-display italic" @paste.prevent @drop.prevent />
                </label>
                <label class="label">Type: <span class="font-semibold text-ink">“{{ AGREEMENT }}”</span>
                  <input v-model="sign.agreement" autocomplete="off" spellcheck="false" required class="input" @paste.prevent @drop.prevent />
                </label>
                <div class="flex gap-3">
                  <button type="button" class="btn-ghost" @click="go('line')"><Icon name="back" :size="16" />Back</button>
                  <button :disabled="busy || !nameSigned || !agreementSigned" class="btn-primary flex-1 !py-3 text-[15px]">{{ busy ? "Creating account…" : "Sign and create account" }}</button>
                </div>
              </form>
            </template>

            <!-- 5. Authenticator -->
            <template v-else-if="step === 'mfa'">
              <h2 class="mt-1 text-3xl font-semibold">Add your authenticator</h2>
              <template v-if="!mfa.uri">
                <p class="mt-2 text-sm text-ink-muted">
                  Nimbus asks for a 6-digit code from an authenticator app when you sign in and before big changes, like moving your number. Confirm your password to start.
                </p>
                <form class="mt-8 space-y-5" @submit.prevent="startMfa">
                  <label class="label">Password
                    <input v-model="mfa.password" type="password" autocomplete="current-password" required class="input" />
                  </label>
                  <button :disabled="busy" class="btn-primary w-full !py-3 text-[15px]">{{ busy ? "Preparing…" : "Continue" }}</button>
                </form>
              </template>
              <template v-else>
                <p class="mt-2 text-sm text-ink-muted">Scan this with Google Authenticator, Microsoft Authenticator, 1Password, or any TOTP app.</p>
                <div class="mt-6 flex flex-col items-center gap-5 sm:flex-row sm:items-start">
                  <div class="w-44 shrink-0 rounded-2xl border border-ink-line bg-white p-2" role="img" aria-label="QR code for your authenticator app" v-html="qrSvg" />
                  <div class="min-w-0 text-sm">
                    <p class="text-ink-muted">Can't scan? Enter this key:</p>
                    <p class="mt-1 break-all font-mono text-[13px] font-semibold tracking-wide text-ink">{{ manualKey }}</p>
                    <button type="button" class="btn-secondary mt-3 !py-1.5 !text-xs" @click="copyKey">{{ mfa.copied ? "Copied" : "Copy key" }}</button>
                  </div>
                </div>
                <form class="mt-8 space-y-5" @submit.prevent="verifyMfa">
                  <label class="label">Code from your app
                    <input v-model="mfa.code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required placeholder="000000" class="input text-center font-display text-2xl tracking-[0.5em]" />
                  </label>
                  <button :disabled="busy" class="btn-primary w-full !py-3 text-[15px]">{{ busy ? "Verifying…" : "Verify and finish" }}</button>
                </form>
              </template>
            </template>

            <!-- Backup codes -->
            <template v-else>
              <span class="mb-5 mt-3 grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-700"><Icon name="check" :size="24" /></span>
              <h2 class="text-3xl font-semibold">You're all set</h2>
              <p class="mt-2 text-sm text-ink-muted">Save these backup codes somewhere safe. Each one works once if you lose your phone.</p>
              <ul class="card mt-6 grid grid-cols-2 gap-2 !p-5 font-mono text-sm">
                <li v-for="c in mfa.backupCodes" :key="c">{{ c }}</li>
              </ul>
              <button class="btn-primary mt-6 w-full !py-3 text-[15px]" @click="reloadTo('/')">I've saved them, go to my account<Icon name="arrow" :size="16" /></button>
            </template>

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
