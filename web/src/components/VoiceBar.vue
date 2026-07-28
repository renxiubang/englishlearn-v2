<script setup lang="ts">
// 语音条：喇叭 + 静态波形 + 时长。传入 playing 时为受控模式（父组件真实播放控制动画，
// 点击仅 emit play）；未传入时保留点击模拟播放 1.6s 的旧行为
import { computed, onBeforeUnmount, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    duration?: string
    /** 波形尺寸：md=7 根(16px高)，sm=5 根(12px高) */
    size?: 'md' | 'sm'
    /** 紧凑变体（双语音条并列用） */
    compact?: boolean
    /** 白色配色（用于"我"的蓝色气泡内） */
    white?: boolean
    /** 是否可点击播放 */
    playable?: boolean
    /** 受控播放态（提供时由父组件控制） */
    playing?: boolean
  }>(),
  { duration: '', size: 'md', compact: false, white: false, playable: true, playing: undefined },
)

const emit = defineEmits<{ play: [] }>()

const innerPlaying = ref(false)
const isPlaying = computed(() => props.playing ?? innerPlaying.value)
let timer: ReturnType<typeof setTimeout> | null = null

function play() {
  if (!props.playable) return
  emit('play')
  if (props.playing !== undefined) return // 受控模式：动画由父组件控制
  innerPlaying.value = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    innerPlaying.value = false
    timer = null
  }, 1600)
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

const barCount = () => (props.size === 'sm' ? 5 : 7)
</script>

<template>
  <div
    class="voice-bar"
    :class="[{ playing: isPlaying, 'voice-bar--compact': compact, 'voice-bar--white': white }]"
    @click="play"
  >
    <span class="spk">
      <svg :width="compact ? 12 : 14" :height="compact ? 12 : 14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M11 5 6 9H2v6h4l5 4V5Z" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      </svg>
    </span>
    <span class="vb-wave" :class="size === 'sm' ? 'vb-wave--sm' : 'vb-wave--md'">
      <i v-for="n in barCount()" :key="n"></i>
    </span>
    <span v-if="duration" class="vb-dur">{{ duration }}</span>
  </div>
</template>

<style scoped>
.voice-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
  border-radius: var(--radius-sm);
  color: var(--accent-color);
}
.voice-bar--compact {
  min-width: 54px;
  flex: none;
  gap: 6px;
}
.spk {
  display: inline-flex;
  transform-origin: center;
}
.vb-wave {
  display: flex;
  align-items: center;
  gap: 2.5px;
  flex: 1;
}
.vb-wave--md {
  height: 16px;
}
.vb-wave--sm {
  height: 12px;
  flex: none;
}
.vb-wave i {
  width: 3px;
  background: currentColor;
  border-radius: 2px;
  height: 8px;
}
.vb-wave i:nth-child(1) { height: 6px; }
.vb-wave i:nth-child(2) { height: 11px; }
.vb-wave i:nth-child(3) { height: 16px; }
.vb-wave i:nth-child(4) { height: 9px; }
.vb-wave i:nth-child(5) { height: 14px; }
.vb-wave i:nth-child(6) { height: 7px; }
.vb-wave i:nth-child(7) { height: 12px; }
.vb-wave--sm i:nth-child(3) { height: 12px; }
.voice-bar.playing .vb-wave i {
  animation: wave 0.4s ease-in-out infinite;
}
.voice-bar.playing .spk {
  animation: spkRing 0.55s ease-in-out infinite;
}
.vb-dur {
  font-size: 11px;
  color: var(--color-muted);
  flex: none;
}
/* 白色配色（蓝色气泡内） */
.voice-bar--white {
  color: rgba(255, 255, 255, 0.92);
}
.voice-bar--white .vb-dur {
  color: #fff;
}
</style>
