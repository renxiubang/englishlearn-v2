<template>
  <el-card shadow="never">
    <el-tabs v-model="activeType" @tab-change="onTypeChange">
      <el-tab-pane
        v-for="t in MODULE_TYPES"
        :key="t"
        :label="MODULE_LABELS[t]"
        :name="t"
      />
    </el-tabs>

    <div class="flex items-center justify-between mb-4">
      <el-select
        v-model="filterCat"
        placeholder="全部分类"
        clearable
        class="!w-48"
        @change="loadPage(1)"
      >
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name" />
      </el-select>
      <el-button type="primary" @click="openCreate">新建内容</el-button>
    </div>

    <el-table :data="stories" v-loading="loading" row-key="id">
      <el-table-column v-if="activeType === 'picStory'" label="图片" width="96">
        <template #default="{ row }">
          <img
            v-if="row.seed"
            :src="`https://picsum.photos/seed/${encodeURIComponent(row.seed)}/80/50`"
            class="rounded"
            width="80"
            height="50"
            alt=""
          />
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="cat" label="分类" width="110" />
      <el-table-column :label="activeType === 'dialogueRead' ? '对话数' : '句数'" width="90">
        <template #default="{ row }">
          {{ contentCount(row) }}
        </template>
      </el-table-column>
      <el-table-column v-if="activeType === 'picStory'" prop="seed" label="Seed" width="120" />
      <el-table-column prop="sortOrder" label="排序" width="80" />
      <el-table-column label="上架" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            @change="(v: string | number | boolean) => onToggle(row, Boolean(v))"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该内容？" @confirm="onDelete(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="flex justify-end mt-4">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="limit"
        :current-page="page"
        @current-change="loadPage"
      />
    </div>
  </el-card>

  <el-drawer
    v-model="drawer"
    :title="editing ? '编辑内容' : `新建内容（${MODULE_LABELS[activeType]}）`"
    size="680px"
  >
    <StoryForm :module-type="activeType" :form="form" :categories="categories" />
    <template #footer>
      <el-button @click="drawer = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { categoryApi, storyApi } from '@/api'
import type { StoryPayload } from '@/api'
import StoryForm from '@/components/StoryForm.vue'
import type { StoryFormModel } from '@/components/StoryForm.vue'
import { MODULE_LABELS, MODULE_TYPES } from '@/types'
import type { Category, ModuleType, Story } from '@/types'

const activeType = ref<ModuleType>('storyRead')
const categories = ref<Category[]>([])
const filterCat = ref('')
const stories = ref<Story[]>([])
const total = ref(0)
const page = ref(1)
const limit = 10
const loading = ref(false)
const drawer = ref(false)
const saving = ref(false)
const editing = ref<Story | null>(null)

const emptyForm = (): StoryFormModel => ({
  title: '',
  seed: '',
  cat: '',
  sentences: [''],
  turns: [{ role: 'A', en: '', zh: '' }],
  sortOrder: 0,
  enabled: true,
})
const form = reactive(emptyForm())

function contentCount(row: Story): number {
  return row.moduleType === 'dialogueRead'
    ? row.content.turns?.length ?? 0
    : row.content.sentences?.length ?? 0
}

async function loadCategories() {
  try {
    categories.value = await categoryApi.list(activeType.value)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '分类加载失败')
  }
}

async function loadPage(p: number) {
  page.value = p
  loading.value = true
  try {
    const res = await storyApi.page(activeType.value, p, limit, filterCat.value || undefined)
    stories.value = res.list
    total.value = res.total
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function onTypeChange() {
  filterCat.value = ''
  await Promise.all([loadCategories(), loadPage(1)])
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm(), {
    cat: filterCat.value,
    sortOrder: total.value + 1,
  })
  drawer.value = true
}

function openEdit(row: Story) {
  editing.value = row
  Object.assign(form, {
    title: row.title,
    seed: row.seed ?? '',
    cat: row.cat,
    sentences: row.content.sentences?.length ? [...row.content.sentences] : [''],
    turns: row.content.turns?.length
      ? row.content.turns.map((t) => ({ role: t.role, en: t.en, zh: t.zh ?? '' }))
      : [{ role: 'A', en: '', zh: '' }],
    sortOrder: row.sortOrder,
    enabled: row.enabled,
  })
  drawer.value = true
}

function buildPayload(): StoryPayload | null {
  if (!form.title.trim()) {
    ElMessage.warning('标题不能为空')
    return null
  }
  if (activeType.value === 'picStory' && !form.seed.trim()) {
    ElMessage.warning('看图讲故事必须填写图片 Seed')
    return null
  }
  const payload: StoryPayload = {
    module_type: activeType.value,
    title: form.title.trim(),
    seed: activeType.value === 'picStory' ? form.seed.trim() : null,
    cat: form.cat,
    content: {},
    sort_order: form.sortOrder,
    enabled: form.enabled,
  }
  if (activeType.value === 'dialogueRead') {
    const turns = form.turns
      .map((t) => ({ role: t.role, en: t.en.trim(), zh: t.zh?.trim() || undefined }))
      .filter((t) => t.en)
    if (!turns.length) {
      ElMessage.warning('至少填写一行英文对话')
      return null
    }
    payload.content = { turns }
  } else {
    const sentences = form.sentences.map((s) => s.trim()).filter(Boolean)
    if (!sentences.length) {
      ElMessage.warning('至少填写一个句子')
      return null
    }
    payload.content = { sentences }
  }
  return payload
}

async function onSave() {
  const payload = buildPayload()
  if (!payload) return
  saving.value = true
  try {
    if (editing.value) {
      await storyApi.update(editing.value.id, payload)
    } else {
      await storyApi.create(payload)
    }
    ElMessage.success('保存成功')
    drawer.value = false
    await loadPage(page.value)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function onToggle(row: Story, enabled: boolean) {
  try {
    await storyApi.toggleEnabled(row.id, enabled)
    row.enabled = enabled
    ElMessage.success(enabled ? '已上架' : '已下架')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function onDelete(row: Story) {
  try {
    await storyApi.remove(row.id)
    ElMessage.success('已删除')
    const lastPage = Math.max(1, Math.ceil((total.value - 1) / limit))
    await loadPage(Math.min(page.value, lastPage))
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(() => {
  loadCategories()
  loadPage(1)
})
</script>
