<script setup lang="ts">
const { data } = await useAccount();
const { data: messages } = useMessages();
const nextBill = computed(() => data.value?.bills.find((b) => !b.paid));
const flagged = computed(() => (messages.value ?? []).filter(needsReview).length);
const greeting = computed(() => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
});
</script>

<template>
  <div v-if="data" class="space-y-6">
    <PageHeader :eyebrow="`Account ${data.account.accountNumber}`" :title="`${greeting}, ${data.user.name.split(' ')[0]}`" />

    <div class="grid gap-5 md:grid-cols-3">
      <section class="card-hero relative overflow-hidden md:col-span-2">
        <svg viewBox="0 0 200 200" class="pointer-events-none absolute -right-10 -top-10 h-64 w-64 text-white/[0.06]" aria-hidden="true">
          <circle cx="160" cy="40" r="40" fill="none" stroke="currentColor" stroke-width="14" />
          <circle cx="160" cy="40" r="80" fill="none" stroke="currentColor" stroke-width="14" />
          <circle cx="160" cy="40" r="120" fill="none" stroke="currentColor" stroke-width="14" />
        </svg>
        <p class="text-[13px] font-medium text-nimbus-300">Balance due</p>
        <p class="mt-3 font-display text-5xl font-semibold tracking-tight tabular-nums">{{ money(data.balanceDue) }}</p>
        <p v-if="nextBill" class="mt-2 text-sm text-nimbus-200">Due {{ shortDate(nextBill.dueDate) }} · {{ nextBill.period }}</p>
        <p v-else class="mt-2 flex items-center gap-1.5 text-sm text-emerald-300"><Icon name="check" :size="16" />You're all paid up.</p>
        <div class="mt-6 flex flex-wrap items-center gap-4">
          <NuxtLink to="/billing" class="btn-accent">{{ nextBill ? "Pay bill" : "View bills" }}</NuxtLink>
          <span class="flex items-center gap-2 text-[13px] text-nimbus-300">
            <span class="h-2 w-2 rounded-full" :class="data.account.autopay ? 'bg-emerald-400' : 'bg-nimbus-400'" />
            Autopay {{ data.account.autopay ? "on" : "off" }}
          </span>
        </div>
      </section>

      <NuxtLink to="/lines" class="card-link flex flex-col">
        <p class="eyebrow">Your plan</p>
        <p class="stat mt-3">{{ data.lines.length }} <span class="font-sans text-base font-normal text-ink-muted">lines</span></p>
        <p class="mt-2 text-sm text-ink-soft">{{ [...new Set(data.lines.map((l) => l.plan))].join(", ") }}</p>
        <span class="link mt-auto inline-flex items-center gap-1 pt-4 text-sm">Manage lines <Icon name="arrow" :size="16" /></span>
      </NuxtLink>
    </div>

    <Card title="Data this cycle">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NuxtLink v-for="l in data.lines" :key="l.id" :to="`/lines/${l.id}`" class="rounded-xl border border-ink-line p-4 transition hover:border-nimbus-200 hover:shadow-lift">
          <div class="mb-3 flex items-baseline justify-between gap-2 text-sm">
            <span class="truncate font-semibold">{{ l.nickname }}</span>
            <span class="shrink-0 text-xs text-ink-muted">{{ l.phone }}</span>
          </div>
          <UsageBar :used="l.dataUsedGb" :allowance="l.dataAllowanceGb" big />
        </NuxtLink>
      </div>
    </Card>

    <NuxtLink to="/messages" class="card-link flex items-center gap-4 !py-5">
      <span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl" :class="flagged ? 'bg-rose-50 text-rose-600' : 'bg-nimbus-50 text-nimbus'">
        <Icon name="shield" :size="22" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="block font-semibold">Scam Shield is on</span>
        <span class="block text-sm text-ink-muted">
          <template v-if="flagged">{{ flagged }} flagged {{ flagged === 1 ? "text needs" : "texts need" }} a look.</template>
          <template v-else>No flagged texts.</template>
          Nimbus never asks for codes or PINs.
        </span>
      </span>
      <Icon name="arrow" class="text-nimbus" />
    </NuxtLink>
  </div>
</template>
