<script setup lang="ts">
// 底部动作面板：点遮罩关闭，内容由 slot 提供（聊天菜单 / 附加功能等）
withDefaults(
  defineProps<{
    show: boolean
    /** 平角变体（聊天页内使用，与原型 sheet--flat 一致） */
    flat?: boolean
  }>(),
  { flat: false },
)

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <!-- 不用 Transition（后台标签 rAF 停止会卡住离场导致遮罩残留），入场动效由 CSS 动画完成 -->
  <div v-if="show" class="overlay overlay--fade-in" @click.self="emit('close')">
    <div class="sheet" :class="{ 'sheet--flat': flat }">
      <div class="sheet-handle"></div>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.overlay--fade-in {
  animation: fadeIn 0.2s ease;
}
</style>
