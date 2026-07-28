<script setup lang="ts">
// 看图讲故事：故事货架（分类/完成徽标/圆点分页）+ 主图 + 英文转写卡（按住讲述逐词转写、
// AI读/我读/删句、讲完啦评分）+ 中文触发辅助卡片跟读；离开页面未评分时二次确认
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import PressTalkButton from '@/components/PressTalkButton.vue'
import AssistCard from '@/components/AssistCard.vue'
import { assistApi, picStoryApi, speechApi } from '@/api'
import type { AssistHint, PicStory, PicStoryProgress } from '@/types'
import { toast } from '@/composables/useToast'
import { useFavoritesStore } from '@/stores/favorites'

const favStore = useFavoritesStore()

// ---------- 数据加载 ----------
const stories = ref<PicStory[]>([])
const cats = ref<string[]>([])
const progress = ref<PicStoryProgress>({})
const curCat = ref('全部')
const curSeed = ref('')

onMounted(async () => {
  favStore.ensureLoaded()
  try {
    const [list, catList, prog] = await Promise.all([
      picStoryApi.list(),
      picStoryApi.getCategories(),
      picStoryApi.getProgress(),
    ])
    stories.value = list
    cats.value = catList
    progress.value = prog
    if (list.length) curSeed.value = list[0].seed
  } catch {
    toast('故事列表加载失败')
  }
})

const curStory = computed(() => stories.value.find(s => s.seed === curSeed.value))

// 货架：按分类过滤，未完成的排前面（与原型一致）
const shelfStories = computed(() =>
  stories.value
    .filter(s => curCat.value === '全部' || s.cat === curCat.value)
    .slice()
    .sort((a, b) => (progress.value[a.seed] ? 1 : 0) - (progress.value[b.seed] ? 1 : 0)),
)

function selectCat(cat: string) {
  if (cat === curCat.value) return
  curCat.value = cat
}

function selectStory(seed: string) {
  if (sentences.value.length && !storyFinished.value) {
    openConfirm('还没有点击"讲完啦"，是否放弃？', () => applyStory(seed))
    return
  }
  applyStory(seed)
}
function applyStory(seed: string) {
  curSeed.value = seed
  restartSession()
}

// ---------- 货架圆点分页 ----------
const shelfEl = ref<HTMLElement | null>(null)
const activeDot = ref(0)
const dotCount = computed(() => Math.max(1, Math.ceil(shelfStories.value.length / 5)))
function onShelfScroll() {
  const el = shelfEl.value
  if (!el || dotCount.value <= 1) return
  const max = el.scrollWidth - el.clientWidth
  const ratio = max > 0 ? el.scrollLeft / max : 0
  activeDot.value = Math.min(dotCount.value - 1, Math.round(ratio * (dotCount.value - 1)))
}

// ---------- 英文转写 ----------
interface Sent {
  id: number
  text: string
}
let sentSeq = 0
const sentences = ref<Sent[]>([])
const selId = ref(-1)

// 逐词打字模拟
const typingText = ref('')
const typingActive = ref(false)
let typingWords: string[] = []
let typingIdx = 0
let typingTimer: ReturnType<typeof setInterval> | null = null

const bodyEl = ref<HTMLElement | null>(null)
const cardEl = ref<HTMLElement | null>(null)
function followTranscript() {
  nextTick(() => {
    const body = bodyEl.value
    const card = cardEl.value
    if (!body || !card) return
    const overflow = card.getBoundingClientRect().bottom - body.getBoundingClientRect().bottom
    if (overflow > 0) body.scrollTo({ top: body.scrollTop + overflow + 12, behavior: 'smooth' })
  })
}

function startTyping() {
  const st = curStory.value
  if (!st) return
  const sent = st.sentences[sentences.value.length % st.sentences.length]
  typingWords = sent.split(' ')
  typingIdx = 0
  typingText.value = ''
  typingActive.value = true
  if (typingTimer) clearInterval(typingTimer)
  typingTimer = setInterval(() => {
    if (typingIdx >= typingWords.length) {
      if (typingTimer) clearInterval(typingTimer)
      return
    }
    typingText.value += (typingIdx ? ' ' : '') + typingWords[typingIdx++]
    followTranscript()
  }, 150)
}
function finalizeTyping(cancelled: boolean) {
  if (typingTimer) {
    clearInterval(typingTimer)
    typingTimer = null
  }
  if (!typingActive.value) return
  typingActive.value = false
  if (!cancelled) {
    while (typingIdx < typingWords.length) typingText.value += (typingIdx ? ' ' : '') + typingWords[typingIdx++]
    sentences.value.push({ id: ++sentSeq, text: typingText.value })
  }
  typingText.value = ''
  typingWords = []
  typingIdx = 0
}

