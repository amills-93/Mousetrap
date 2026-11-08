<script setup lang="ts">
const { data } = await useAccount();
const nextBill = computed(() => data.value?.bills.find((b) => !b.paid));
</script>

<template>
  <div v-if="data" class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-nimbus">Hi, {{ data.user.name.split(" ")[0] }}</h1>
      <p class="text-sm text-gray-500">Account {{ data.account.accountNumber }}</p>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <Card title="Balance due">
        <p class="text-3xl font-semibold">{{ money(data.balanceDue) }}</p>
        <p v-if="nextBill" class="text-sm text-gray-500 mt-1">Due {{ shortDate(nextBill.dueDate) }} · {{ nextBill.period }}</p>
        <p v-else class="text-sm text-green-700 mt-1">You're all paid up.</p>
        <div class="mt-4 flex items-center gap-4">
          <NuxtLink to="/billing" class="rounded bg-nimbus text-white px-4 py-2 text-sm font-medium">{{ nextBill ? "Pay bill" : "View bills" }}</NuxtLink>
          <span class="text-sm text-gray-500">Autopay {{ data.account.autopay ? "on" : "off" }}</span>
        </div>
      </Card>
      <Card title="Your plan">
        <p class="text-3xl font-semibold">{{ data.lines.length }} <span class="text-base font-normal text-gray-500">lines</span></p>
        <p class="text-sm text-gray-500 mt-1">{{ [...new Set(data.lines.map((l) => l.plan))].join(", ") }}</p>
        <NuxtLink to="/lines" class="mt-4 inline-block text-sm text-nimbus font-medium hover:underline">Manage lines →</NuxtLink>
      </Card>
    </div>

    <Card title="Data usage this cycle">
      <ul class="space-y-4">
        <li v-for="l in data.lines" :key="l.id">
          <div class="flex justify-between text-sm mb-1">
            <NuxtLink :to="`/lines/${l.id}`" class="font-medium hover:underline">{{ l.nickname }}</NuxtLink>
            <span class="text-gray-500">{{ l.phone }}</span>
          </div>
          <UsageBar :used="l.dataUsedGb" :allowance="l.dataAllowanceGb" />
        </li>
      </ul>
    </Card>
  </div>
</template>
