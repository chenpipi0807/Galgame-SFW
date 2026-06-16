<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm px-4"
        @click.self="close"
        @keydown.escape="close"
      >
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-xl max-h-[70vh] flex flex-col overflow-hidden">
          <!-- 头部：搜尋框 -->
          <div class="flex items-center gap-2 px-4 py-3 border-b border-border flex-shrink-0">
            <span class="text-sm">🔍</span>
            <input
              ref="inputRef"
              v-model="query"
              class="flex-1 bg-transparent text-sm text-text placeholder:text-muted/50 outline-none"
              placeholder="搜尋世界書關鍵詞或內容..."
              @input="onInput"
              @keydown.escape="close"
            />
            <span class="text-[10px] text-muted/40 flex-shrink-0">ESC 關閉</span>
          </div>

          <!-- 內容區 -->
          <div class="flex-1 overflow-y-auto">
            <!-- 載入中 -->
            <div v-if="loading" class="flex items-center justify-center py-12">
              <span class="text-sm text-muted loading-dots">搜尋中</span>
            </div>

            <!-- 空輸入提示 -->
            <div v-else-if="!query.trim()" class="flex flex-col items-center justify-center py-12 text-muted/50">
              <span class="text-3xl mb-3">📖</span>
              <p class="text-sm">輸入關鍵詞搜尋世界書</p>
              <p class="text-xs mt-1">可搜尋關鍵詞標籤或條目內容</p>
            </div>

            <!-- 無結果 -->
            <div v-else-if="!results.length" class="flex flex-col items-center justify-center py-12 text-muted/50">
              <span class="text-3xl mb-3">🔍</span>
              <p class="text-sm">沒有找到匹配的世界書條目</p>
            </div>

            <!-- 搜尋結果 -->
            <div v-else class="divide-y divide-border/30">
              <div
                v-for="(item, idx) in results"
                :key="idx"
                class="px-4 py-3 hover:bg-panel/50 transition-colors"
              >
                <!-- 所屬世界書名稱 -->
                <div class="flex items-center gap-1.5 mb-1.5">
                  <span class="text-[10px] text-accent/60">📖</span>
                  <span class="text-[11px] text-accent/60 font-medium">{{ item.lorebook_title }}</span>
                </div>

                <!-- 關鍵詞標籤 -->
                <div v-if="item.keywords && item.keywords.length" class="flex flex-wrap gap-1 mb-2">
                  <span
                    v-for="kw in item.keywords"
                    :key="kw"
                    class="text-[10px] px-1.5 py-0.5 rounded-md border"
                    :class="isMatch(kw, query) ? 'border-amber-500/40 bg-amber-900/20 text-amber-300' : 'border-border/50 text-muted/70'"
                  >{{ kw }}</span>
                </div>

                <!-- 內容預覽（截取匹配片段前後文） -->
                <div class="text-xs text-text/80 leading-relaxed whitespace-pre-wrap line-clamp-4">
                  <template v-for="(seg, si) in highlightSegments(item.content, query)" :key="si">
                    <mark v-if="seg.highlight" class="bg-amber-500/25 text-amber-200 rounded-sm px-0.5">{{ seg.text }}</mark>
                    <span v-else>{{ seg.text }}</span>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部提示 -->
          <div v-if="results.length" class="px-4 py-2 border-t border-border/40 flex-shrink-0">
            <span class="text-[10px] text-muted/40">{{ results.length }} 條結果</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  plotId: { type: [Number, String], required: true },
})

const visible = ref(false)
const query = ref('')
const results = ref([])
const loading = ref(false)
const inputRef = ref(null)

let debounceTimer = null

function open() {
  visible.value = true
  query.value = ''
  results.value = []
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  visible.value = false
  query.value = ''
  results.value = []
}

function onInput() {
  clearTimeout(debounceTimer)
  const q = query.value.trim()
  if (!q) {
    results.value = []
    return
  }
  loading.value = true
  debounceTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/plots/${props.plotId}/lorebooks/search?q=${encodeURIComponent(q)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      results.value = await res.json()
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 250)
}

function isMatch(text, q) {
  if (!q || !text) return false
  return text.toLowerCase().includes(q.toLowerCase())
}

function highlightSegments(content, q) {
  if (!q || !q.trim() || !content) return [{ text: content || '', highlight: false }]
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  const segments = []
  let lastIndex = 0
  let match
  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: content.slice(lastIndex, match.index), highlight: false })
    }
    segments.push({ text: match[0], highlight: true })
    lastIndex = regex.lastIndex
    if (match[0].length === 0) regex.lastIndex++
  }
  if (lastIndex < content.length) {
    segments.push({ text: content.slice(lastIndex), highlight: false })
  }
  return segments.length ? segments : [{ text: content, highlight: false }]
}

defineExpose({ open, close })

watch(visible, (val) => {
  if (!val) {
    query.value = ''
    results.value = []
  }
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
