<script setup lang="ts">
// 辅助卡片（v5）：chat 模式传入中文录音（audio），走接口 16 流式获取中/英翻译与合成语音
// （audio_chunk 边收边播、audio_end 后可点击重播 wav）；跟读记录真实录音，"读完啦"携带
// 最后一段录音与英文文本，交给父组件走接口 17 校验。picture 模式保留原 zh/en 提示行为。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { assistApi } from '@/api'
import { toast } from '@/composables/useToast'
import { createPcmPlayer, playBlob, playUrl, stopUrl } from '@/composables/usePcmPlayer'
import type { Recording } from '@/composables/useRecorder'

const props = withDefaults(
  defineProps<{
    /** 中文提示语（picture 模式传入；chat 模式由接口 16 流式返回） */
    zh?: string
    /** 英文提示句（picture 模式传入；chat 模式由接口 16 流式返回） */
    en?: string
    /** 触发辅助的中文录音（chat 模式），传入后自动调接口 16 翻译 */
    audio?: Blob
    /** chat：带跟读语音区；picture：仅提示与点读 */
    mode?: 'chat' | 'picture'
    favorited?: boolean
  }>(),
  { zh: '', en: '', audio: undefined, mode: 'chat', favorited: false },
)

const emit = defineEmits<{
  close: []
  /** 点击"读完啦"：携带跟读次数、最后一段录音与英文原文（供接口 17 校验） */
  finish: [payload: { count: number; rec: Recording | null; en: string }]
  favorite: [payload: { en: string; zh: string; faved: boolean }]
  /** 跟读语音段数变化（父组件据此切换按钮文案） */
  voiceChange: [count: number]
}>()

// ---- 中/英文本（chat 模式由接口 16 填充） ----
const zhText = ref(props.zh)
const enText = ref(props.en)
const words = computed(() => (enText.value ? enText.value.split(' ') : []))

// ---- 合成语音条（chat：SSE 分片边收边播 + wav 重播；picture：3s 模拟） ----
const playing = ref(false)
const ttsUrl = ref('')
const ttsDuration = ref(0)
const pcm = createPcmPlayer()
let playTimer: ReturnType<typeof setTimeout> | null = null
let autoTimer: ReturnType<typeof setTimeout> | null = null

const ttsDurText = computed(() => {
  const sec = Math.max(1, Math.round(ttsDuration.value || 3))
  return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0')
})

function togglePlay() {
  if (playing.value) {
    // 停止：流式分片与整段重播一并停掉
    playing.value = false
    pcm.stop()
    stopUrl()
    if (playTimer) { clearTimeout(playTimer); playTimer = null }
    return
  }
  if (ttsUrl.value) {
    // 接口 16 audio_end 已给出完整 wav：整段重播
    playing.value = true
    playUrl(ttsUrl.value, 1, () => { playing.value = false })
    return
  }
  if (props.audio) return // chat 模式音频尚未就绪：等 SSE 分片自动播放
  // picture 模式：保留 3s 模拟播放
  playing.value = true
  playTimer = setTimeout(() => {
    playing.value = false
    playTimer = null
  }, 3000)
}

