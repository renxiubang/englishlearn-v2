<script setup lang="ts">
// 统一聊天页（AI + 真人）：语音/文本双模输入、按住说话（ECAPA 语种分流）、
// 5a 文字消息 / 5b 语音消息 SSE、游标分页历史、辅助卡片跟读（接口 16/17）
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { assistApi, chatApi } from '@/api'
import { ApiError } from '@/api/http'
import type { AudioRef, Contact, UserBubblePayload } from '@/types'
import { useChatStore } from '@/stores/chat'
import { useFavoritesStore } from '@/stores/favorites'
import { toast } from '@/composables/useToast'
import { useRecorder, type Recording } from '@/composables/useRecorder'
import { detectLanguage, preloadLangDetect } from '@/composables/useLangDetect'
import { createPcmPlayer } from '@/composables/usePcmPlayer'
import NavBar from '@/components/NavBar.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import PressTalkButton from '@/components/PressTalkButton.vue'
import AssistCard from '@/components/AssistCard.vue'
import ActionSheet from '@/components/ActionSheet.vue'

/** 页面内消息（在接口 ChatMessage 基础上增加本地展示标记） */
interface LocalMessage {
  id: number
  from: 'them' | 'me'
  en: string
  zh: string
  /** me 语音消息：原始逐字转录（原译） */
  raw?: string
  duration?: string
  score?: number
  textOnly?: boolean
  userAudio?: AudioRef
  ttsAudio?: AudioRef
  url?: string
  /** 辅助跟读产生的 me 气泡（紧凑语音条变体） */
  assist?: boolean
  /** 乐观插入、等待服务端 user_bubble 回填 */
  pending?: boolean
}

const route = useRoute()
const chatStore = useChatStore()
const favStore = useFavoritesStore()

const contactId = computed(() => String(route.params.id))
const contact = computed<Contact | undefined>(() => chatStore.contactById(contactId.value))

const messages = ref<LocalMessage[]>([])
const loading = ref(true)
/** 本地临时气泡 id（负数，避免与服务端 id 冲突） */
let tempSeq = -1

function byId(id: number): LocalMessage | undefined {
  return messages.value.find((m) => m.id === id)
}

function fmtSeconds(sec: number): string {
  const s = Math.max(1, Math.round(sec))
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0')
}

// ---------- 加载 + 游标分页（接口 4） ----------
const bodyEl = ref<HTMLElement | null>(null)
const hasMore = ref(false)
const loadingMore = ref(false)
let nextCursor: number | null = null

async function scrollBottom() {
  await nextTick()
  bodyEl.value?.scrollTo({ top: bodyEl.value.scrollHeight, behavior: 'smooth' })
}

onMounted(async () => {
  favStore.ensureLoaded()
  await chatStore.ensureContacts()
  try {
    const page = await chatApi.getMessages(contactId.value)
    messages.value = page.list
    hasMore.value = page.hasMore
    nextCursor = page.nextCursor
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
    scrollBottom()
  }
})

/** 滚到顶部附近时向上加载更早消息（prepend 并保持视口位置） */
async function onBodyScroll() {
  const el = bodyEl.value
  if (!el || el.scrollTop > 30 || !hasMore.value || loadingMore.value || nextCursor == null) return
  loadingMore.value = true
  try {
    const page = await chatApi.getMessages(contactId.value, nextCursor)
    const prevHeight = el.scrollHeight
    messages.value = [...page.list, ...messages.value]
    hasMore.value = page.hasMore
    nextCursor = page.nextCursor
    await nextTick()
    el.scrollTop += el.scrollHeight - prevHeight
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败')
  } finally {
    loadingMore.value = false
  }
}

function appendMessage(msg: Omit<LocalMessage, 'id'>): LocalMessage {
  messages.value.push({ ...msg, id: tempSeq-- })
  return messages.value[messages.value.length - 1]
}

// ---------- 语音输入（按住说话 / 按住跟读） ----------
const recorder = useRecorder()
const sending = ref(false)
const player = createPcmPlayer()

onBeforeUnmount(() => {
  recorder.cancel()
  player.dispose()
})

async function onTalkStart() {
  preloadLangDetect()
  await recorder.start()
}

function onTalkCancel() {
  recorder.cancel()
}

async function onTalkSend() {
  const rec = recorder.stop()
  if (!rec || rec.seconds < 0.5) {
    if (rec) toast('说话时间太短')
    return
  }
  // 辅助卡片打开时：松开记录一段跟读语音
  if (assistAudio) {
    assistCardRef.value?.addVoice(rec)
    toast('已记录跟读语音，可继续跟读或点击"读完啦"')
    return
  }
  if (sending.value) {
    toast('AI 正在回复中，请稍候')
    return
  }
  const lang = await detectLanguage(rec.samples)
  if (lang === 'zh') {
    // 识别到中文 → 进入辅助卡片（接口 16）
    toast('识别到中文，正在为你进入辅助…')
    assistAudio = rec
    assistShown.value = true
    scrollBottom()
  } else {
    await sendVoice(rec)
  }
}

