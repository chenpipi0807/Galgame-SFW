<template>
  <div class="max-w-5xl mx-auto px-6 py-10">
    <!-- 头部 -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold gradient-text">故事库</h1>
        <p class="text-muted text-sm mt-1">你的私人叙事宇宙</p>
      </div>
      <div class="flex gap-3">
        <RouterLink to="/wizard" class="btn-primary flex items-center gap-2">
          <span class="text-lg">＋</span> 新建故事
        </RouterLink>
        <button
          class="btn-ghost flex items-center gap-2 border border-amber-500/30 text-amber-300/70 hover:bg-amber-900/20 hover:text-amber-200 hover:border-amber-400/50 transition-all"
          :disabled="importingCard"
          @click="triggerImport"
        >
          <span class="text-lg">📥</span> {{ importingCard ? '导入中…' : '导入 Galgame 卡' }}
        </button>
        <input
          ref="importInput"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          class="hidden"
          @change="onImportFile"
        />
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex justify-center py-20">
      <div class="text-muted text-sm loading-dots">加载中</div>
    </div>

    <!-- 后端连接失败 -->
    <div v-else-if="loadError" class="text-center py-24">
      <p class="text-red-400 mb-2 text-sm">无法连接到后端服务</p>
      <p class="text-muted text-xs">请确认后端已启动（start-backend.bat），然后刷新页面</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="plots.length === 0" class="text-center py-24">
      <div class="text-6xl mb-4 opacity-30">✦</div>
      <p class="text-muted mb-6">还没有故事，创造你的第一个世界吧</p>
      <RouterLink to="/wizard" class="btn-primary">开始创作</RouterLink>
    </div>

    <!-- 故事列表 -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      <div
        v-for="plot in plots"
        :key="plot.id"
        :data-plot-id="plot.id"
        class="card group hover:border-accent/40 transition-all duration-200 cursor-pointer relative overflow-hidden !p-0 flex flex-col"
      >
        <!-- 缩略图 -->
        <div class="relative w-full h-32 overflow-hidden rounded-t-xl shrink-0">
          <img
            v-if="plotBgImages[plot.id]"
            :src="plotBgImages[plot.id]"
            class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
          <img v-else src="/gen_failed.png" class="w-full h-full object-cover opacity-40" />
          <!-- 渐变遮罩 -->
          <div class="absolute inset-0 bg-gradient-to-t from-surface via-surface/20 to-transparent"></div>
        </div>

        <!-- 内容区 -->
        <div class="flex flex-col flex-1 px-4 pt-3 pb-4">

        <!-- 状态标签 -->
        <div class="flex items-start justify-between mb-3">
          <span
            class="text-xs px-2 py-0.5 rounded-full border"
            :class="statusClass(plot.status)"
          >{{ statusLabel(plot.status) }}</span>
          <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <RouterLink
              :to="`/edit/${plot.id}`"
              class="p-1.5 rounded text-muted hover:text-text hover:bg-panel transition-colors"
              title="编辑"
              @click.stop
            >✎</RouterLink>
            <button
              class="p-1.5 rounded text-muted hover:text-red-400 hover:bg-panel transition-colors"
              title="删除"
              @click.stop="confirmDelete(plot)"
            >✕</button>
          </div>
        </div>

        <!-- 标题 -->
        <div class="mb-1">
          <div v-if="editingTitle === plot.id" class="flex gap-1 items-center -mx-1">
            <input
              ref="titleInputRef"
              v-model="editTitleValue"
              class="input text-sm font-bold flex-1 min-w-0 py-0.5 px-1"
              maxlength="60"
              @keydown.enter="saveTitle(plot)"
              @keydown.escape="cancelEditTitle"
              @click.stop
            />
            <button
              class="p-1 rounded text-green-400 hover:bg-green-900/30 transition-colors flex-shrink-0"
              title="确认"
              @click.stop="saveTitle(plot)"
            >✓</button>
            <button
              class="p-1 rounded text-muted hover:text-red-400 hover:bg-panel transition-colors flex-shrink-0"
              title="取消"
              @click.stop="cancelEditTitle"
            >✕</button>
          </div>
          <h2
            v-else
            class="font-bold text-base text-text leading-snug cursor-pointer hover:text-accent transition-colors"
            title="点击修改标题"
            @click.stop="startEditTitle(plot)"
          >{{ plot.title || '未命名故事' }}</h2>
        </div>
        <p class="text-muted text-xs line-clamp-2 mb-3">{{ plot.concept }}</p>

        <!-- Vibe 标签 -->
        <div class="flex flex-wrap gap-1 mb-4">
          <span
            v-for="v in parseVibe(plot.vibe)"
            :key="v"
            class="text-xs px-2 py-0.5 rounded-full bg-panel text-muted border border-border"
          >{{ v }}</span>
        </div>

        <!-- 操作按钮 -->
        <div class="flex gap-2 mt-auto">
          <button
            v-if="plot.status === 'published' || plot.status === 'ready'"
            class="btn-primary flex-1 text-sm py-1.5"
            @click="startReading(plot)"
          >马上穿越</button>
          <button
            v-else
            class="btn-ghost flex-1 text-sm py-1.5"
            @click="continueWizard(plot)"
          >捏个世界</button>
        </div>

        </div><!-- end 内容区 -->
      </div>
    </div>
  </div>

  <!-- 删除确认对话框 -->
  <Teleport to="body">
    <div v-if="deletingPlot" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center" @click.self="deletingPlot = null">
      <div class="card max-w-sm w-full mx-4 animate-slide-up">
        <h3 class="font-bold mb-2">确认删除</h3>
        <p class="text-muted text-sm mb-5">删除《{{ deletingPlot.title }}》？此操作不可撤销，相关会话和角色也会一并删除。</p>
        <div class="flex gap-3">
          <button class="btn-ghost flex-1" @click="deletingPlot = null">取消</button>
          <button class="btn-danger flex-1" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePlotStore } from '../stores/plotStore.js'

