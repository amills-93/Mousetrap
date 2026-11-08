<script setup lang="ts">
const { data } = await useAccount();
</script>

<template>
  <div v-if="data">
    <PageHeader title="Lines" :subtitle="`${data.lines.length} lines on this account`" />
    <div class="grid gap-5 sm:grid-cols-2">
      <NuxtLink v-for="l in data.lines" :key="l.id" :to="`/lines/${l.id}`" class="card-link group">
        <div class="flex items-start gap-3">
          <span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-nimbus-50 text-nimbus"><Icon name="phone" :size="22" /></span>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold">{{ l.nickname }}</p>
            <p class="text-sm text-ink-muted">{{ l.phone }}</p>
          </div>
          <span class="badge bg-nimbus-50 text-nimbus">{{ l.plan }}</span>
        </div>
        <div class="mt-5"><UsageBar :used="l.dataUsedGb" :allowance="l.dataAllowanceGb" /></div>
        <div class="mt-5 flex items-center justify-between border-t border-ink-line pt-4 text-sm">
          <span class="text-ink-muted">{{ l.deviceName }} · SIM ••{{ l.simIccidLast4 }}</span>
          <span class="link inline-flex items-center gap-1">Manage <Icon name="arrow" :size="16" class="transition group-hover:translate-x-0.5" /></span>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>
