<template>
  <div class="login-wrap">
    <el-card class="login-card" shadow="hover">
      <div class="text-center mb-6">
        <div class="text-2xl font-bold text-gray-800">EnglishLearn 管理后台</div>
        <div class="text-sm text-gray-400 mt-2">内容运营 · 数字人 · 提示词</div>
      </div>
      <el-form @submit.prevent="onSubmit">
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            size="large"
            placeholder="请输入管理员密码"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="w-full"
          :loading="loading"
          @click="onSubmit"
        >
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  loading.value = true
  try {
    await auth.login(password.value)
    ElMessage.success('登录成功')
    router.push({ name: 'contacts' })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f7fa 100%);
}
.login-card {
  width: 380px;
  padding: 12px 8px;
}
</style>
