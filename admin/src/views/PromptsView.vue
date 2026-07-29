<template>
  <el-card shadow="never">
    <div class="text-sm text-gray-500 mb-4">
      任务提示词与数字人 persona 组合使用；保存后立即生效，无需重启后端
    </div>
    <el-table :data="prompts" v-loading="loading" row-key="key">
      <el-table-column prop="key" label="Key" width="180" />
      <el-table-column prop="remark" label="用途" min-width="220" show-overflow-tooltip />
      <el-table-column label="内容预览" min-width="280">
        <template #default="{ row }">
          <span class="text-gray-500 text-xs">{{ truncate(row.content) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">
          <span class="text-xs text-gray-400">{{ formatTime(row.updatedAt) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawer" :title="`编辑提示词：${form.key}`" size="640px">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="保存后新提示词对下一次模型调用立即生效"
      class="mb-4"
    />
    <el-form label-position="top">
      <el-form-item label="用途备注">
        <el-input v-model="form.remark" maxlength="255" />
      </el-form-item>
      <el-form-item label="提示词内容" required>
        <el-input v-model="form.content" type="textarea" :rows="16" spellcheck="false" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="drawer = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存并生效</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { promptApi } from '@/api'
import type { PromptItem } from '@/types'

const prompts = ref<PromptItem[]>([])
const loading = ref(false)
const drawer = ref(false)
const saving = ref(false)
const form = reactive({ key: '', content: '', remark: '' })

function truncate(text: string): string {
  return text.length > 100 ? `${text.slice(0, 100)}…` : text
}

function formatTime(ts: number | null): string {
  return ts ? new Date(ts).toLocaleString('zh-CN') : '—'
}

async function load() {
  loading.value = true
  try {
    prompts.value = await promptApi.list()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openEdit(row: PromptItem) {
  Object.assign(form, { key: row.key, content: row.content, remark: row.remark })
  drawer.value = true
}

async function onSave() {
  if (!form.content.trim()) {
    ElMessage.warning('提示词内容不能为空')
    return
  }
  saving.value = true
  try {
    await promptApi.update(form.key, form.content.trim(), form.remark)
    ElMessage.success('已保存并即时生效')
    drawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