/** 接口 5b：上传语音 → 消费 SSE 事件流（AI 回复流式 + 用户气泡回填） */
async function sendVoice(rec: Pick<Recording, 'blob' | 'seconds'>, assist = false) {
  sending.value = true
  player.stop()
  const pendingMsg = appendMessage({
    from: 'me',
    en: '',
    zh: '',
    duration: fmtSeconds(rec.seconds),
    assist,
    pending: true,
  })
  scrollBottom()
  let aiId: number | null = null
  try {
    await chatApi.sendAudio(contactId.value, rec.blob, (event, data) => {
      switch (event) {
        case 'reply_start': {
          aiId = Number(data.id)
          messages.value.push({ id: aiId, from: 'them', en: '', zh: '' })
          scrollBottom()
          break
        }
        case 'reply_delta': {
          const ai = aiId != null ? byId(aiId) : undefined
          if (ai) ai.en += String(data.text ?? '')
          break
        }
        case 'reply_audio_chunk':
          // 分片 Int16 PCM 24kHz → 边收边播
          player.feed(String(data.base64 ?? ''))
          break
        case 'reply_end': {
          const ai = aiId != null ? byId(aiId) : undefined
          if (ai) {
            ai.duration = String(data.duration ?? '')
            if (typeof data.url === 'string') ai.url = data.url
          }
          scrollBottom()
          break
        }
        case 'user_en':
          pendingMsg.en = String(data.en ?? '')
          pendingMsg.raw = String(data.raw ?? '')
          break
        case 'user_bubble': {
          const b = data as unknown as UserBubblePayload
          Object.assign(pendingMsg, {
            id: b.id,
            en: b.en,
            raw: b.raw,
            userAudio: b.userAudio,
            ttsAudio: b.ttsAudio,
            duration: b.userAudio?.duration ?? pendingMsg.duration,
            pending: false,
          })
          break
        }
      }
    })
  } catch (e) {
    // 失败回滚：移除 pending 用户气泡与半成品 AI 气泡
    player.stop()
    messages.value = messages.value.filter((m) => m !== pendingMsg && m.id !== aiId)
    if (e instanceof ApiError && e.code === 409) toast('AI 正在回复中，请稍候')
    else toast(e instanceof Error ? e.message : '发送失败')
  } finally {
    sending.value = false
  }
}

// ---------- 文本输入（接口 5a） ----------
const inputMode = ref<'voice' | 'text'>('voice')
const draft = ref('')
const textInput = ref<HTMLInputElement | null>(null)

function toggleInputMode() {
  inputMode.value = inputMode.value === 'voice' ? 'text' : 'voice'
  if (inputMode.value === 'text') nextTick(() => textInput.value?.focus())
}

async function sendText() {
  const text = draft.value.trim()
  if (!text) return
  if (sending.value) {
    toast('AI 正在回复中，请稍候')
    return
  }
  draft.value = ''
  sending.value = true
  const local = appendMessage({ from: 'me', en: text, zh: '', textOnly: true })
  scrollBottom()
  try {
    const { reply } = await chatApi.sendText(contactId.value, text)
    messages.value.push({
      id: reply.id,
      from: 'them',
      en: reply.en,
      zh: reply.zh ?? '',
      textOnly: reply.textOnly,
      duration: reply.duration,
    })
    scrollBottom()
  } catch (e) {
    // 失败回滚并还原草稿，避免用户输入丢失
    messages.value = messages.value.filter((m) => m !== local)
    draft.value = text
    if (e instanceof ApiError && e.code === 409) toast('AI 正在回复中，请稍候')
    else toast(e instanceof Error ? e.message : '发送失败')
  } finally {
    sending.value = false
  }
}

// ---------- 辅助卡片流程（接口 16/17） ----------
/** 触发辅助的中文录音（非响应式，仅传递给卡片） */
let assistAudio: Recording | null = null
const assistShown = ref(false)
const assistCardRef = ref<InstanceType<typeof AssistCard> | null>(null)
const verifying = ref(false)

function closeAssist() {
  assistAudio = null
  assistShown.value = false
}

async function onAssistFinish(payload: { count: number; rec: Recording | null; en: string }) {
  if (verifying.value) return
  if (!payload.rec || !payload.en) {
    toast('请先跟读一遍')
    return
  }
  verifying.value = true
  try {
    // 接口 17：复读语义校验
    const r = await assistApi.verify(payload.rec.blob, payload.en)
    if (!r.consistent) {
      assistCardRef.value?.resetVoices()
      toast(r.reason || '读的不太准，重新来一次吧')
      return
    }
    const rec = payload.rec
    closeAssist()
    // 校验通过：复读音频作为正式语音消息走 5b 上屏并获取 AI 回复
    await sendVoice(rec, true)
  } catch (e) {
    toast(e instanceof Error ? e.message : '校验失败')
  } finally {
    verifying.value = false
  }
}

