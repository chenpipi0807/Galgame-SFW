<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <div class="flex items-center gap-3 mb-6">
      <RouterLink to="/" class="text-muted hover:text-text text-sm">← 返回</RouterLink>
      <h1 class="font-bold text-lg">编辑故事</h1>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 bg-panel rounded-lg p-1 w-fit">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab-btn"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >{{ t.label }}</button>
    </div>

    <!-- Tab: 故事设定 -->
    <div v-if="activeTab === 'plot'" class="space-y-4">
      <div>
        <label class="label">故事标题</label>
        <input v-model="form.title" class="input" />
      </div>
      <div>
        <label class="label">故事概念</label>
        <textarea v-model="form.concept" class="textarea min-h-24" />
      </div>
      <div>
        <label class="label">开场</label>
        <textarea v-model="form.opening" class="textarea min-h-32" />
      </div>
      <div>
        <label class="label">背景设定</label>
        <textarea v-model="form.backstory" class="textarea min-h-32" />
      </div>
      <div>
        <label class="label">叙事视角</label>
        <select v-model="plotPov" class="input">
          <option value="3rd">第三人称</option>
          <option value="2nd">第二人称</option>
          <option value="1st">第一人称</option>
        </select>
      </div>
      <div class="flex gap-3">
        <button class="btn-primary" :disabled="saving" @click="savePlot">
          {{ saving ? '保存中…' : '保存设定' }}
        </button>
        <button v-if="plot?.status !== 'published'" class="btn-ghost" @click="publishPlot">发布故事</button>
      </div>
    </div>

    <!-- Tab: 角色 -->
    <div v-if="activeTab === 'characters'" class="space-y-4">
      <div v-if="loadingChars" class="text-muted text-sm loading-dots py-8 text-center">加载中</div>
      <template v-else>
        <div
          v-for="char in characters"
          :key="char.id"
          class="card space-y-3"
        >
          <div class="flex items-start gap-4">
            <!-- 头像 + 参考图 -->
            <div class="flex-shrink-0 text-center space-y-1">
              <!-- 头像预览 -->
              <div class="w-20 h-20 rounded-lg overflow-hidden bg-panel border border-border">
                <img v-if="char.avatar_url" :src="char.avatar_url" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full flex items-center justify-center text-muted text-3xl">
                  {{ char.name?.[0] || '?' }}
                </div>
              </div>
              <!-- 参考图上传 -->
              <label class="block w-20 h-10 rounded-lg border border-dashed border-border cursor-pointer overflow-hidden hover:border-accent/50 transition-colors relative">
                <img v-if="char.reference_image" :src="char.reference_image" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full flex flex-col items-center justify-center text-muted text-xs">
                  <span>↑参考图</span>
                </div>
                <input type="file" accept="image/*" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer" @change="onRefImageUpload($event, char)" />
              </label>
              <button
                class="text-xs text-muted hover:text-accent transition-colors block w-full"
                :disabled="regenLoading[char.id]"
                @click="regenAvatar(char)"
              >{{ regenLoading[char.id] ? '生成中…' : '重新生成' }}</button>
            </div>
            <!-- 字段 -->
            <div class="flex-1 space-y-2">
              <input v-model="char.name" class="input font-semibold" placeholder="角色名" />
              <textarea v-model="char.description" class="textarea text-sm min-h-16" placeholder="外貌描述" />
              <textarea v-model="char.personality" class="textarea text-sm min-h-12" placeholder="性格特征" />
              <!-- 生图模式 + 风格选择 -->
              <div>
                <div class="flex items-center gap-2 mb-1.5">
                  <span v-if="char.reference_image" class="text-xs px-2 py-0.5 rounded-full bg-green-900/30 text-green-400 border border-green-700/40">参考生图</span>
                  <span v-else class="text-xs px-2 py-0.5 rounded-full bg-panel text-muted border border-border">文生图</span>
                  <span class="text-xs text-muted">生图描述</span>
                </div>
                <div v-if="!char.reference_image" class="flex flex-wrap gap-1 mb-1.5">
                  <button
                    v-for="s in styleOptions"
                    :key="s.key"
                    class="text-xs px-2 py-0.5 rounded-full border transition-all"
                    :class="char.image_style === s.key
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border text-muted hover:border-accent/40'"
                    @click="setCharStyle(char, s.key)"
                  >{{ s.label }}</button>
                </div>
                <textarea v-model="char.image_prompt" class="textarea text-sm min-h-16" placeholder="角色外貌描述，用于生成头像…" />
              </div>
            </div>
          </div>
          <div class="flex justify-between">
            <button class="btn-ghost text-xs" @click="saveCharacter(char)">保存角色</button>
            <button class="btn-danger text-xs" @click="deleteChar(char)">删除角色</button>
          </div>
        </div>
        <!-- 导入酒馆角色卡 -->
        <label class="btn-ghost w-full cursor-pointer text-center relative">
          <span v-if="!importingTavern">导入酒馆角色卡 (.png)</span>
          <span v-else class="loading-dots">解析中</span>
          <input
            v-if="!importingTavern"
            type="file"
            accept="image/png"
            class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
            @change="onTavernCardUpload"
          />
        </label>
        <!-- 导入预览 -->
        <div v-if="tavernPreview" class="card space-y-3 border border-accent/30">
          <div class="flex items-start gap-4">
            <img :src="tavernPreview.image_url" class="w-20 h-20 object-cover rounded-lg flex-shrink-0" />
            <div class="flex-1 space-y-1.5">
              <p class="font-semibold text-text">{{ tavernPreview.name }}</p>
              <p class="text-xs text-muted line-clamp-3">{{ tavernPreview.description || '（无描述）' }}</p>
              <p v-if="tavernPreview.personality" class="text-xs text-muted/70">性格：{{ tavernPreview.personality.slice(0, 80) }}</p>
              <div class="flex flex-wrap gap-1.5 pt-0.5">
                <span v-if="tavernPreview.first_mes" class="text-[11px] px-2 py-0.5 rounded-full bg-green-900/20 text-green-400/80 border border-green-700/30">✓ 开场白</span>
                <span v-if="tavernPreview.alternate_greetings?.length" class="text-[11px] px-2 py-0.5 rounded-full bg-blue-900/20 text-blue-400/80 border border-blue-700/30">+{{ tavernPreview.alternate_greetings.length }} 备用开场</span>
                <span v-if="tavernPreview.creator_notes" class="text-[11px] px-2 py-0.5 rounded-full bg-panel text-muted border border-border">作者备注</span>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <button class="btn-primary text-xs flex-1" :disabled="importingTavern" @click="confirmTavernImport">确认导入</button>
            <button class="btn-ghost text-xs" @click="tavernPreview = null">取消</button>
          </div>
        </div>
        <button class="btn-ghost w-full" @click="addChar">＋ 添加角色</button>
      </template>
    </div>

    <!-- Tab: Lorebook -->
    <div v-if="activeTab === 'lorebook'" class="space-y-4">
      <!-- 已挂载的 Lorebook -->
      <div>
        <h3 class="text-sm font-medium mb-3 text-muted">已挂载到本故事</h3>
        <div v-if="attachedBooks.length === 0" class="text-muted text-xs py-3">
          未挂载任何世界书
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="lb in attachedBooks"
            :key="lb.id"
            class="flex items-center gap-3 bg-panel rounded-lg px-3 py-2"
          >
            <span class="flex-1 text-sm">{{ lb.title }}</span>
            <button class="text-xs text-muted hover:text-red-400" @click="detachBook(lb.id)">移除</button>
          </div>
        </div>
        <button class="btn-ghost text-xs mt-2" @click="showAttach = !showAttach">
          {{ showAttach ? '收起' : '+ 挂载世界书' }}
        </button>
        <div v-if="showAttach" class="mt-2 space-y-1">
          <div
            v-for="lb in availableBooks"
            :key="lb.id"
            class="flex items-center gap-3 bg-panel rounded-lg px-3 py-2 cursor-pointer hover:bg-surface"
            @click="attachBook(lb.id)"
          >
            <span class="flex-1 text-sm">{{ lb.title }}</span>
            <span class="text-xs text-accent">挂载</span>
          </div>
        </div>
      </div>

      <div class="border-t border-border pt-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-medium text-muted">所有世界书</h3>
          <button class="btn-ghost text-xs" @click="createLorebook">＋ 新建世界书</button>
        </div>
        <div class="space-y-4">
          <div v-for="lb in lorebooks" :key="lb.id" class="card">
            <div class="flex items-center gap-2 mb-3">
              <input v-model="lb.title" class="input flex-1 py-1 text-sm font-medium" placeholder="世界书标题" />
              <button class="text-xs text-muted hover:text-red-400" @click="deleteLorebook(lb.id)">删除</button>
            </div>
            <!-- 条目 -->
            <div class="space-y-2 mb-2">
              <div
                v-for="(entry, ei) in lb.entries"
                :key="ei"
                class="bg-panel rounded-lg p-3 space-y-2"
              >
                <div class="flex items-center gap-2">
                  <input
                    v-model="entry.keywordInput"
                    class="input flex-1 text-xs py-1"
                    placeholder="关键词（逗号分隔，如：Alice,爱丽丝）"
                    @blur="parseKeywords(entry)"
                  />
                  <button class="text-xs text-muted hover:text-red-400" @click="lb.entries.splice(ei, 1)">✕</button>
                </div>
                <textarea
                  v-model="entry.content"
                  class="textarea text-xs min-h-16"
                  placeholder="触发关键词时注入的内容…"
                />
              </div>
            </div>
            <div class="flex gap-2">
              <button class="btn-ghost text-xs" @click="lb.entries.push({ keywords: [], keywordInput: '', content: '' })">
                ＋ 添加条目
              </button>
              <button class="btn-primary text-xs px-3 py-1.5" @click="saveLorebook(lb)">保存</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 保存成功提示 -->
    <div v-if="saveMsg" class="fixed bottom-6 right-6 bg-surface border border-green-600/40 text-green-400 text-sm px-4 py-2 rounded-lg animate-slide-up">
      {{ saveMsg }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const plotId = Number(route.params.plotId)

const styleOptions = [
  { key: 'realistic',  label: '写实' },
  { key: 'manhwa',     label: '韩漫' },
  { key: 'anime',      label: '日漫' },
  { key: 'otome3d',    label: '乙女3D' },
  { key: 'donghua3d',  label: '国漫3D' },
  { key: 'donghua2d',  label: '国漫2D' },
  { key: 'comics',     label: '美漫' },
  { key: 'disney3d',   label: '3D卡通' },
  { key: 'manga_bw',   label: '黑白漫画' },
]

function setCharStyle(char, key) {
  char.image_style = char.image_style === key ? '' : key
  apiFetch(`/characters/${char.id}`, {
    method: 'PUT',
    body: JSON.stringify({ image_style: char.image_style }),
  })
}

const activeTab = ref('plot')
const tabs = [
  { key: 'plot', label: '故事设定' },
  { key: 'characters', label: '角色' },
  { key: 'lorebook', label: '世界书' },
]

const plot = ref(null)
const form = ref({ title: '', concept: '', opening: '', backstory: '' })
const plotPov = ref('3rd')
const saving = ref(false)
const characters = ref([])
const loadingChars = ref(false)
const regenLoading = ref({})
const importingTavern = ref(false)
const tavernPreview = ref(null)
const lorebooks = ref([])
const attachedBooks = ref([])
const showAttach = ref(false)
const saveMsg = ref('')

const availableBooks = computed(() =>
  lorebooks.value.filter(lb => !attachedBooks.value.find(a => a.id === lb.id))
)

async function apiFetch(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

function showSave(msg = '已保存') {
  saveMsg.value = msg
  setTimeout(() => { saveMsg.value = '' }, 2500)
}

async function loadAll() {
  const p = await apiFetch(`/plots/${plotId}`)
  plot.value = p
  characters.value = p.characters || []
  let style = {}
  try { style = JSON.parse(p.style_settings || '{}') } catch {}
  plotPov.value = style.pov || '3rd'
  form.value = { title: p.title, concept: p.concept, opening: p.opening, backstory: p.backstory }

  const [lbs, attached] = await Promise.all([
    apiFetch('/lorebooks'),
    apiFetch(`/plots/${plotId}/lorebooks`),
  ])
  lorebooks.value = lbs.map(lb => ({ ...lb, entries: [] }))
  attachedBooks.value = attached
  // 加载每本 lorebook 的 entries
  await Promise.all(lorebooks.value.map(async (lb) => {
    const full = await apiFetch(`/lorebooks/${lb.id}`)
    lb.entries = full.entries.map(e => ({
      ...e,
      keywordInput: e.keywords.join(','),
    }))
  }))
}

async function savePlot() {
  saving.value = true
  try {
    const style = { pov: plotPov.value }
    await apiFetch(`/plots/${plotId}`, {
      method: 'PUT',
      body: JSON.stringify({ ...form.value, style_settings: style }),
    })
    showSave()
  } finally { saving.value = false }
}

async function publishPlot() {
  await apiFetch(`/plots/${plotId}/publish`, { method: 'PUT' })
  showSave('已发布')
}

async function saveCharacter(char) {
  await apiFetch(`/characters/${char.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: char.name,
      description: char.description,
      personality: char.personality,
      image_prompt: char.image_prompt,
    }),
  })
  showSave()
}

async function deleteChar(char) {
  await apiFetch(`/characters/${char.id}`, { method: 'DELETE' })
  characters.value = characters.value.filter(c => c.id !== char.id)
}

async function addChar() {
  const data = await apiFetch('/characters', {
    method: 'POST',
    body: JSON.stringify({ plot_id: plotId, name: '新角色', description: '', personality: '', image_prompt: '' }),
  }).catch(() => null)
  if (data) await loadAll()
}

async function onTavernCardUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  importingTavern.value = true
  tavernPreview.value = null
  const reader = new FileReader()
  reader.onload = async () => {
    try {
      const res = await fetch('/api/characters/parse-tavern-card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: reader.result }),
      })
      const data = await res.json()
      if (!data.is_tavern_card) {
        alert('这张图片不包含酒馆角色卡数据')
        return
      }
      tavernPreview.value = data
    } catch (e) {
      alert('解析失败：' + e.message)
    } finally {
      importingTavern.value = false
    }
  }
  reader.readAsDataURL(file)
}

async function confirmTavernImport() {
  if (!tavernPreview.value) return
  importingTavern.value = true
  try {
    const p = tavernPreview.value
    // 创建角色，同时设置头像（卡图）
    await apiFetch('/characters', {
      method: 'POST',
      body: JSON.stringify({
        plot_id: plotId,
        name: p.name,
        description: p.description,
        personality: p.personality,
        first_mes: p.first_mes || '',
        image_prompt: '',
        reference_image: p.image_url,
        avatar_url: p.image_url,
        image_url: p.image_url,
      }),
    })
    tavernPreview.value = null
    showSave(`已导入角色：${p.name}`)
    await loadAll()
  } catch (e) {
    alert('导入失败：' + e.message)
  } finally {
    importingTavern.value = false
  }
}

async function onRefImageUpload(event, char) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  const reader = new FileReader()
  reader.onload = async () => {
    const dataUri = reader.result
    // 若是 PNG，先尝试解析酒馆角色卡
    if (file.type === 'image/png' || file.name.endsWith('.png')) {
      try {
        const res = await fetch('/api/characters/parse-tavern-card', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: dataUri }),
        })
        const parsed = await res.json()
        if (parsed.is_tavern_card) {
          // 用卡中数据覆盖当前角色字段，图片作为参考图和头像
          if (parsed.name && !char.name) char.name = parsed.name
          if (parsed.description && !char.description) char.description = parsed.description
          if (parsed.personality && !char.personality) char.personality = parsed.personality
          if (parsed.first_mes && !char.first_mes) char.first_mes = parsed.first_mes
          char.reference_image = parsed.image_url
          char.avatar_url = parsed.image_url
          await apiFetch(`/characters/${char.id}`, {
            method: 'PUT',
            body: JSON.stringify({
              name: char.name,
              description: char.description,
              personality: char.personality,
              reference_image: char.reference_image,
              avatar_url: parsed.image_url,
            }),
          })
          showSave(`已从酒馆卡导入参考图及信息：${parsed.name}`)
          return
        }
      } catch { /* 解析失败则正常上传 */ }
    }
    // 普通图片上传
    try {
      const res = await fetch('/api/uploads/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: dataUri }),
      })
      const data = await res.json()
      char.reference_image = data.url
      await apiFetch(`/characters/${char.id}`, {
        method: 'PUT',
        body: JSON.stringify({ reference_image: char.reference_image }),
      })
    } catch {
      char.reference_image = dataUri
    }
  }
  reader.readAsDataURL(file)
}

async function regenAvatar(char) {
  regenLoading.value[char.id] = true
  try {
    const { task_id } = await apiFetch(`/characters/${char.id}/regenerate-avatar`, { method: 'POST' })
    const poll = setInterval(async () => {
      const task = await apiFetch(`/tasks/${task_id}`)
      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(poll)
        regenLoading.value[char.id] = false
        if (task.status === 'completed') await loadAll()
      }
    }, 2000)
  } catch { regenLoading.value[char.id] = false }
}

function parseKeywords(entry) {
  entry.keywords = entry.keywordInput.split(',').map(k => k.trim()).filter(Boolean)
}

async function createLorebook() {
  const lb = await apiFetch('/lorebooks', {
    method: 'POST',
    body: JSON.stringify({ title: '新世界书', description: '', entries: [] }),
  })
  lorebooks.value.push({ id: lb.id, title: '新世界书', entries: [] })
}

async function saveLorebook(lb) {
  lb.entries.forEach(e => parseKeywords(e))
  await apiFetch(`/lorebooks/${lb.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      title: lb.title,
      entries: lb.entries.map(e => ({ keywords: e.keywords, content: e.content })),
    }),
  })
  showSave()
}

async function deleteLorebook(lbId) {
  await apiFetch(`/lorebooks/${lbId}`, { method: 'DELETE' })
  lorebooks.value = lorebooks.value.filter(lb => lb.id !== lbId)
  attachedBooks.value = attachedBooks.value.filter(lb => lb.id !== lbId)
}

async function attachBook(lbId) {
  await apiFetch(`/plots/${plotId}/lorebooks`, {
    method: 'POST',
    body: JSON.stringify({ lorebook_id: lbId }),
  })
  const lb = lorebooks.value.find(l => l.id === lbId)
  if (lb) attachedBooks.value.push(lb)
  showAttach.value = false
}

async function detachBook(lbId) {
  await apiFetch(`/plots/${plotId}/lorebooks/${lbId}`, { method: 'DELETE' })
  attachedBooks.value = attachedBooks.value.filter(lb => lb.id !== lbId)
}

// 需要一个 POST /api/characters 端点，先在 characters API 中补充
onMounted(loadAll)
</script>