const router = useRouter()
const store = usePlotStore()
const { plots } = storeToRefs(store)
const { fetchPlots, fetchSessions, createSession, deletePlot, updatePlot } = store
const editingTitle = ref(null)
const editTitleValue = ref('')

const loading = ref(true)
const loadError = ref(false)
const deletingPlot = ref(null)
const plotBgImages = ref({})
const importInput = ref(null)
const importingCard = ref(false)

onMounted(async () => {
  try {
    await fetchPlots()
    // 并行拉取各故事的会话背景图
    await Promise.all(plots.value.map(async (p) => {
      try {
        const res = await fetch(`/api/sessions?plot_id=${p.id}`)
        if (!res.ok) return
        const sessions = await res.json()
        const url = sessions[0]?.bg_image_url
        if (url) plotBgImages.value[p.id] = url
      } catch { /* ignore */ }
    }))
  } catch { loadError.value = true } finally { loading.value = false }
})

const parseVibe = (v) => {
  try { return JSON.parse(v || '[]') } catch { return [] }
}

const statusLabel = (s) => ({ draft: '草稿', ready: '待发布', published: '已发布' }[s] || s)
const statusClass = (s) => ({
  draft: 'text-muted border-border',
  ready: 'text-yellow-400 border-yellow-700/50',
  published: 'text-green-400 border-green-700/50',
}[s] || 'text-muted border-border')

async function startReading(plot) {
  const sessions = await fetchSessions(plot.id)
  if (sessions.length > 0) {
    router.push(`/read/${sessions[0].id}`)
  } else {
    const { session_id } = await createSession(plot.id)
    router.push(`/read/${session_id}`)
  }
}

function continueWizard(plot) {
  router.push({ path: '/wizard', query: { plot_id: plot.id } })
}

function confirmDelete(plot) { deletingPlot.value = plot }
async function doDelete() {
  await deletePlot(deletingPlot.value.id)
  deletingPlot.value = null
}

function startEditTitle(plot) {
  editingTitle.value = plot.id
  editTitleValue.value = plot.title || ''
  // 下一帧自动聚焦输入框
  requestAnimationFrame(() => {
    const el = document.querySelector(`[data-plot-id="${plot.id}"] input`)
    el?.focus()
    el?.select()
  })
}

function cancelEditTitle() {
  editingTitle.value = null
}

async function saveTitle(plot) {
  const newTitle = editTitleValue.value.trim()
  if (!newTitle) {
    editingTitle.value = null
    return
  }
  if (newTitle !== plot.title) {
    try {
      await updatePlot(plot.id, { title: newTitle })
      // 直接更新当前 plot 对象，确保 UI 立即刷新
      plot.title = newTitle
    } catch (e) {
      console.error('[saveTitle] 更新失败:', e)
    }
  }
  editingTitle.value = null
}

function triggerImport() {
  importInput.value?.click()
}

async function onImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  importingCard.value = true

  try {
    const b64 = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })

    const res = await fetch('/api/galgame-card/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: b64 }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `导入失败 (${res.status})`)
    }
    const { session_id } = await res.json()

    // 刷新列表并跳转
    await fetchPlots()
    router.push(`/read/${session_id}`)
  } catch (e) {
    alert('导入 Galgame 卡失败：' + e.message)
  } finally {
    importingCard.value = false
  }
}
</script>
