<script setup lang="ts">
import { useRoute } from 'vue-router'
import TabBar from '@/components/TabBar.vue'
import AppToast from '@/components/AppToast.vue'
import TalkHint from '@/components/TalkHint.vue'

const route = useRoute()
</script>

<template>
  <div class="app-frame">
    <RouterView />
    <TabBar v-if="!route.meta.hideTab" />
    <TalkHint />
    <AppToast />
  </div>
</template>
