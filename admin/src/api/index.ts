import { http } from './http'
import type {
  AdminContact,
  Category,
  ModuleType,
  PromptItem,
  Story,
  StoryContent,
  StoryPage,
} from '@/types'

// ---------- 登录 ----------
export const authApi = {
  login: (password: string) =>
    http.post<{ token: string; expiresIn: number }>('/admin/login', { password }),
}

// ---------- 数字人 ----------
export interface ContactPayload {
  type: 'human' | 'ai'
  name: string
  tag?: string | null
  avatar?: string | null
  emoji?: string | null
  avatar_bg?: string | null
  sub?: string
  persona_prompt?: string
  sort_order?: number
}

export const contactApi = {
  list: () => http.get<AdminContact[]>('/admin/contacts'),
  create: (id: string, payload: ContactPayload) =>
    http.post<AdminContact>('/admin/contacts', { id, ...payload }),
  update: (id: string, payload: ContactPayload) =>
    http.put<AdminContact>(`/admin/contacts/${id}`, payload),
  remove: (id: string) => http.delete<{ removed: boolean }>(`/admin/contacts/${id}`),
}

// ---------- 提示词 ----------
export const promptApi = {
  list: () => http.get<PromptItem[]>('/admin/prompts'),
  update: (key: string, content: string, remark?: string) =>
    http.put<PromptItem>(`/admin/prompts/${key}`, { content, remark }),
}

// ---------- 分类 ----------
export interface CategoryPayload {
  module_type: ModuleType
  name: string
  sort_order?: number
}

export const categoryApi = {
  list: (type?: ModuleType) =>
    http.get<Category[]>(`/admin/categories${type ? `?type=${type}` : ''}`),
  create: (payload: CategoryPayload) => http.post<Category>('/admin/categories', payload),
  update: (id: number, payload: CategoryPayload) =>
    http.put<Category>(`/admin/categories/${id}`, payload),
  remove: (id: number) => http.delete<{ removed: boolean }>(`/admin/categories/${id}`),
}

// ---------- 内容 stories ----------
export interface StoryPayload {
  module_type: ModuleType
  title: string
  seed?: string | null
  cat?: string
  content: StoryContent
  sort_order?: number
  enabled?: boolean
}

export const storyApi = {
  page: (type: ModuleType, page: number, limit: number, cat?: string) => {
    const qs = new URLSearchParams({ type, page: String(page), limit: String(limit) })
    if (cat) qs.set('cat', cat)
    return http.get<StoryPage>(`/admin/stories?${qs}`)
  },
  create: (payload: StoryPayload) => http.post<Story>('/admin/stories', payload),
  update: (id: number, payload: StoryPayload) =>
    http.put<Story>(`/admin/stories/${id}`, payload),
  toggleEnabled: (id: number, enabled: boolean) =>
    http.patch<Story>(`/admin/stories/${id}/enabled`, { enabled }),
  remove: (id: number) => http.delete<{ removed: boolean }>(`/admin/stories/${id}`),
}
