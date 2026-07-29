<template>
  <el-card shadow="never">
    <div class="flex items-center justify-between mb-4">
      <div class="text-sm text-gray-500">
        共 {{ contacts.length }} 个数字人；persona 提示词与任务提示词组合为 system prompt
      </div>
      <el-button type="primary" @click="openCreate">新建数字人</el-button>
    </div>

    <el-table :data="contacts" v-loading="loading" row-key="id">
      <el-table-column label="头像" width="72">
        <template #default="{ row }">
          <el-avatar v-if="row.avatar" :src="row.avatar" :size="36" />
          <el-avatar
            v-else
            :size="36"
            :style="{ background: row.avatarBg ?? '#e7f0fd', fontSize: '18px' }"
          >
            {{ row.emoji ?? row.name[0] }}
          </el-avatar>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="110" />
      <el-table-column prop="name" label="名称" width="130" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.type === 'ai' ? 'primary' : 'success'" size="small">
            {{ row.type === 'ai' ? 'AI' : '真人' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sub" label="副标题" min-width="160" show-overflow-tooltip />
      <el-table-column label="人设提示词" min-width="240">
        <template #default="{ row }">
          <span class="text-gray-500 text-xs">{{ truncate(row.personaPrompt) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="sortOrder" label="排序" width="70" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该数字人？" @confirm="onDelete(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawer" :title="editing ? '编辑数字人' : '新建数字人'" size="520px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="ID" required>
        <el-input v-model="form.id" :disabled="!!editing" placeholder="小写字母开头，如 lily" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.name" maxlength="64" />
      </el-form-item>
      <el-form-item label="类型">
        <el-radio-group v-model="form.type">
          <el-radio value="ai">AI 数字人</el-radio>
          <el-radio value="human">真人角色</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="标签">
        <el-input v-model="form.tag" placeholder="如：陪练者（可空）" maxlength="32" />
      </el-form-item>
      <el-form-item label="副标题">
        <el-input v-model="form.sub" placeholder="如：老师 · 严谨纠错模式" maxlength="128" />
      </el-form-item>
      <el-form-item label="头像 URL">
        <el-input v-model="form.avatar" placeholder="留空则用 Emoji 头像" />
      </el-form-item>
      <el-form-item label="Emoji">
        <el-input v-model="form.emoji" placeholder="如 👩（头像 URL 为空时生效）" maxlength="16" class="!w-40" />
        <el-color-picker v-model="form.avatarBg" class="ml-3" />
        <span class="text-xs text-gray-400 ml-2">Emoji 背景色</span>
      </el-form-item>
      <el-form-item label="人设提示词">
        <el-input
          v-model="form.personaPrompt"
          type="textarea"
          :rows="8"
          placeholder="英文人设描述，与任务提示词 chat_reply 组合为 system prompt"
        />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sortOrder" :min="0" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="drawer = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { contactApi } from '@/api'
import type { AdminContact } from '@/types'

const contacts = ref<AdminContact[]>([])
const loading = ref(false)
const drawer = ref(false)
const saving = ref(false)
const editing = ref<AdminContact | null>(null)

const emptyForm = () => ({
  id: '',
  type: 'ai' as 'ai' | 'human',
  name: '',
  tag: '',
  avatar: '',
  emoji: '',
  avatarBg: '',
  sub: '',
  personaPrompt: '',
  sortOrder: 0,
})
const form = reactive(emptyForm())

function truncate(text: string): string {
  return text.length > 80 ? `${text.slice(0, 80)}…` : text
}

async function load() {
  loading.value = true
  try {
    contacts.value = await contactApi.list()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  drawer.value = true
}

function openEdit(row: AdminContact) {
  editing.value = row
  Object.assign(form, {
    id: row.id,
    type: row.type,
    name: row.name,
    tag: row.tag ?? '',
    avatar: row.avatar ?? '',
    emoji: row.emoji ?? '',
    avatarBg: row.avatarBg ?? '',
    sub: row.sub,
    personaPrompt: row.personaPrompt,
    sortOrder: row.sortOrder,
  })
  drawer.value = true
}

async function onSave() {
  if (!form.id.trim() || !form.name.trim()) {
    ElMessage.warning('ID 与名称必填')
    return
  }
  saving.value = true
  const payload = {
    type: form.type,
    name: form.name.trim(),
    tag: form.tag.trim() || null,
    avatar: form.avatar.trim() || null,
    emoji: form.emoji.trim() || null,
    avatar_bg: form.avatarBg || null,
    sub: form.sub.trim(),
    persona_prompt: form.personaPrompt.trim(),
    sort_order: form.sortOrder,
  }
  try {
    if (editing.value) {
      await contactApi.update(editing.value.id, payload)
    } else {
      await contactApi.create(form.id.trim(), payload)
    }
    ElMessage.success('保存成功')
    drawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(row: AdminContact) {
  try {
    await contactApi.remove(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败（已有聊天记录的数字人不可删除）')
  }
}

onMounted(load)
</script>
