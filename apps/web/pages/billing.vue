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
  <div v-if="data" class="space-y-6">
    <h1 class="text-2xl font-semibold text-nimbus">Billing</h1>

    <div class="grid gap-4 sm:grid-cols-2">
      <Card title="Balance due">
        <p class="text-3xl font-semibold">{{ money(data.balanceDue) }}</p>
      </Card>
      <Card title="Autopay">
        <div class="flex items-center justify-between">
          <p class="text-sm text-gray-600">Pay your bill automatically on the due date.</p>
          <button
            role="switch"
            :aria-checked="data.account.autopay"
            :disabled="busy"
            class="relative h-6 w-11 shrink-0 rounded-full transition"
            :class="data.account.autopay ? 'bg-nimbus' : 'bg-gray-300'"
            @click="toggleAutopay"
          >
            <span class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition" :class="data.account.autopay ? 'left-[22px]' : 'left-0.5'" />
          </button>
        </div>
      </Card>
    </div>

    <p v-if="msg" class="text-sm" :class="msg.ok ? 'text-green-700' : 'text-red-600'">{{ msg.text }}</p>

    <Card title="Bill history">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-gray-500">
            <tr><th class="py-2 font-normal">Period</th><th class="font-normal">Due</th><th class="font-normal text-right">Amount</th><th class="font-normal text-right">Status</th></tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="b in data.bills" :key="b.id">
              <td class="py-3">{{ b.period }}</td>
              <td>{{ shortDate(b.dueDate) }}</td>
              <td class="text-right">{{ money(b.amount) }}</td>
              <td class="text-right">
                <span v-if="b.paid" class="text-green-700">Paid</span>
                <button v-else :disabled="busy" class="rounded bg-nimbus text-white px-3 py-1 text-xs font-medium disabled:opacity-50" @click="pay(b.id)">Pay {{ money(b.amount) }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
