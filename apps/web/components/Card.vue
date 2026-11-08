<script setup lang="ts">
defineProps<{ title?: string }>();
</script>

<template>
  <section class="bg-white rounded-xl shadow-sm ring-1 ring-black/5 p-5">
    <h2 v-if="title" class="font-medium text-gray-900 mb-3">{{ title }}</h2>
    <slot />
  </section>
</template>
