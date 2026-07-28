// 收藏 store：与 /api/favorites 同步，按英文原句去重（气泡/辅助卡片收藏共用）
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { favoriteApi } from '@/api'
import type { Favorite } from '@/types'

export const useFavoritesStore = defineStore('favorites', () => {
  const items = ref<Favorite[]>([])
  const loaded = ref(false)

  async function ensureLoaded() {
    if (loaded.value) return
    try {
      items.value = await favoriteApi.list()
      loaded.value = true
    } catch {
      // 静默失败：收藏非关键路径，下次操作时重试
    }
  }

  const count = computed(() => items.value.length)

  function has(en: string) {
    return items.value.some((f) => f.en === en)
  }

  /** 收藏 / 取消收藏（faved 为目标状态） */
  async function toggle(en: string, zh: string, faved: boolean) {
    if (faved) {
      const row = await favoriteApi.add(en, zh)
      if (!has(row.en)) items.value.unshift(row)
    } else {
      const row = items.value.find((f) => f.en === en)
      if (!row) return
      await favoriteApi.remove(row.id)
      items.value = items.value.filter((f) => f.id !== row.id)
    }
  }

  return { items, count, loaded, ensureLoaded, has, toggle }
})
