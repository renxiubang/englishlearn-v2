<template>
  <el-container class="h-full">
    <el-aside width="220px" class="aside">
      <div class="logo">EnglishLearn 后台</div>
      <el-menu :default-active="String(route.name)" router class="border-0">
        <el-menu-item index="contacts" :route="{ name: 'contacts' }">
          <el-icon><Avatar /></el-icon>
          <span>数字人管理</span>
        </el-menu-item>
        <el-menu-item index="prompts" :route="{ name: 'prompts' }">
          <el-icon><ChatLineSquare /></el-icon>
          <span>提示词管理</span>
        </el-menu-item>
        <el-menu-item index="stories" :route="{ name: 'stories' }">
          <el-icon><Notebook /></el-icon>
          <span>内容管理</span>
        </el-menu-item>
        <el-menu-item index="categories" :route="{ name: 'categories' }">
          <el-icon><Collection /></el-icon>
          <span>分类管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="text-base font-medium text-gray-700">
          {{ route.meta.title ?? '' }}
        </div>
        <el-button link type="danger" @click="onLogout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Avatar, ChatLineSquare, Collection, Notebook } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function onLogout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.aside {
  background: #fff;
  border-right: 1px solid #ebeef5;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  color: #409eff;
  border-bottom: 1px solid #ebeef5;
}
.header {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.main {
  background: #f5f7fa;
}
</style>
