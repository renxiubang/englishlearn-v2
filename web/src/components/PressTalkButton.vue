<script setup lang="ts">
// 按住说话按钮：mousedown 开始录音态，mouseup 松开发送，上移 60px 取消（联动全局 TalkHint 浮层）
import { ref } from 'vue'
import { beginTalk, talkState } from '@/composables/useTalk'
import { toast } from '@/composables/useToast'

const props = withDefaults(
  defineProps<{
    /** 常态文案，如"按住 说话" */
    label: string
    /** 按住中的文案，缺省沿用 label */
    pressingLabel?: string
    disabled?: boolean
    /** 取消时是否弹"已取消"toast（原型行为），默认开启 */
    cancelToast?: boolean
  }>(),
  { pressingLabel: undefined, disabled: false, cancelToast: true },
)

const emit = defineEmits<{
  /** 开始按住 */
  start: []
  /** 松开发送（未取消） */
  send: []
  /** 上移取消 */
  cancel: []
}>()

const pressing = ref(false)

function onDown(e: MouseEvent) {
  if (props.disabled || e.button !== 0) return
  pressing.value = true
  emit('start')
  beginTalk(e, cancelled => {
    pressing.value = false
    if (cancelled) {
      if (props.cancelToast) toast('已取消')
      emit('cancel')
    } else {
      emit('send')
    }
  })
}
</script>

<template>
  <button
    type="button"
    class="press-talk"
    :class="{ pressing, 'cancel-talk': pressing && talkState.cancel }"
    :disabled="disabled"
    @mousedown="onDown"
  >
    <slot :pressing="pressing">
      <span class="label">{{ pressing ? pressingLabel ?? label : label }}</span>
    </slot>
  </button>
</template>

<style scoped>
.press-talk {
  border: none;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease, color 0.15s ease, transform 0.12s ease;
}
.press-talk .label {
  display: inline-flex;
  align-items: center;
  line-height: 1;
}
.press-talk.pressing {
  background: var(--accent-color);
  color: #fff;
  transform: scale(0.98);
}
.press-talk.cancel-talk {
  background: var(--accent-color) !important;
  color: #fff !important;
}
.press-talk:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>