// ---------- 收藏 ----------
function onFavorite(payload: { en: string; zh: string; faved: boolean }) {
  favStore.toggle(payload.en, payload.zh, payload.faved)
}

// ---------- 按需翻译（接口 19） ----------
/** 点击气泡"翻译"按钮：zh 未生成时调接口回填（落库供历史复用） */
async function onTranslate(m: LocalMessage) {
  // 已有译文或本地临时气泡（负 id，尚未落库）时跳过
  if (m.zh || m.id < 0) return
  try {
    const { zh } = await chatApi.translateMessage(m.id)
    m.zh = zh
  } catch (e) {
    toast(e instanceof Error ? e.message : '翻译失败')
  }
}

// ---------- 菜单 / 附加功能面板 ----------
const menuOpen = ref(false)
const plusOpen = ref(false)
const clearing = ref(false)

/** 接口 18：清空聊天记录（后端删除消息/音频后再清本地态） */
async function clearHistory() {
  if (clearing.value) return
  if (sending.value) {
    toast('AI 正在回复中，请稍候')
    return
  }
  clearing.value = true
  try {
    await chatApi.clearMessages(contactId.value)
    player.stop()
    messages.value = []
    hasMore.value = false
    nextCursor = null
    menuOpen.value = false
    toast('聊天记录已清空')
  } catch (e) {
    toast(e instanceof Error ? e.message : '清空失败')
  } finally {
    clearing.value = false
  }
}

function plusAction(name: string) {
  plusOpen.value = false
  toast(name)
}
</script>