function toggleSentSel(id: number) {
  if (storyFinished.value) return
  selId.value = selId.value === id ? -1 : id
}
function deleteSelectedSent() {
  if (selId.value < 0) return
  sentences.value = sentences.value.filter(s => s.id !== selId.value)
  selId.value = -1
  toast('已删除该句')
}

// ---------- 按住讲述 ----------
let pressCount = 0
const talkLabel = computed(() => (assistHint.value ? '按住 跟读' : '按住 讲述'))

function onTalkStart() {
  if (assistHint.value) return
  startTyping()
}
function onTalkSend() {
  if (assistHint.value) {
    onAssistMimicSend()
    return
  }
  pressCount++
  if (pressCount % 2 === 1) {
    // 奇数次按住模拟识别到中文 → 进入辅助（与聊天页节奏一致）
    finalizeTyping(true)
    toast('识别到中文，正在为你进入辅助…')
    setTimeout(openAssist, 500)
  } else {
    finalizeTyping(false)
  }
}
function onTalkCancel() {
  if (assistHint.value) {
    toast('已取消发送')
    return
  }
  pressCount++
  finalizeTyping(true)
  toast('已取消本次讲述')
}

// ---------- 辅助卡片（picture 模式：跟读一次即上屏英文句） ----------
const assistHint = ref<AssistHint | null>(null)
async function openAssist() {
  try {
    assistHint.value = await assistApi.getHint('picture')
  } catch {
    toast('辅助内容加载失败')
  }
}
function closeAssist() {
  assistHint.value = null
}
function onAssistMimicSend() {
  const hint = assistHint.value
  if (!hint) return
  closeAssist()
  setTimeout(() => {
    sentences.value.push({ id: ++sentSeq, text: hint.en })
    toast('已通过"辅助"添加英文句子')
    followTranscript()
  }, 300)
}
function onAssistFavorite(payload: { en: string; zh: string; faved: boolean }) {
  favStore.toggle(payload.en, payload.zh, payload.faved)
}

// ---------- AI读 / 我读 ----------
const readMode = ref<'' | 'ai' | 'my'>('')
const readPaused = ref(false)
const speakingId = ref(-1)
let readTargets: Sent[] = []
let readIdx = 0
let readTimer: ReturnType<typeof setTimeout> | null = null

function toggleRead(mode: 'ai' | 'my') {
  if (readMode.value && readMode.value !== mode) stopRead()
  if (!readMode.value) {
    const sel = sentences.value.find(s => s.id === selId.value)
    readTargets = sel ? [sel] : sentences.value.slice()
    if (!readTargets.length) {
      toast('先按住讲述')
      return
    }
    readMode.value = mode
    readIdx = 0
    toast(mode === 'ai' ? 'AI 正在合成语音…' : '播放我的录音')
    readTimer = setTimeout(playStep, mode === 'ai' ? 750 : 100)
  } else if (!readPaused.value) {
    if (readTimer) clearTimeout(readTimer)
    readPaused.value = true
    toast('已暂停')
  } else {
    readPaused.value = false
    playStep()
  }
}
function playStep() {
  if (readIdx >= readTargets.length) {
    stopRead()
    return
  }
  const cur = readTargets[readIdx]
  speakingId.value = cur.id
  const dur = Math.max(750, cur.text.trim().split(/\s+/).length * 230)
  readTimer = setTimeout(() => {
    readIdx++
    playStep()
  }, dur)
}
function stopRead() {
  if (readTimer) clearTimeout(readTimer)
  readTimer = null
  speakingId.value = -1
  readMode.value = ''
  readPaused.value = false
  readTargets = []
  readIdx = 0
}

// ---------- 讲完啦（评分） ----------
const storyFinished = ref(false)
const scoring = ref(false)
const storyScore = ref<number | null>(null)
const scoreModalOpen = ref(false)

const subScores = computed(() => {
  const s = storyScore.value ?? 0
  return [
    { label: '发音准确度', value: Math.min(100, s + 2) },
    { label: '流利度', value: Math.max(40, s - 4) },
    { label: '完整度', value: Math.min(100, s + 1) },
  ]
})
const scoreComment = computed(() => {
  const s = storyScore.value ?? 0
  if (s >= 90) return '优秀 · 继续保持！'
  if (s >= 75) return '很棒 · 再接再厉！'
  return '不错 · 多练几次会更好'
})

