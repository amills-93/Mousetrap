<script setup lang="ts">
const { demoMode } = useRuntimeConfig().public;
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <ClientOnly>
    <StepUpModal />
    <DevOverlay v-if="demoMode" />
  </ClientOnly>
</template>
