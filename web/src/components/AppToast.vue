<script setup lang="ts">
import { toastState } from '@/composables/useToast'
</script>

<template>
  <Transition name="toast">
    <div v-if="toastState.visible" class="app-toast" role="status">{{ toastState.message }}</div>
  </Transition>
</template>

<style scoped>
.app-toast {
  position: absolute;
  left: 50%;
  bottom: 120px;
  transform: translateX(-50%);
  z-index: 99;
  background: rgba(15, 23, 42, 0.86);
  color: #fff;
  padding: 9px 16px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  max-width: 80%;
  text-align: center;
  pointer-events: none;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.18s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>
