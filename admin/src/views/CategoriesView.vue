<template>
  <el-card shadow="never">
    <el-tabs v-model="activeType" @tab-change="load">
      <el-tab-pane
        v-for="t in MODULE_TYPES"
        :key="t"
        :label="MODULE_LABELS[t]"
        :name="t"
      />
    </el-tabs>

    <div class="flex items-center justify-between mb-4">
      <div class="text-sm text-gray-500">
        “全部”分类由接口自动拼接，无需在此维护
      </div>
      <el-button type="primary" @click="openCreate">新建分类</el-button>
    </div>

    <el-table :data="categories" v-loading="loading" row-key="id">
      <el-table-column prop="name" label="分类名" min-width="160" />
      <el-table-column prop="sortOrder" label="排序" width="100" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该分类？" @confirm="onDelete(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog
    v-model="dialog"
    :title="editing ? '编辑分类' : `新建分类（${MODULE_LABELS[activeType]}）`"
    width="420px"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="分类名" required>
        <el-input v-model="form.name" maxlength="32" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sortOrder" :min="0" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { categoryApi } from '@/api'
import { MODULE_LABELS, MODULE_TYPES } from '@/types'
import type { Category, ModuleType } from '@/types'

const activeType = ref<ModuleType>('storyRead')
const categories = ref<Category[]>([])
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const editing = ref<Category | null>(null)
const form = reactive({ name: '', sortOrder: 0 })

async function load() {
  loading.value = true
  try {
    categories.value = await categoryApi.list(activeType.value)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', sortOrder: categories.value.length + 1 })
  dialog.value = true
}

function openEdit(row: Category) {
  editing.value = row
  Object.assign(form, { name: row.name, sortOrder: row.sortOrder })
  dialog.value = true
}

async function onSave() {
  if (!form.name.trim()) {
    ElMessage.warning('分类名不能为空')
    return
  }
  saving.value = true
  const payload = {
    module_type: activeType.value,
    name: form.name.trim(),
    sort_order: form.sortOrder,
  }
  try {
    if (editing.value) {
      await categoryApi.update(editing.value.id, payload)
    } else {
      await categoryApi.create(payload)
    }
    ElMessage.success('保存成功')
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(row: Category) {
  try {
    await categoryApi.remove(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败（有内容引用的分类不可删除）')
  }
}

onMounted(load)
</script>
