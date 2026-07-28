<script setup lang="ts">
// 首页：问候区（时段问候 + 用户资料）+ 学习统计卡 + 功能入口 x4 + 我的收藏 + 继续练习
import { computed, onMounted, ref } from 'vue'
import { userApi } from '@/api'
import type { UserProfile, UserStats } from '@/types'
import { useChatStore } from '@/stores/chat'
import { useFavoritesStore } from '@/stores/favorites'

const profile = ref<UserProfile | null>(null)
const stats = ref<UserStats | null>(null)
const chatStore = useChatStore()
const favStore = useFavoritesStore()

/** 按当前时段生成问候语 */
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '上午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

/** 继续练习入口：与爸爸的对话（原型固定推荐 dad） */
const dad = computed(() => chatStore.contactById('dad'))

onMounted(async () => {
  chatStore.ensureContacts()
  favStore.ensureLoaded()
  try {
    ;[profile.value, stats.value] = await Promise.all([userApi.getProfile(), userApi.getStats()])
  } catch {
    // 资料加载失败不阻塞页面，保留占位
  }
})
</script>

<template>
  <section class="screen">
    <div class="screen-body">
      <header class="screen-hero">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-[13px] muted flex items-center gap-1.5">
              {{ greeting }}，{{ profile?.name ?? '…' }}
              <span class="mascot-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="11" r="7" fill="#4A90E2" opacity=".15" /><circle cx="12" cy="11" r="5" fill="#4A90E2" /><circle cx="10" cy="10" r="1.2" fill="#fff" /><circle cx="14" cy="10" r="1.2" fill="#fff" /><path d="M10 13c.8.8 3.2.8 4 0" stroke="#fff" stroke-width="1.2" stroke-linecap="round" /><path d="M7 8c-1-2 0-4 2-4" stroke="#FF6B35" stroke-width="1.5" stroke-linecap="round" /><path d="M17 8c1-2 0-4-2-4" stroke="#FF6B35" stroke-width="1.5" stroke-linecap="round" /></svg>
              </span>
            </div>
            <div class="typ-display">今天也来练口语吧</div>
          </div>
          <img v-if="profile" :src="profile.avatar" class="w-11 h-11 rounded-2xl object-cover" alt="avatar" />
          <div v-else class="w-11 h-11 rounded-2xl bg-tertiary"></div>
        </div>

        <!-- Component: StatsCard（学习时长 / 连续打卡） -->
        <div class="card glass card-gradient-brand mt-4 p-4 flex items-center justify-between">
          <div>
            <div class="text-[12px] muted">今日学习时长</div>
            <div class="text-[26px] font-extrabold text-primary">{{ stats?.todayMinutes ?? '—' }}<span class="text-[14px] font-bold"> 分钟</span></div>
          </div>
          <div class="text-right">
            <div class="text-[12px] muted">连续打卡</div>
            <div class="text-[20px] font-extrabold text-accent">{{ stats?.streakDays ?? '—' }} 天 🔥</div>
          </div>
        </div>
      </header>

      <!-- Component: FeatureCard（功能入口卡片 x4） -->
      <nav class="px-[18px] grid grid-cols-2 gap-3 mt-2">
        <RouterLink to="/story-read" class="card p-4 text-left block">
          <div class="icon-tile--blue w-12 h-12 rounded-2xl flex items-center justify-center">
            <svg class="licon" width="26" height="26" viewBox="0 0 24 24" stroke="#4A90E2" aria-hidden="true"><path d="M12 6c-1.6-1-4-1.6-6-1.6V18c2 0 4.4.6 6 1.6 1.6-1 4-1.6 6-1.6V4.4c-2 0-4.4.6-6 1.6z" /><path d="M12 6v13.6" /></svg>
          </div>
          <div class="mt-3 font-bold text-[15px]">故事跟读</div>
          <div class="text-[11px] muted mt-1">高亮句子 · 逐句评分</div>
        </RouterLink>
        <RouterLink to="/dialogue-read" class="card p-4 text-left block">
          <div class="icon-tile--orange w-12 h-12 rounded-2xl flex items-center justify-center">
            <svg class="licon" width="26" height="26" viewBox="0 0 24 24" stroke="#FF6B35" aria-hidden="true"><path d="M8 13a5 5 0 0 1 5-5h1a5 5 0 0 1 0 10h-1l-4 3v-3a5 5 0 0 1-1-5z" /><path d="M6.5 9.5A4.5 4.5 0 0 1 10 5" /></svg>
          </div>
          <div class="mt-3 font-bold text-[15px]">对话跟读</div>
          <div class="text-[11px] muted mt-1">角色扮演 · 气泡对练</div>
        </RouterLink>
        <RouterLink to="/listen-story" class="card p-4 text-left block">
          <div class="icon-tile--green w-12 h-12 rounded-2xl flex items-center justify-center">
            <svg class="licon" width="26" height="26" viewBox="0 0 24 24" stroke="#2fa562" aria-hidden="true"><path d="M4 13v-1a8 8 0 0 1 16 0v1" /><rect x="3" y="13" width="4" height="7" rx="1.6" /><rect x="17" y="13" width="4" height="7" rx="1.6" /></svg>
          </div>
          <div class="mt-3 font-bold text-[15px]">听故事</div>
          <div class="text-[11px] muted mt-1">倍速 · 单句循环</div>
        </RouterLink>
        <RouterLink to="/picture-story" class="card p-4 text-left block">
          <div class="icon-tile--purple w-12 h-12 rounded-2xl flex items-center justify-center">
            <svg class="licon" width="26" height="26" viewBox="0 0 24 24" stroke="#7c5cc4" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5" /><circle cx="8.5" cy="9.5" r="1.4" /><path d="M21 15.5 16 11 6 20" /></svg>
          </div>
          <div class="mt-3 font-bold text-[15px]">看图讲故事</div>
          <div class="text-[11px] muted mt-1">选故事 · 讲述 · 评分</div>
        </RouterLink>
      </nav>

      <!-- 我的收藏入口 -->
      <div class="px-[18px] mt-3">
        <RouterLink to="/favorites" class="card p-3.5 w-full flex items-center gap-3">
          <div class="icon-tile--yellow w-10 h-10 rounded-2xl flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
          </div>
          <div class="flex-1 text-left">
            <div class="font-semibold text-[14px]">我的收藏</div>
            <div class="text-[11px] muted">收藏的句子随时复习</div>
          </div>
          <span class="muted text-[13px]">{{ favStore.count }} 句 ›</span>
        </RouterLink>
      </div>

      <!-- 继续练习 -->
      <section class="px-[18px] mt-4 mb-4">
        <div class="text-[14px] font-bold mb-2">继续练习</div>
        <RouterLink v-if="dad" to="/chat/dad" class="w-full flex items-center gap-3 px-0 py-3.5">
          <img :src="dad.avatar" class="w-10 h-10 rounded-xl" alt="" />
          <div class="flex-1 text-left">
            <div class="font-semibold text-[14px]">和 {{ dad.name }} 的英语对话</div>
            <div class="text-[11px] muted">陪练者模式 · 3 条未跟读</div>
          </div>
          <span class="text-accent text-[13px] font-bold">继续 ›</span>
        </RouterLink>
      </section>
    </div>
  </section>
</template>
