// ---------- 通用 ----------
export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// ---------- 用户 ----------
export interface UserProfile {
  id: string
  name: string
  avatar: string
  level: number
  levelTitle: string
  totalHours: number
}

export interface UserStats {
  todayMinutes: number
  streakDays: number
}

// ---------- 联系人 ----------
export interface Contact {
  id: string
  type: 'human' | 'ai'
  name: string
  tag?: string
  avatar?: string
  emoji?: string
  avatarBg?: string
  sub: string
}

// ---------- 聊天 ----------
/** 音频资源引用（后端 /audio/*.wav） */
export interface AudioRef {
  url: string
  duration: string
}

export interface ChatMessage {
  id: number
  from: 'them' | 'me'
  en: string
  zh: string
  duration?: string
  score?: number
  /** 纯文本消息（无语音条） */
  textOnly?: boolean
  /** me 消息：用户原声 */
  userAudio?: AudioRef
  /** me 消息：标准发音 TTS */
  ttsAudio?: AudioRef
  /** them 消息：AI 回复 TTS 音频 */
  url?: string
}

/** 接口 4：游标分页包装 */
export interface MessagePage {
  list: ChatMessage[]
  hasMore: boolean
  nextCursor: number | null
}

export interface ChatReply {
  id: number
  from: 'them'
  en: string
  zh: string
  duration?: string
  textOnly?: boolean
}

// ---------- SSE 事件载荷（接口 5b / 16） ----------
export interface SseAudioChunk {
  seq: number
  /** Int16 PCM mono 24kHz 裸流 base64 */
  base64: string
}

export interface UserBubblePayload {
  id: number
  en: string
  zh: string
  userAudio: AudioRef
  ttsAudio: AudioRef
}

/** 接口 17：复读语义校验结果 */
export interface VerifyResult {
  consistent: boolean
  reason?: string
}

export interface ScoreResult {
  score: number
}

export type ScoreType = 'assist' | 'dialogue' | 'story' | 'picture'

export interface AssistHint {
  zh: string
  en: string
}

// ---------- 收藏 ----------
export interface Favorite {
  id: number
  en: string
  zh: string
  createdAt: number
}

// ---------- 看图讲故事 ----------
export interface PicStory {
  title: string
  seed: string
  cat: string
  sentences: string[]
}

/** seed -> 最高分 */
export type PicStoryProgress = Record<string, number>
