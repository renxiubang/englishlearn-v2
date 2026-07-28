<script setup lang="ts">
// 按住说话浮层：显示"松开发送 · 上滑取消"，取消态变红显示 ✕（对应原型 #talkHint）
import { talkState } from '@/composables/useTalk'
</script>

<template>
  <div class="talk-hint" :class="{ show: talkState.active, cancel: talkState.cancel }" role="status">
    <div class="th-visual">
      <div class="th-wave"><i></i><i></i><i></i><i></i><i></i></div>
      <div class="th-cancel-ic">✕</div>
    </div>
    <div class="th-text">{{ talkState.cancel ? '松开手指，取消发送' : '松开发送 · 上滑取消' }}</div>
  </div>
</template>

<style scoped>
.talk-hint {
  position: absolute;
  left: 50%;
  bottom: 80px;
  transform: translateX(-50%) scale(0.94);
  z-index: 96;
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: var(--spacing-lg) 22px;
  border-radius: 22px;
  background: rgba(5, 7, 10, 0.9);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3);
  opacity: 0;
  transition: opacity 0.18s ease, transform 0.18s ease, background 0.15s ease;
  pointer-events: none;
  white-space: nowrap;
}
.talk-hint.show {
  display: flex;
  opacity: 1;
  transform: translateX(-50%) scale(1);
}
.talk-hint.cancel {
  background: var(--accent-color);
}
.th-visual {
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.th-wave {
  display: flex;
  gap: 3px;
  align-items: center;
  height: 20px;
}
.th-wave i {
  width: 3px;
  background: #fff;
  border-radius: 2px;
  animation: wave 0.6s ease-in-out infinite;
}
.th-wave i:nth-child(1) { height: 8px; animation-delay: 0s; }
.th-wave i:nth-child(2) { height: 16px; animation-delay: 0.1s; }
.th-wave i:nth-child(3) { height: 11px; animation-delay: 0.2s; }
.th-wave i:nth-child(4) { height: 18px; animation-delay: 0.15s; }
.th-wave i:nth-child(5) { height: 9px; animation-delay: 0.05s; }
.th-cancel-ic {
  display: none;
  font-size: 20px;
  line-height: 1;
}
.talk-hint.cancel .th-wave { display: none; }
.talk-hint.cancel .th-cancel-ic { display: block; }
</style>
