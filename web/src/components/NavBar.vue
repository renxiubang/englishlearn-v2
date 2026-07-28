<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{
    title: string
    /** 显示返回按钮，并指定返回目标（默认浏览器后退） */
    back?: boolean
    backTo?: string
  }>(),
  { back: false, backTo: '' },
)

const emit = defineEmits<{ back: [] }>()
const router = useRouter()

function onBack() {
  emit('back')
  if (props.backTo) router.push(props.backTo)
  else router.back()
}
</script>

<template>
  <header class="navbar">
    <button v-if="back" class="icon-btn" @click="onBack">
      <svg class="licon" width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
    </button>
    <span class="title"><slot name="title">{{ title }}</slot></span>
    <slot name="right">
      <span class="navbar-spacer"></span>
    </slot>
  </header>
</template>

<style>
.navbar {
  flex: none;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-md);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.navbar .title {
  font-size: var(--font-size-lg);
  font-weight: 700;
}
.navbar-spacer {
  width: var(--touch-target);
  flex: none;
}
.icon-btn {
  width: var(--touch-target);
  height: var(--touch-target);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: var(--color-ink);
}
.icon-btn:active {
  background: rgba(0, 0, 0, 0.06);
}
.icon-btn--sm {
  width: 30px;
  height: 30px;
}
</style>
