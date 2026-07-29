<template>
  <el-form :model="form" label-width="80px">
    <el-form-item label="标题" required>
      <el-input v-model="form.title" maxlength="64" />
    </el-form-item>

    <el-form-item label="分类">
      <el-select v-model="form.cat" placeholder="选择分类" clearable class="!w-56">
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name" />
      </el-select>
      <span class="text-xs text-gray-400 ml-2">先在“分类管理”维护分类</span>
    </el-form-item>

    <el-form-item v-if="moduleType === 'picStory'" label="图片 Seed" required>
      <div class="flex items-center gap-3">
        <el-input v-model="form.seed" placeholder="picsum 取图与进度主键，如 forest" class="!w-56" />
        <img
          v-if="form.seed.trim()"
          :src="`https://picsum.photos/seed/${encodeURIComponent(form.seed.trim())}/160/100`"
          class="rounded border border-gray-200"
          width="160"
          height="100"
          alt="预览"
        />
      </div>
    </el-form-item>

    <!-- 逐句编辑：storyRead / listenStory / picStory -->
    <el-form-item v-if="moduleType !== 'dialogueRead'" label="句子列表" required>
      <div class="w-full space-y-2">
        <div v-for="(_, i) in form.sentences" :key="i" class="flex items-center gap-2">
          <span class="text-xs text-gray-400 w-5 text-right">{{ i + 1 }}</span>
          <el-input v-model="form.sentences[i]" placeholder="英文句子" />
          <el-button
            link
            type="danger"
            :disabled="form.sentences.length <= 1"
            @click="form.sentences.splice(i, 1)"
          >
            删除
          </el-button>
        </div>
        <el-button size="small" @click="form.sentences.push('')">+ 添加句子</el-button>
      </div>
    </el-form-item>

    <!-- 对话编辑：dialogueRead -->
    <el-form-item v-else label="对话内容" required>
      <div class="w-full space-y-2">
        <div v-for="(turn, i) in form.turns" :key="i" class="flex items-center gap-2">
          <el-select v-model="turn.role" class="!w-20">
            <el-option label="A" value="A" />
            <el-option label="B" value="B" />
          </el-select>
          <el-input v-model="turn.en" placeholder="英文台词" />
          <el-input v-model="turn.zh" placeholder="中文翻译（可空）" class="!w-52" />
          <el-button
            link
            type="danger"
            :disabled="form.turns.length <= 1"
            @click="form.turns.splice(i, 1)"
          >
            删除
          </el-button>
        </div>
        <el-button size="small" @click="addTurn">+ 添加对话行</el-button>
      </div>
    </el-form-item>

    <el-form-item label="排序">
      <el-input-number v-model="form.sortOrder" :min="0" />
    </el-form-item>
    <el-form-item label="上架">
      <el-switch v-model="form.enabled" />
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import type { Category, DialogueTurn, ModuleType } from '@/types'

export interface StoryFormModel {
  title: string
  seed: string
  cat: string
  sentences: string[]
  turns: DialogueTurn[]
  sortOrder: number
  enabled: boolean
}

const props = defineProps<{
  moduleType: ModuleType
  form: StoryFormModel
  categories: Category[]
}>()

function addTurn() {
  const last = props.form.turns[props.form.turns.length - 1]
  const role = last?.role === 'A' ? 'B' : 'A'
  props.form.turns.push({ role, en: '', zh: '' })
}
</script>
