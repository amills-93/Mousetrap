<script setup lang="ts">
const { demoMode } = useRuntimeConfig().public;
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <ClientOnly>
    <StepUpModal />
    <ScamPauseModal />
    <DevOverlay v-if="demoMode" />
  </ClientOnly>
</template>
