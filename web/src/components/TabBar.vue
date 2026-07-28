<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'home', label: '首页', to: '/' },
  { key: 'contacts', label: '对话', to: '/contacts' },
  { key: 'share', label: '分享', to: '/share' },
  { key: 'profile', label: '我的', to: '/profile' },
] as const
</script>

<template>
  <nav class="tabbar">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="tab"
      :class="{ active: route.meta.tab === tab.key }"
      @click="router.push(tab.to)"
    >
      <svg v-if="tab.key === 'home'" class="ic licon" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V20h14V9.5" /></svg>
      <svg v-else-if="tab.key === 'contacts'" class="ic licon" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path d="M21 11.5a8 8 0 0 1-11.5 7.2L4 20l1.3-5A8 8 0 1 1 21 11.5z" /></svg>
      <svg v-else-if="tab.key === 'share'" class="ic licon" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M16 8l-5.5 2.5L8 16l5.5-2.5z" /></svg>
      <svg v-else class="ic licon" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="8" r="3.6" /><path d="M5 20c0-3.6 3.4-5.6 7-5.6s7 2 7 5.6" /></svg>
      {{ tab.label }}
    </button>
  </nav>
</template>

<style scoped>
.tabbar {
  flex: none;
  height: calc(64px + env(safe-area-inset-bottom, 0px));
  /* 把 Home Indicator 安全区留在按钮下方，按钮仍居于上方 64px 内 */
  padding-bottom: env(safe-area-inset-bottom, 0px);
  display: flex;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(18px);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.tab {
  flex: 1;
  border: none;
  background: none;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  color: var(--color-muted);
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.tab .ic {
  font-size: 21px;
  line-height: 1;
  display: inline-flex;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.tab.active {
  color: var(--primary-color);
}
.tab.active .ic {
  transform: scale(1.12);
}
</style>