// ---- 接口 16：中文录音 → 流式翻译 + 合成语音 ----
async function startTranslate(blob: Blob) {
  try {
    await assistApi.translate(blob, (event, data) => {
      if (event === 'zh') {
        zhText.value = String(data.zh ?? '')
      } else if (event === 'en') {
        enText.value = String(data.en ?? '')
      } else if (event === 'audio_chunk') {
        playing.value = true
        pcm.feed(String(data.base64 ?? ''))
      } else if (event === 'audio_end') {
        ttsUrl.value = String(data.url ?? '')
        ttsDuration.value = Number(data.duration ?? 0)
        playing.value = false
      }
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '辅助翻译失败')
  }
}

onMounted(() => {
  if (props.audio) {
    void startTranslate(props.audio)
    return
  }
  // picture 模式：等入场动画结束后自动播放
  autoTimer = setTimeout(() => {
    if (!playing.value) togglePlay()
  }, 300)
})

onBeforeUnmount(() => {
  if (playTimer) clearTimeout(playTimer)
  if (autoTimer) clearTimeout(autoTimer)
  if (wordTimer) clearTimeout(wordTimer)
  pcm.dispose()
  if (playing.value) stopUrl()
})

// ---- 英文文本展开 ----
const enShown = ref(false)

// ---- 逐词点读 ----
const activeWord = ref(-1)
let wordTimer: ReturnType<typeof setTimeout> | null = null
function playWord(i: number) {
  activeWord.value = i
  toast('🔊 ' + words.value[i])
  if (wordTimer) clearTimeout(wordTimer)
  wordTimer = setTimeout(() => {
    activeWord.value = -1
    wordTimer = null
  }, 1200)
}

// ---- 收藏 ----
const faved = ref(props.favorited)
function toggleStar() {
  faved.value = !faved.value
  toast(faved.value ? '已收藏此句' : '已取消收藏')
  emit('favorite', { en: enText.value, zh: zhText.value, faved: faved.value })
}

// ---- 跟读语音（chat 模式）：记录真实录音段 ----
const recordings = ref<Recording[]>([])
const voicePlaying = ref(false)
const voiceCount = computed(() => recordings.value.length)

const voiceDur = computed(() => {
  const sec = Math.round(recordings.value.reduce((s, r) => s + r.seconds, 0))
  const mm = Math.floor(sec / 60)
  const ss = sec % 60
  return mm + ':' + (ss < 10 ? '0' + ss : ss)
})

function addVoice(rec: Recording) {
  recordings.value.push(rec)
  emit('voiceChange', recordings.value.length)
}

function removeLastVoice() {
  if (!recordings.value.length) return
  recordings.value.pop()
  emit('voiceChange', recordings.value.length)
}

function resetVoices() {
  recordings.value = []
  emit('voiceChange', 0)
}

function playVoices() {
  const last = recordings.value[recordings.value.length - 1]
  if (!last || voicePlaying.value) return
  voicePlaying.value = true
  playBlob(last.blob, () => {
    voicePlaying.value = false
  })
}

function onFinish() {
  emit('finish', {
    count: recordings.value.length,
    rec: recordings.value[recordings.value.length - 1] ?? null,
    en: enText.value,
  })
}

defineExpose({ addVoice, resetVoices, voiceCount })
</script>

<template>
  <div class="assist-mini" :class="{ playing }">
    <button class="assist-close" @click="emit('close')">✕</button>
    <div class="assist-zh">{{ zhText || (audio ? '正在翻译…' : '') }}</div>

    <!-- 合成语音条 + 查看英文文本 -->
    <div class="assist-tts-row">
      <div class="assist-tts-bar" @click="togglePlay">
        <span class="spk">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M11 5 6 9H2v6h4l5 4V5Z" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
        </span>
        <span class="tts-wave"><i v-for="n in 7" :key="n"></i></span>
        <span class="tts-dur">{{ ttsDurText }}</span>
      </div>
      <button class="assist-show-en" @click="enShown = !enShown">
        {{ enShown ? '收起英文文本' : '点击查看英文文本' }}
      </button>
    </div>

    <!-- 英文文本（默认隐藏）：可点读单词 + 句末收藏星 -->
    <div v-if="enShown && words.length" class="assist-en">
      <template v-for="(w, i) in words" :key="i">
        <span class="assist-word" :class="{ active: activeWord === i }" @click="playWord(i)">{{ w }}</span>{{ ' ' }}
      </template>
      <button class="assist-star" :class="{ active: faved }" title="收藏此句" @click="toggleStar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
        </svg>
      </button>
    </div>

    <!-- 跟读语音合并条 + 读完啦（chat 模式，跟读后出现） -->
    <div v-if="mode === 'chat' && voiceCount > 0" class="assist-voice-row">
      <div class="assist-voices">
        <div class="voice-item" :class="{ playing: voicePlaying }">
          <span class="voice-play" @click="playVoices">
            <span class="spk">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M11 5 6 9H2v6h4l5 4V5Z" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              </svg>
            </span>
            <span class="voice-wave"><i v-for="n in 5" :key="n"></i></span>
            <span class="text-[10px] opacity-90">{{ voiceDur }}</span>
          </span>
          <button class="voice-del" title="删除最后一段" @click.stop="removeLastVoice">✕</button>
          <span v-if="voiceCount > 1" class="voice-badge">{{ voiceCount }}</span>
          <span v-if="voiceCount > 1" class="voice-del-hint">(每次删除最后一段)</span>
        </div>
      </div>
      <button class="assist-finish" @click="onFinish">读完啦</button>
    </div>
  </div>
</template>

<style scoped>
.assist-mini {
  position: relative;
  background: var(--color-surface);
  padding: 16px 16px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  animation: assistUp 0.25s ease-out;
  overflow: hidden;
}
@keyframes assistUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.assist-zh {
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.4;
  margin-bottom: var(--spacing-sm);
  padding-right: var(--spacing-xl);
}
.assist-en {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: #1a2332;
  line-height: 1.7;
  position: relative;
  margin-top: 10px;
}
.assist-mini.playing .assist-en {
  color: var(--primary-color);
}
/* 合成语音条行 */
.assist-tts-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: var(--spacing-xl);
}
.assist-tts-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex: 1;
  min-width: 0;
  background: var(--tint-blue);
  color: var(--primary-color);
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s;
}
.assist-tts-bar:active {
  background: #d9e8fb;
}
.tts-wave {
  display: flex;
  align-items: center;
  gap: 2.5px;
  flex: 1;
}
.tts-wave i {
  width: 3px;
  background: var(--primary-color);
  border-radius: 2px;
  height: 8px;
}
.tts-wave i:nth-child(1) { height: 6px; }
.tts-wave i:nth-child(2) { height: 11px; }
.tts-wave i:nth-child(3) { height: 16px; }
.tts-wave i:nth-child(4) { height: 9px; }
.tts-wave i:nth-child(5) { height: 14px; }
.tts-wave i:nth-child(6) { height: 7px; }
.tts-wave i:nth-child(7) { height: 12px; }
.assist-mini.playing .tts-wave i {
  animation: wave 0.4s ease-in-out infinite;
}
.assist-mini.playing .assist-tts-bar .spk {
  animation: spkRing 0.55s ease-in-out infinite;
}
.tts-dur {
  font-size: var(--font-size-xs);
  color: var(--primary-color);
  flex: none;
}
.spk {
  display: inline-flex;
  transform-origin: center;
}
/* 查看英文文本按钮 */
.assist-show-en {
  flex: none;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--primary-color);
  background: var(--color-bg-tertiary);
  border: none;
  border-radius: var(--radius-full);
  padding: 6px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.12s;
}
.assist-show-en:active {
  background: #e3e9f2;
}
/* 可点击单词 */
.assist-word {
  cursor: pointer;
  border-radius: 4px;
  padding: 1px;
  margin: 0 1px;
  transition: background 0.12s;
}
.assist-word:hover {
  background: rgba(74, 144, 226, 0.1);
}
.assist-word.active {
  background: var(--tint-blue);
  color: var(--primary-dark);
}
/* 收藏五角星 */
.assist-star {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: var(--spacing-xs);
  vertical-align: middle;
  background: transparent;
  border: none;
  padding: 0;
  color: #c8cdd6;
  cursor: pointer;
  transition: color 0.15s, transform 0.12s;
  position: relative;
}
.assist-star:hover {
  color: var(--color-star);
}
.assist-star.active {
  color: var(--color-star);
}
.assist-star.active svg {
  fill: currentColor;
  stroke: none;
}
.assist-star:active {
  transform: scale(1.25);
}
/* 右上角关闭 */
.assist-close {
  position: absolute;
  right: 10px;
  top: 10px;
  z-index: 2;
  font-size: 15px;
  color: #c0c8d4;
  width: 26px;
  height: 26px;
  background: transparent;
  border: none;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.15s;
}
.assist-close:active {
  background: var(--color-bg-tertiary);
  color: #666;
}
/* 跟读语音区 */
.assist-voice-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.assist-voices {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}
.voice-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--spacing-xs) 6px;
  border-radius: 8px;
  color: var(--accent-color);
}
.voice-play {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.voice-wave {
  display: flex;
  align-items: center;
  gap: 2.5px;
  height: 12px;
}
.voice-wave i {
  width: 3px;
  background: var(--accent-color);
  border-radius: 2px;
  height: 8px;
}
.voice-wave i:nth-child(1) { height: 6px; }
.voice-wave i:nth-child(2) { height: 11px; }
.voice-wave i:nth-child(3) { height: 12px; }
.voice-wave i:nth-child(4) { height: 9px; }
.voice-wave i:nth-child(5) { height: 7px; }
.voice-item.playing .voice-wave i {
  animation: wave 0.4s ease-in-out infinite;
}
.voice-item.playing .spk {
  animation: spkRing 0.55s ease-in-out infinite;
}
.voice-del {
  font-size: var(--font-size-xs);
  color: #c0c8d4;
  cursor: pointer;
  margin-left: var(--spacing-xs);
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  padding: 0;
  border-radius: 50%;
  transition: all 0.15s;
  line-height: 1;
  vertical-align: middle;
  position: relative;
}
.voice-del:hover {
  background: #fde8e8;
  color: #e05555;
}
.voice-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin-left: 6px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  color: #fff;
  background: var(--primary-color);
  border-radius: var(--radius-full);
}
.voice-del-hint {
  font-size: 10px;
  color: #b0b8c4;
  margin-left: var(--spacing-xs);
  white-space: nowrap;
}
.assist-finish {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: #fff;
  background: var(--accent-color);
  border: none;
  padding: 6px 16px;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: opacity 0.15s;
}
.assist-finish:active {
  opacity: 0.85;
}
</style>
