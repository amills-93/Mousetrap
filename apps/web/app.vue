<script setup lang="ts">
const { demoMode } = useRuntimeConfig().public;
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <ClientOnly>
    <DevOverlay v-if="demoMode" />
  </ClientOnly>
</template>
