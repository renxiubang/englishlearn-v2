<script setup lang="ts">
// 聊天气泡：语音条 + 展开区（英文原文/慢速/AI读/翻译/收藏），them=对方白色气泡，me=我方蓝色气泡；
// 真实播放后端 /audio/*.wav：them 点击播 url（tts），me 点击播 userAudio，"AI读"播 ttsAudio，慢速 = 0.7x
import { computed, onBeforeUnmount, ref } from 'vue'
import VoiceBar from '@/components/VoiceBar.vue'
import { toast } from '@/composables/useToast'
import { playUrl, stopUrl } from '@/composables/usePcmPlayer'
import type { AudioRef } from '@/types'

const props = withDefaults(
  defineProps<{
    side: 'them' | 'me'
    en: string
    zh?: string
    /** me 语音气泡：原始逐字转录（原译，en 为纠译） */
    raw?: string
    /** 语音时长文案（服务端返回值格式化） */
    duration?: string
    /** them 气泡的 tts 音频地址（点击/慢速播放） */
    url?: string
    /** me 气泡：用户原声 */
    userAudio?: AudioRef
    /** me 气泡：AI 范读音频 */
    ttsAudio?: AudioRef
    /** 评分（me 气泡显示分数 tag，0 不显示） */
    score?: number
    /** 纯文本气泡（无语音条，直接显示 en） */
    textOnly?: boolean
    /** 紧凑语音条变体（辅助跟读产生的 me 气泡） */
    compact?: boolean
    /** them+真人：展开翻译时显示熟练度权重降低警告 */
    warnOnTranslate?: boolean
    /** 初始收藏态 */
    favorited?: boolean
  }>(),
  {
    zh: '',
    raw: '',
    duration: '',
    url: '',
    userAudio: undefined,
    ttsAudio: undefined,
    score: 0,
    textOnly: false,
    compact: false,
    warnOnTranslate: false,
    favorited: false,
  },
)

const emit = defineEmits<{
  /** 收藏状态切换 */
  favorite: [payload: { en: string; zh: string; faved: boolean }]
  /** 请求按需翻译（zh 为空时点击"翻译"触发，接口 19） */
  translate: []
}>()

const expanded = ref(false)
const zhShown = ref(false)
const faved = ref(props.favorited)
const barPlaying = ref(false)
const aiReading = ref(false)

/** 语音条点击播放的音频：them=tts url，me=用户原声 */
const mainUrl = computed(() => (props.side === 'them' ? props.url : props.userAudio?.url) || '')

function toggleFav() {
  faved.value = !faved.value
  toast(faved.value ? '已加入收藏' : '已取消收藏')
  emit('favorite', { en: props.en, zh: props.zh, faved: faved.value })
}

/** 翻译按钮：zh 未生成时向上游请求按需翻译（展示"翻译中…"占位），已有则切换显隐 */
function onTranslateClick() {
  if (!props.zh) {
    emit('translate')
    zhShown.value = true
    return
  }
  zhShown.value = !zhShown.value
}

function playMain() {
  if (barPlaying.value) {
    stopUrl()
    return
  }
  if (!mainUrl.value) return
  playUrl(mainUrl.value, 1, () => { barPlaying.value = false })
  barPlaying.value = true
}

function playSlow() {
  if (!props.url) return
  playUrl(props.url, 0.7, () => { barPlaying.value = false })
  barPlaying.value = true
}

function aiRead() {
  const u = props.ttsAudio?.url
  if (!u) return
  playUrl(u, 1, () => { aiReading.value = false })
  aiReading.value = true
}

onBeforeUnmount(() => {
  if (barPlaying.value || aiReading.value) stopUrl()
})
</script>

<template>
  <!-- 纯文本气泡 -->
  <div v-if="textOnly" class="bubble" :class="side">{{ en }}</div>

  <!-- 语音气泡 -->
  <div v-else class="bubble" :class="[side, compact ? 'bubble--xl' : 'bubble--lg']">
    <div class="flex items-center gap-2" :class="{ 'flex-wrap': compact }">
      <VoiceBar :duration="duration" :compact="compact" :size="compact ? 'sm' : 'md'" :white="side === 'me'" :playing="barPlaying" @play="playMain" />
      <span v-if="side === 'me' && score > 0" class="tag tag--on-primary">{{ score }}</span>
      <button class="tri-btn flex-none" :class="{ open: expanded }" @click="expanded = !expanded">▸</button>
    </div>
    <div v-if="expanded" class="mt-2">
      <!-- me 语音消息带原译时分两行展示原译/AI译 -->
      <div v-if="side === 'me' && raw" class="text-[13px] space-y-1">
        <div class="opacity-80">原译：{{ raw }}</div>
        <div>AI译：{{ en }}</div>
      </div>
      <div v-else class="text-[13px]">{{ en }}</div>
      <!-- them：慢速 / 翻译 / 收藏 -->
      <div v-if="side === 'them'" class="flex flex-wrap gap-2 mt-2">
        <button class="help-btn" @click="playSlow">慢速</button>
        <button class="help-btn" @click="onTranslateClick">🌐 翻译</button>
        <button class="fav-btn ml-auto" :class="{ faved }" @click="toggleFav">{{ faved ? '★' : '☆' }}</button>
      </div>
      <!-- me：AI读 / 翻译 / 收藏 -->
      <div v-else class="flex flex-wrap gap-2 mt-2 justify-between items-center">
        <div class="flex flex-wrap gap-2">
          <button class="help-btn" @click="aiRead"><span class="spk-ic" :class="{ ringing: aiReading }">AI读</span></button>
          <button class="help-btn" @click="onTranslateClick">🌐 翻译</button>
        </div>
        <button class="fav-btn" :class="{ faved }" @click="toggleFav">{{ faved ? '★' : '☆' }}</button>
      </div>
      <div v-if="zhShown" class="mt-2">
        <template v-if="zh">
          <div v-if="side === 'them'" class="text-[13px] text-accent">{{ zh }}</div>
          <div v-else class="text-[12px] opacity-90">{{ zh }}</div>
          <div v-if="side === 'them' && warnOnTranslate" class="text-[10px] mt-1 text-accent">
            ⚠️ 本句因您点击了“翻译/提示”按钮，熟练度权重降低
          </div>
        </template>
        <!-- 按需翻译进行中（接口 19）占位 -->
        <div v-else class="text-[12px] opacity-70">翻译中…</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.spk-ic {
  display: inline-block;
  transform-origin: center;
}
.spk-ic.ringing {
  animation: spkRing 0.55s ease-in-out infinite;
}
</style>