async function finishStory() {
  if (!sentences.value.length) {
    toast('还没有讲述内容')
    return
  }
  if (storyFinished.value || scoring.value) return
  scoring.value = true
  stopRead()
  try {
    await new Promise(r => setTimeout(r, 900))
    const { score } = await speechApi.score('picture')
    storyScore.value = score
    storyFinished.value = true
    selId.value = -1
    progress.value = await picStoryApi.saveProgress(curSeed.value, score)
    scoreModalOpen.value = true
  } catch {
    toast('评分失败，请重试')
  } finally {
    scoring.value = false
  }
}

function redoStory() {
  restartSession()
  toast('已清空转写 · 再来一遍')
}
function restartSession() {
  storyFinished.value = false
  storyScore.value = null
  scoreModalOpen.value = false
  pressCount = 0
  sentences.value = []
  selId.value = -1
  closeAssist()
  stopRead()
  finalizeTyping(true)
}

// ---------- 确认弹窗 / 离开拦截 ----------
const confirmMsg = ref('')
let confirmOk: (() => void) | null = null
let confirmCancel: (() => void) | null = null
function openConfirm(msg: string, onOk: () => void, onCancel?: () => void) {
  confirmMsg.value = msg
  confirmOk = onOk
  confirmCancel = onCancel ?? null
}
function doConfirmOk() {
  const fn = confirmOk
  confirmMsg.value = ''
  confirmOk = confirmCancel = null
  fn?.()
}
function doConfirmCancel() {
  const fn = confirmCancel
  confirmMsg.value = ''
  confirmOk = confirmCancel = null
  fn?.()
}

onBeforeRouteLeave((_to, _from, next) => {
  if (sentences.value.length && !storyFinished.value) {
    openConfirm(
      '还没有点击"讲完啦"，是否放弃保存及评分？',
      () => {
        restartSession()
        next()
      },
      () => next(false),
    )
    return
  }
  next()
})

onBeforeUnmount(() => {
  if (typingTimer) clearInterval(typingTimer)
  if (readTimer) clearTimeout(readTimer)
})
</script>

