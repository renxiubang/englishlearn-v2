// 与后端 /api/admin 响应字段对齐（camelCase 出参 / snake_case 入参）

export type ModuleType = 'storyRead' | 'dialogueRead' | 'listenStory' | 'picStory'

export const MODULE_LABELS: Record<ModuleType, string> = {
  storyRead: '故事跟读',
  dialogueRead: '对话跟读',
  listenStory: '听故事',
  picStory: '看图讲故事',
}

export const MODULE_TYPES = Object.keys(MODULE_LABELS) as ModuleType[]

export interface AdminContact {
  id: string
  type: 'human' | 'ai'
  name: string
  tag: string | null
  avatar: string | null
  emoji: string | null
  avatarBg: string | null
  sub: string
  personaPrompt: string
  sortOrder: number
}

export interface PromptItem {
  key: string
  content: string
  remark: string
  updatedAt: number | null
}

export interface Category {
  id: number
  moduleType: ModuleType
  name: string
  sortOrder: number
}

export interface DialogueTurn {
  role: string
  en: string
  zh?: string
}

export interface StoryContent {
  sentences?: string[]
  turns?: DialogueTurn[]
}

export interface Story {
  id: number
  moduleType: ModuleType
  title: string
  seed: string | null
  cat: string
  content: StoryContent
  sortOrder: number
  enabled: boolean
}

export interface StoryPage {
  list: Story[]
  total: number
  page: number
  limit: number
}
