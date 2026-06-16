<template>
  <div class="min-h-screen bg-bg">
    <!-- 全局导航栏 -->
    <nav class="fixed top-0 left-0 right-0 z-50 h-14 border-b border-border bg-bg/90 backdrop-blur-sm flex items-center px-6 gap-6">
      <RouterLink to="/" class="gradient-text font-bold text-lg tracking-wider">GalGame</RouterLink>
      <div class="flex-1" />
      <RouterLink to="/" class="text-sm text-muted hover:text-text transition-colors">返回主页</RouterLink>
      <button class="text-sm text-muted hover:text-text transition-colors" @click="showReadme = true">新手必读</button>
      <RouterLink to="/admin" class="text-sm text-muted hover:text-text transition-colors">系统设置</RouterLink>
    </nav>

    <!-- 页面内容 -->
    <main class="pt-14">
      <RouterView />
    </main>

    <!-- 新手必读悬浮窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showReadme"
          class="fixed inset-0 z-[300] flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
          @click.self="showReadme = false"
        >
          <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col overflow-hidden" style="max-height:85vh">
            <!-- 头部 -->
            <div class="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
              <span class="font-bold text-sm text-text">📖 新手必读</span>
              <button
                class="w-7 h-7 rounded-full bg-panel border border-border text-muted hover:text-text hover:border-accent/40 text-sm flex items-center justify-center transition-all"
                @click="showReadme = false"
              >✕</button>
            </div>
            <!-- 内容（可滚动） -->
            <div class="flex-1 overflow-y-auto">
              <ReadmeView />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import ReadmeView from './views/ReadmeView.vue'

const showReadme = ref(false)
</script>
