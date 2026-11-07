<script setup lang="ts">
const { data: health } = await useFetch("/api/health");
</script>

<template>
  <main class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <div class="bg-white rounded-xl shadow p-8 max-w-md w-full">
      <h1 class="text-2xl font-semibold text-nimbus">Nimbus Mobile</h1>
      <p class="text-gray-500 mt-1">Scaffold is running.</p>
      <dl class="mt-6 space-y-2 text-sm">
        <div class="flex justify-between"><dt>Database</dt><dd :class="health?.db ? 'text-green-600' : 'text-red-600'">{{ health?.db ? "ok" : "down" }}</dd></div>
        <div class="flex justify-between"><dt>ML service</dt><dd :class="health?.ml ? 'text-green-600' : 'text-red-600'">{{ health?.ml ? "ok" : "down" }}</dd></div>
      </dl>
    </div>
  </main>
</template>
