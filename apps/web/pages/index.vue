<script setup lang="ts">
const { data: session } = await useAuthSession();
const { data: health } = await useFetch("/api/health");
</script>

<template>
  <section>
    <h1 class="text-2xl font-semibold text-nimbus">Welcome, {{ session?.user.name }}</h1>
    <p class="text-gray-500 mt-1">Account overview arrives in Stage 3.</p>
    <dl class="mt-6 bg-white rounded-xl shadow p-6 max-w-sm space-y-2 text-sm">
      <div class="flex justify-between"><dt>Database</dt><dd :class="health?.db ? 'text-green-600' : 'text-red-600'">{{ health?.db ? "ok" : "down" }}</dd></div>
      <div class="flex justify-between"><dt>ML service</dt><dd :class="health?.ml ? 'text-green-600' : 'text-red-600'">{{ health?.ml ? "ok" : "down" }}</dd></div>
    </dl>
  </section>
</template>
