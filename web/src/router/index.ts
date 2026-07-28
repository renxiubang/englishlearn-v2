import { createRouter, createWebHistory } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 所属底部 Tab */
    tab: 'home' | 'contacts' | 'share' | 'profile'
    /** 是否隐藏底部 TabBar */
    hideTab?: boolean
    /** 页面标题（占位页 NavBar 用） */
    title?: string
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { tab: 'home' } },
    { path: '/contacts', name: 'contacts', component: () => import('@/views/ContactsView.vue'), meta: { tab: 'contacts' } },
    { path: '/chat/:id', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { tab: 'contacts', hideTab: true } },
    { path: '/picture-story', name: 'picture-story', component: () => import('@/views/PictureStoryView.vue'), meta: { tab: 'home', hideTab: true } },
    // ---- 以下模块暂未移植，统一占位页 ----
    { path: '/share', name: 'share', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'share', title: '英语秀场' } },
    { path: '/profile', name: 'profile', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'profile', title: '我的' } },
    { path: '/story-read', name: 'story-read', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'home', hideTab: true, title: '故事跟读' } },
    { path: '/dialogue-read', name: 'dialogue-read', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'home', hideTab: true, title: '对话跟读' } },
    { path: '/listen-story', name: 'listen-story', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'home', hideTab: true, title: '听故事' } },
    { path: '/favorites', name: 'favorites', component: () => import('@/views/PlaceholderView.vue'), meta: { tab: 'home', hideTab: true, title: '我的收藏' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
