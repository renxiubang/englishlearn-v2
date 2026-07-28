<script setup lang="ts">
import { useRoute } from 'vue-router'
import NavBar from '@/components/NavBar.vue'

const route = useRoute()
</script>

<template>
  <section class="screen">
    <NavBar :title="route.meta.title ?? ''" :back="!!route.meta.hideTab" back-to="/" />
    <div class="screen-body flex flex-col items-center justify-center gap-3">
      <div class="w-16 h-16 rounded-3xl icon-tile--blue flex items-center justify-center">
        <svg class="licon" width="30" height="30" viewBox="0 0 24 24" stroke="#4A90E2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></svg>
      </div>
      <div class="text-[15px] font-bold">功能开发中</div>
      <div class="text-[12px] muted">该模块将在后续版本开放，敬请期待</div>
    </div>
  </section>
</template>
