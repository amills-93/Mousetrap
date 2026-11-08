<!-- Result line for a form action: { ok, text } or null. -->
<script setup lang="ts">
defineProps<{ msg: { ok: boolean; text: string } | null }>();
</script>

<template>
  <Transition enter-from-class="opacity-0 -translate-y-1" enter-active-class="transition duration-200">
    <p v-if="msg" :class="msg.ok ? 'notice-ok' : 'notice-err'" :role="msg.ok ? 'status' : 'alert'">
      <Icon :name="msg.ok ? 'check' : 'alert'" :size="18" class="mt-px" />
      <span>{{ msg.text }}</span>
    </p>
  </Transition>
</template>
