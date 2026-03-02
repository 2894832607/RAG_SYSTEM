<template>
  <div class="app-layout" :class="{ 'no-sidebar': !showSidebar }">
    <AppSidebar v-if="showSidebar" />
    <main class="app-main" :class="{ 'full-main': !showSidebar }">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'

const route = useRoute()
const showSidebar = computed(() => route.path !== '/login')
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-main);
}
.app-main {
  flex: 1;
  margin-left: 260px;
  min-height: 100vh;
}
.app-main.full-main {
  margin-left: 0;
}
</style>
