import { http } from './http'
import { postSse, type SseHandler } from './sse'
import type {
  AssistHint,
  ChatReply,
  Contact,
  Favorite,
  MessagePage,
  PicStory,
  PicStoryProgress,
  ScoreResult,
  ScoreType,
  UserProfile,
  UserStats,
  VerifyResult,
} from '@/types'

// ---------- 用户 ----------
export const userApi = {
  getProfile: () => http.get<UserProfile>('/user/profile'),
  getStats: () => http.get<UserStats>('/user/stats'),
}

// ---------- 联系人 / 聊天 ----------
export const chatApi = {
  getContacts: () => http.get<Contact[]>('/contacts'),
  /** 接口 4：游标分页（cursor 缺省取最新一页） */
  getMessages: (contactId: string, cursor?: number, limit = 20) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (cursor != null) qs.set('cursor', String(cursor))
    return http.get<MessagePage>(`/chats/${contactId}/messages?${qs}`)
  },
  /** 接口 5a：文字消息（同步 JSON） */
  sendText: (contactId: string, text: string) =>
    http.post<{ reply: ChatReply }>(`/chats/${contactId}/messages`, { text }),
  /** 接口 5b：语音消息（multipart → SSE） */
  sendAudio: (contactId: string, wav: Blob, onEvent: SseHandler) => {
    const form = new FormData()
    form.append('audio', wav, 'record.wav')
    return postSse(`/chats/${contactId}/messages`, form, onEvent)
  },
  /** 接口 18：清空聊天记录 */
  clearMessages: (contactId: string) =>
    http.delete<{ removed: number }>(`/chats/${contactId}/messages`),
}

// ---------- 语音（看图讲故事评分，仍走 mock） ----------
export const speechApi = {
  score: (type: ScoreType) => http.post<ScoreResult>('/speech/score', { type }),
}

// ---------- 辅助卡片 ----------
export const assistApi = {
  /** 接口 8（mock）：看图讲故事辅助提示 */
  getHint: (scene: 'chat' | 'picture') => http.get<AssistHint>(`/assist-hints?scene=${scene}`),
  /** 接口 16：中文语音 → zh/en/audio_chunk/audio_end（SSE） */
  translate: (wav: Blob, onEvent: SseHandler) => {
    const form = new FormData()
    form.append('audio', wav, 'assist.wav')
    return postSse('/assist/translate', form, onEvent)
  },
  /** 接口 17：复读语义校验（同步 JSON） */
  verify: (wav: Blob, en: string) => {
    const form = new FormData()
    form.append('audio', wav, 'verify.wav')
    form.append('en', en)
    return http.postForm<VerifyResult>('/assist/verify', form)
  },
}

// ---------- 收藏 ----------
export const favoriteApi = {
  list: () => http.get<Favorite[]>('/favorites'),
  add: (en: string, zh: string) => http.post<Favorite>('/favorites', { en, zh }),
  remove: (id: number) => http.delete<{ removed: boolean }>(`/favorites/${id}`),
}

// ---------- 看图讲故事 ----------
export const picStoryApi = {
  list: () => http.get<PicStory[]>('/pic-stories'),
  getCategories: () => http.get<string[]>('/categories?type=picStory'),
  getProgress: () => http.get<PicStoryProgress>('/pic-story-progress'),
  saveProgress: (seed: string, score: number) =>
    http.put<PicStoryProgress>('/pic-story-progress', { seed, score }),
}
