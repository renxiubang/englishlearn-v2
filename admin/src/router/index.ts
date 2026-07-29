import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/views/LayoutView.vue'),
      children: [
        { path: '', redirect: { name: 'contacts' } },
        {
          path: 'contacts',
          name: 'contacts',
          component: () => import('@/views/ContactsView.vue'),
          meta: { title: '数字人管理' },
        },
        {
          path: 'prompts',
          name: 'prompts',
          component: () => import('@/views/PromptsView.vue'),
          meta: { title: '提示词管理' },
        },
        {
          path: 'stories',
          name: 'stories',
          component: () => import('@/views/StoriesView.vue'),
          meta: { title: '内容管理' },
        },
        {
          path: 'categories',
          name: 'categories',
          component: () => import('@/views/CategoriesView.vue'),
          meta: { title: '分类管理' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 全局前置守卫：未登录一律去登录页
router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) return { name: 'login' }
  if (to.name === 'login' && getToken()) return { name: 'contacts' }
})

export default router
