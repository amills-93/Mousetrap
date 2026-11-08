<script setup lang="ts">
const { data, refresh } = await useAccount();
const msg = ref<{ ok: boolean; text: string } | null>(null);
const busy = ref(false);

async function run(path: string, body: unknown, okText: string) {
  busy.value = true;
  const err = await accountAction(path, body);
  busy.value = false;
  msg.value = err ? { ok: false, text: err } : { ok: true, text: okText };
  if (!err) await refresh();
}

const pay = (billId: string) => run("/api/account/billing/pay", { billId }, "Payment received. Thank you!");
const toggleAutopay = () => run("/api/account/billing/autopay", { enabled: !data.value!.account.autopay }, `Autopay turned ${data.value!.account.autopay ? "off" : "on"}`);
</script>

<template>
  <div v-if="data" class="space-y-5">
    <PageHeader title="Billing" subtitle="Pay your bill, manage autopay and see past statements." />

    <div class="grid gap-5 md:grid-cols-2">
      <section class="card-hero">
        <p class="text-[13px] font-medium text-nimbus-300">Balance due</p>
        <p class="mt-3 font-display text-5xl font-semibold tracking-tight tabular-nums">{{ money(data.balanceDue) }}</p>
      </section>
      <Card title="Autopay" subtitle="Pay your bill automatically on the due date.">
        <template #action>
          <button
            role="switch"
            :aria-checked="data.account.autopay"
            aria-label="Autopay"
            :disabled="busy"
            class="relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-50"
            :class="data.account.autopay ? 'bg-nimbus' : 'bg-nimbus-200'"
            @click="toggleAutopay"
          >
            <span class="absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all" :class="data.account.autopay ? 'left-6' : 'left-1'" />
          </button>
        </template>
        <p class="flex items-center gap-2 text-sm" :class="data.account.autopay ? 'text-emerald-700' : 'text-ink-muted'">
          <span class="h-2 w-2 rounded-full" :class="data.account.autopay ? 'bg-emerald-500' : 'bg-nimbus-300'" />
          {{ data.account.autopay ? "On" : "Off" }}
        </p>
      </Card>
    </div>

    <Notice :msg="msg" />

    <Card title="Bill history">
      <div class="-mx-6 overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-xs uppercase tracking-wider text-ink-muted">
            <tr class="border-b border-ink-line">
              <th class="px-6 py-2.5 font-medium">Period</th>
              <th class="px-3 py-2.5 font-medium">Due</th>
              <th class="px-3 py-2.5 text-right font-medium">Amount</th>
              <th class="px-6 py-2.5 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-ink-line">
            <tr v-for="b in data.bills" :key="b.id" class="transition hover:bg-ink-wash/60">
              <td class="whitespace-nowrap px-6 py-3.5 font-medium">{{ b.period }}</td>
              <td class="whitespace-nowrap px-3 text-ink-muted">{{ shortDate(b.dueDate) }}</td>
              <td class="px-3 text-right tabular-nums">{{ money(b.amount) }}</td>
              <td class="px-6 text-right">
                <span v-if="b.paid" class="badge bg-emerald-50 text-emerald-700"><Icon name="check" :size="14" />Paid</span>
                <button v-else :disabled="busy" class="btn-primary !px-3 !py-1.5 text-xs" @click="pay(b.id)">Pay {{ money(b.amount) }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