<template>
  <section class="screen">
    <NavBar title="看图讲故事" back back-to="/" />
    <div ref="bodyEl" class="screen-body p-[18px]">
      <!-- 故事货架 -->
      <div class="flex justify-between items-center">
        <div class="text-[13px] font-bold">选一个故事</div>
        <div class="text-[11px] muted">共 {{ shelfStories.length }} 篇</div>
      </div>
      <div class="flex gap-1.5 overflow-x-auto scrollbar-none mt-2">
        <button
          v-for="c in cats"
          :key="c"
          class="cat-chip"
          :class="{ sel: c === curCat }"
          @click="selectCat(c)"
        >{{ c }}</button>
      </div>
      <div class="shelf-wrap">
        <div ref="shelfEl" class="flex gap-3 overflow-x-auto scrollbar-none mt-2 py-1.5 px-0.5" @scroll.passive="onShelfScroll">
          <button
            v-for="st in shelfStories"
            :key="st.seed"
            class="story-card"
            :class="{ sel: st.seed === curSeed }"
            @click="selectStory(st.seed)"
          >
            <span v-if="progress[st.seed]" class="story-done-badge">⭐{{ progress[st.seed] }}</span>
            <div class="story-thumb" :style="{ backgroundImage: `url('https://picsum.photos/seed/${st.seed}/200')` }">
              <div class="story-name">{{ st.title }}</div>
            </div>
          </button>
        </div>
      </div>
      <div v-if="dotCount > 1" class="shelf-dots">
        <i v-for="i in dotCount" :key="i" :class="{ on: i - 1 === activeDot }"></i>
      </div>

      <!-- 主图 -->
      <div
        class="mt-3 aspect-[4/3] rounded-2xl bg-cover relative overflow-hidden"
        :style="curStory ? { backgroundImage: `url('https://picsum.photos/seed/${curStory.seed}/600')` } : undefined"
      >
        <div class="img-caption-chip absolute left-3 bottom-3 px-2.5 py-1 rounded-full text-white text-[12px] font-bold">
          {{ curStory?.title ?? '…' }}
        </div>
      </div>

      <!-- 英文转写卡 -->
      <div ref="cardEl" class="card p-4 mt-3 relative">
        <div class="flex justify-between items-center text-[12px]">
          <span class="muted flex items-center gap-1.5">
            <span v-if="typingActive" class="w-1.5 h-1.5 rounded-full rec-dot"></span>英文转写
          </span>
          <span class="text-[11px] muted">已转写 {{ sentences.length }} 句</span>
        </div>
        <div class="text-[14px] mt-2 min-h-[64px] leading-[1.9]">
          <span v-if="!sentences.length && !typingActive" class="muted">按住底部按钮，开始讲故事</span>
          <template v-else>
            <span
              v-for="s in sentences"
              :key="s.id"
              class="ts-sent"
              :class="{
                sel: s.id === selId,
                'speaking-ai': s.id === speakingId && readMode === 'ai',
                'speaking-my': s.id === speakingId && readMode === 'my',
              }"
              @click="toggleSentSel(s.id)"
            >{{ s.text }}</span>
            <span v-if="typingActive" class="ts-sent typing">{{ typingText }}</span>
          </template>
        </div>
        <div class="transcript-actions flex items-center gap-2 mt-3 pt-3">
          <button
            class="read-btn ai"
            :class="{ busy: readMode === 'ai' && !readPaused, paused: readMode === 'ai' && readPaused }"
            :disabled="!sentences.length"
            @click="toggleRead('ai')"
          >AI读</button>
          <button
            class="read-btn my"
            :class="{ busy: readMode === 'my' && !readPaused, paused: readMode === 'my' && readPaused }"
            :disabled="!sentences.length"
            @click="toggleRead('my')"
          >我读</button>
          <button class="read-btn del" :disabled="!sentences.length || selId < 0 || storyFinished" @click="deleteSelectedSent">删句</button>
          <div class="ml-auto flex items-center gap-2">
            <div v-if="storyScore !== null" class="text-[18px] font-extrabold text-primary">{{ storyScore }}分</div>
            <button
              class="finish-btn flex-none"
              :class="{ done: storyFinished }"
              :disabled="!sentences.length || scoring || storyFinished"
              @click="finishStory"
            >{{ scoring ? '评分中…' : '讲完啦' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 辅助卡片（中文触发） -->
    <AssistCard
      v-if="assistHint"
      mode="picture"
      :zh="assistHint.zh"
      :en="assistHint.en"
      :favorited="favStore.has(assistHint.en)"
      @close="closeAssist"
      @favorite="onAssistFavorite"
    />

    <footer class="screen-footer screen-footer--tall pt-4">
      <button
        v-if="storyFinished"
        class="redo-btn card w-full py-3.5 font-bold text-accent flex items-center justify-center"
        @click="redoStory"
      >再来一次</button>
      <PressTalkButton
        v-else
        class="story-talk-btn card w-full py-3.5 font-bold text-primary flex items-center justify-center relative"
        :label="talkLabel"
        :cancel-toast="false"
        @start="onTalkStart"
        @send="onTalkSend"
        @cancel="onTalkCancel"
      >
        <template #default="{ pressing }">
          <span v-if="pressing" class="press-wave absolute left-4 flex items-center gap-[3px] h-[22px]"><i></i><i></i><i></i><i></i><i></i></span>
          <span class="label">{{ talkLabel }}</span>
        </template>
      </PressTalkButton>
    </footer>

    <!-- 发音诊所评分弹窗 -->
    <div v-if="scoreModalOpen" class="overlay overlay--fade-in center" @click.self="scoreModalOpen = false">
      <div class="modal">
        <div class="text-center">
          <div class="text-[13px] muted">发音诊所 · 本次评分</div>
          <div class="text-[40px] font-extrabold text-primary mt-1">{{ storyScore }}</div>
          <div class="text-[12px] muted">{{ scoreComment }}</div>
        </div>
        <div class="mt-3 space-y-2">
          <div v-for="item in subScores" :key="item.label" class="flex justify-between text-[13px]">
            <span>{{ item.label }}</span><span class="font-bold">{{ item.value }}</span>
          </div>
        </div>
        <button class="w-full mt-4 py-2.5 rounded-2xl bg-primary text-white font-bold" @click="scoreModalOpen = false">知道了</button>
      </div>
    </div>

    <!-- 二次确认弹窗 -->
    <div v-if="confirmMsg" class="overlay overlay--fade-in center">
      <div class="modal modal--sm">
        <div class="text-[15px] font-bold text-center">{{ confirmMsg }}</div>
        <div class="flex gap-2.5 mt-4">
          <button class="flex-1 py-2.5 rounded-2xl font-bold border border-gray-200 muted" @click="doConfirmCancel">取消</button>
          <button class="flex-1 py-2.5 rounded-2xl bg-primary text-white font-bold" @click="doConfirmOk">放弃</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 浮层入场（避免 Transition 在后台标签页卡住离场，统一用 CSS 入场动画） */
.overlay--fade-in {
  animation: fadeIn 0.2s ease;
}

/* 分类 chips */
.cat-chip {
  flex: none;
  border: none;
  cursor: pointer;
  font-size: var(--font-size-xs);
  font-weight: 600;
  padding: 4px 11px;
  border-radius: var(--radius-full);
  background: var(--color-bg-tertiary);
  color: var(--color-ink);
  transition: background 0.2s ease, color 0.2s ease;
}
.cat-chip.sel {
  background: var(--primary-color);
  color: #fff;
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(74, 144, 226, 0.35);
}

/* 故事卡货架 */
.shelf-wrap {
  position: relative;
}
.shelf-wrap::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 28px;
  background: linear-gradient(to right, transparent, var(--color-bg));
  pointer-events: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  z-index: 2;
}
.story-card {
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  border-radius: 14px;
  flex: none;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.story-card:active {
  transform: scale(0.93);
}
.story-card.sel {
  transform: scale(1.06) translateY(-2px);
  box-shadow: 0 0 0 2.5px var(--primary-color), 0 8px 22px rgba(74, 144, 226, 0.32);
}
.story-thumb {
  width: 84px;
  height: 84px;
  border-radius: 14px;
  background-size: cover;
  background-position: center;
  position: relative;
  overflow: hidden;
}
.story-thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.62) 0%, rgba(0, 0, 0, 0.12) 48%, transparent 72%);
  border-radius: 14px;
}
.story-name {
  position: absolute;
  bottom: 5px;
  left: 5px;
  right: 5px;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  z-index: 1;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}
