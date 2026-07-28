<script setup lang="ts">
// 联系人页：搜索框（本地过滤）+ 最近聊天列表（AI 徽标 / 真人标签）
import { computed, onMounted, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { toast } from '@/composables/useToast'
import NavBar from '@/components/NavBar.vue'

const store = useChatStore()
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return store.contacts
  return store.contacts.filter(
    (c) => c.name.toLowerCase().includes(kw) || c.sub.toLowerCase().includes(kw) || (c.tag ?? '').toLowerCase().includes(kw),
  )
})

onMounted(() => store.ensureContacts())
</script>

<template>
  <section class="screen">
    <NavBar title="对话">
      <template #right>
        <button class="icon-btn" @click="toast('搜索 / 添加好友')">
          <svg class="licon" width="20" height="20" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        </button>
      </template>
    </NavBar>
    <div class="screen-body">
      <div class="px-[18px] pt-3">
        <div class="glass rounded-2xl px-3 py-2 flex items-center gap-2 text-[13px] muted">
          <svg class="licon" width="18" height="18" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.2-3.2" /></svg>
          <input v-model="keyword" class="bg-transparent outline-none flex-1" placeholder="搜索联系人 / 添加好友" />
        </div>
      </div>
      <div class="px-[18px] mt-4 text-[12px] font-bold muted">最近聊天</div>

      <div v-if="store.loading" class="px-[18px] mt-3 text-[12px] muted">加载中…</div>
      <div v-else-if="store.error" class="px-[18px] mt-3 text-[12px] text-accent">{{ store.error }}</div>
      <div v-else-if="!filtered.length" class="px-[18px] mt-3 text-[12px] muted">未找到匹配的联系人</div>
      <nav v-else class="px-[18px] mt-2 pb-4">
        <RouterLink v-for="c in filtered" :key="c.id" :to="`/chat/${c.id}`" class="contact-item">
          <img v-if="c.type === 'human'" :src="c.avatar" class="w-11 h-11 rounded-2xl" alt="" />
          <div v-else class="w-11 h-11 rounded-2xl flex items-center justify-center text-[22px]" :style="{ background: c.avatarBg }">{{ c.emoji }}</div>
          <div class="flex-1 text-left">
            <div class="font-semibold text-[14px] flex items-center gap-2">
              {{ c.name }}
              <span v-if="c.type === 'ai'" class="badge-ai">AI</span>
              <span v-else-if="c.tag" class="tag tag--accent">{{ c.tag }}</span>
            </div>
            <div class="text-[11px] muted">{{ c.sub }}</div>
          </div>
          <span class="text-[10px] muted">›</span>
        </RouterLink>
      </nav>
    </div>
  </section>
</template>

<style scoped>
.contact-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: var(--spacing-md) 0;
  background: transparent;
  border: none;
  cursor: pointer;
  position: relative;
  text-align: left;
  color: inherit;
  text-decoration: none;
}
.contact-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 56px;
  right: 0;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}
.contact-item:last-child::after {
  display: none;
}
</style>
