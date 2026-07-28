// 联系人 / 会话 store：联系人列表全局共享（联系人页与聊天页复用），消息属于页面态由 ChatView 自管
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { chatApi } from '@/api'
import type { Contact } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const contacts = ref<Contact[]>([])
  const loading = ref(false)
  const error = ref('')
  const loaded = ref(false)

  /** 拉取联系人（幂等，已加载则跳过） */
  async function ensureContacts() {
    if (loaded.value || loading.value) return
    loading.value = true
    error.value = ''
    try {
      contacts.value = await chatApi.getContacts()
      loaded.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  const contactById = computed(() => (id: string) => contacts.value.find((c) => c.id === id))

  return { contacts, loading, error, loaded, ensureContacts, contactById }
})