.story-done-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px 5px 2px 3px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
  box-shadow: 0 1px 5px rgba(31, 42, 55, 0.18);
  font-size: 9px;
  font-weight: 800;
  color: #d4760a;
}
.shelf-dots {
  display: flex;
  justify-content: center;
  gap: 5px;
  margin-top: 6px;
}
.shelf-dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(138, 148, 166, 0.35);
  transition: background 0.2s ease, transform 0.2s ease;
}
.shelf-dots i.on {
  background: var(--primary-color);
  transform: scale(1.25);
}

/* 主图标题 chip */
.img-caption-chip {
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
}

/* 转写句子 */
.transcript-actions {
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
}
.ts-sent {
  display: inline;
  padding: 1px 4px;
  margin-right: 5px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}
.ts-sent:hover {
  background: #eef1f6;
}
.ts-sent.typing {
  color: var(--primary-color);
}
.ts-sent.sel {
  background: #dfe3ea;
  color: var(--color-ink);
}
.ts-sent.speaking-ai {
  background: var(--primary-color);
  color: #fff;
}
.ts-sent.speaking-my {
  background: var(--accent-color);
  color: #fff;
}

/* AI读 / 我读 / 删句 */
.read-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: var(--radius-full);
  border: none;
  cursor: pointer;
  transition: transform 0.12s ease, background 0.15s ease, color 0.15s ease, opacity 0.15s ease;
}
.read-btn:active {
  transform: scale(0.94);
}
.read-btn.ai {
  background: var(--tint-blue);
  color: var(--primary-color);
}
.read-btn.my {
  background: var(--tint-orange-soft);
  color: var(--accent-color);
}
.read-btn.del {
  background: #f0f1f4;
  color: var(--color-muted);
}
.read-btn.busy {
  opacity: 0.8;
}
.read-btn.paused {
  opacity: 0.45;
}
.read-btn:disabled {
  opacity: 0.35;
  cursor: default;
  pointer-events: none;
}

/* 讲完啦 */
.finish-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 22px;
  border-radius: var(--radius-full);
  border: none;
  cursor: pointer;
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-color), #ff8f5e);
  box-shadow: 0 6px 16px rgba(255, 107, 53, 0.35);
  transition: background 0.3s ease, box-shadow 0.3s ease, transform 0.12s ease;
}
.finish-btn:active {
  transform: scale(0.94);
}
.finish-btn:disabled:not(.done) {
  background: #c7cfda;
  box-shadow: none;
  cursor: default;
  color: #f6f8fb;
  opacity: 0.6;
}
.finish-btn.done {
  background: #c7cfda;
  box-shadow: none;
  cursor: default;
  color: #f6f8fb;
}

/* 按住讲述 / 再来一次 */
.redo-btn {
  border: none;
  cursor: pointer;
}
.press-wave i {
  width: 3px;
  background: #fff;
  border-radius: 2px;
  animation: wave 0.9s ease-in-out infinite;
}
.press-wave i:nth-child(odd) {
  animation-duration: 0.7s;
}
</style>
