<script setup lang="ts">
const { data } = await useAccount();
</script>

<template>
  <div v-if="data" class="space-y-6">
    <h1 class="text-2xl font-semibold text-nimbus">Lines</h1>
    <div class="grid gap-4 sm:grid-cols-2">
      <Card v-for="l in data.lines" :key="l.id">
        <div class="flex justify-between items-start">
          <div>
            <p class="font-medium">{{ l.nickname }}</p>
            <p class="text-sm text-gray-500">{{ l.phone }}</p>
          </div>
          <span class="text-xs rounded-full bg-nimbus/10 text-nimbus px-2 py-0.5">{{ l.plan }}</span>
        </div>
        <p class="text-sm text-gray-600 mt-3">{{ l.deviceName }} · SIM ••{{ l.simIccidLast4 }}</p>
        <div class="mt-3"><UsageBar :used="l.dataUsedGb" :allowance="l.dataAllowanceGb" /></div>
        <NuxtLink :to="`/lines/${l.id}`" class="mt-4 inline-block text-sm text-nimbus font-medium hover:underline">Manage line →</NuxtLink>
      </Card>
    </div>
  </div>
</template>