<template>
  <section class="screen">
    <NavBar title="聊天" back back-to="/contacts">
      <template #title>
        <span class="flex items-center gap-2">
          {{ contact?.name ?? '聊天' }}
          <span v-if="contact?.type === 'ai'" class="badge-ai">AI</span>
          <span v-else-if="contact?.tag" class="tag tag--accent">{{ contact.tag }}</span>
        </span>
      </template>
      <template #right>
        <button class="icon-btn" @click="menuOpen = true">
          <svg class="licon" width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></svg>
        </button>
      </template>
    </NavBar>

    <!-- 消息区 -->
    <div ref="bodyEl" class="screen-body screen-body--secondary p-[14px] space-y-3" @scroll.passive="onBodyScroll">
      <div v-if="loading" class="text-center text-[12px] muted mt-8">加载中…</div>
      <template v-else>
        <div v-if="loadingMore" class="text-center text-[12px] muted">加载更早消息…</div>
        <div v-for="m in messages" :key="m.id">
          <!-- 对方消息：头像 + 气泡 -->
          <div v-if="m.from === 'them'" class="flex items-start gap-2">
            <img v-if="contact?.type === 'human'" :src="contact.avatar" class="w-8 h-8 rounded-xl flex-none" alt="" />
            <div v-else class="w-8 h-8 rounded-xl flex items-center justify-center flex-none" :style="{ background: contact?.avatarBg }">{{ contact?.emoji }}</div>
            <ChatBubble
              side="them"
              :en="m.en"
              :zh="m.zh"
              :duration="m.duration"
              :url="m.url"
              :text-only="m.textOnly"
              :warn-on-translate="contact?.type === 'human'"
              :favorited="favStore.has(m.en)"
              @favorite="onFavorite"
              @translate="onTranslate(m)"
            />
          </div>
          <!-- 我方消息 -->
          <div v-else class="flex justify-end">
            <ChatBubble
              side="me"
              :en="m.en"
              :zh="m.zh"
              :raw="m.raw"
              :duration="m.duration"
              :score="m.score"
              :text-only="m.textOnly"
              :compact="m.assist"
              :user-audio="m.userAudio"
              :tts-audio="m.ttsAudio"
              :favorited="favStore.has(m.en)"
              @favorite="onFavorite"
              @translate="onTranslate(m)"
            />
          </div>
        </div>
      </template>
    </div>

    <!-- 辅助卡片（输入条上方）：中文录音交给卡片走接口 16 翻译 -->
    <AssistCard
      v-if="assistShown && assistAudio"
      ref="assistCardRef"
      :audio="assistAudio.blob"
      mode="chat"
      @close="closeAssist"
      @finish="onAssistFinish"
      @favorite="onFavorite"
    />

    <!-- 输入条：表情 / 模式切换 / 按住说话或文本框 / 附加功能 -->
    <footer class="chat-input-bar">
      <button class="icon-btn flex-none" @click="toast('表情选择')">
        <svg class="licon" width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M8.5 14a4 4 0 0 0 7 0" /><path d="M9 9.5h.01M15 9.5h.01" /></svg>
      </button>
      <button class="chat-mode-btn flex-none w-11 h-11 flex items-center justify-center rounded-full" @click="toggleInputMode">
        <svg v-if="inputMode === 'text'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="22" /></svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="2" /><line x1="6" y1="10" x2="6.01" y2="10" /><line x1="10" y1="10" x2="10.01" y2="10" /><line x1="14" y1="10" x2="14.01" y2="10" /><line x1="18" y1="10" x2="18.01" y2="10" /><path d="M6 14h12" /></svg>
      </button>

      <PressTalkButton
        v-if="inputMode === 'voice'"
        :label="assistShown ? '按住 跟读' : '按住 说话'"
        class="chat-voice-btn flex-1 py-2.5 rounded-full font-semibold text-[13px] text-primary"
        @start="onTalkStart"
        @cancel="onTalkCancel"
        @send="onTalkSend"
      />
      <template v-else>
        <input
          ref="textInput"
          v-model="draft"
          class="chat-text-input flex-1 px-4 py-2 rounded-full text-[13px] outline-none"
          placeholder="输入消息..."
          @keydown.enter.prevent="sendText"
        />
        <button class="chat-send-btn flex-none w-11 h-11 flex items-center justify-center rounded-full text-white" @click="sendText">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
        </button>
      </template>

      <button class="icon-btn flex-none" @click="plusOpen = true">
        <svg class="licon" width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      </button>
    </footer>

    <!-- 聊天菜单 -->
    <ActionSheet :show="menuOpen" flat @close="menuOpen = false">
      <div class="flex items-center gap-3 mb-3">
        <img v-if="contact?.type === 'human'" :src="contact.avatar" class="w-11 h-11 rounded-2xl" alt="" />
        <div v-else class="w-11 h-11 rounded-2xl flex items-center justify-center text-[22px]" :style="{ background: contact?.avatarBg }">{{ contact?.emoji }}</div>
        <div>
          <div class="text-[15px] font-bold flex items-center gap-2">
            {{ contact?.name }}
            <span v-if="contact?.type === 'ai'" class="badge-ai">AI</span>
          </div>
          <div class="text-[11px] muted mt-0.5">{{ contact?.sub }}</div>
        </div>
      </div>
      <button class="sheet-option--danger w-full flex items-center gap-3 p-3 rounded-2xl" :disabled="clearing" @click="clearHistory">
        <span class="label text-[14px] font-semibold">{{ clearing ? '正在清空…' : '清空聊天记录' }}</span>
      </button>
    </ActionSheet>

    <!-- 附加功能面板 -->
    <ActionSheet :show="plusOpen" flat @close="plusOpen = false">
      <div class="grid grid-cols-4 gap-4 text-center text-[11px]">
        <button @click="plusAction('选择图片')">
          <div class="icon-tile--blue w-14 h-14 mx-auto rounded-2xl flex items-center justify-center">🖼️</div>
          <div class="mt-1.5 font-medium">图片</div>
        </button>
        <button @click="plusAction('打开相机')">
          <div class="icon-tile--orange w-14 h-14 mx-auto rounded-2xl flex items-center justify-center">📷</div>
          <div class="mt-1.5 font-medium">拍摄</div>
        </button>
        <button @click="plusAction('视频通话')">
          <div class="icon-tile--green w-14 h-14 mx-auto rounded-2xl flex items-center justify-center">📹</div>
          <div class="mt-1.5 font-medium">视频通话</div>
        </button>
        <button @click="plusAction('语音通话')">
          <div class="icon-tile--purple w-14 h-14 mx-auto rounded-2xl flex items-center justify-center">📞</div>
          <div class="mt-1.5 font-medium">语音通话</div>
        </button>
      </div>
    </ActionSheet>
  </section>
</template>

<style scoped>
/* Component: ChatInputBar */
.chat-input-bar {
  flex: none;
  background: var(--color-surface);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px calc(8px + env(safe-area-inset-bottom, 0px));
}
.chat-mode-btn {
  color: var(--color-ink);
  background: transparent;
  border: none;
  cursor: pointer;
}
.chat-mode-btn:active {
  background: rgba(0, 0, 0, 0.06);
}
.chat-text-input {
  background: var(--color-bg-tertiary);
  border: none;
}
.chat-send-btn {
  background: var(--primary-color);
  border: none;
  cursor: pointer;
}
/* 常态胶囊底色（按住态由 PressTalkButton 内部样式覆盖） */
.chat-voice-btn:not(.pressing) {
  background: var(--color-bg-tertiary);
}
</style>
