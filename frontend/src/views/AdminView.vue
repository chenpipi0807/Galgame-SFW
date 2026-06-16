<template>
  <div class="max-w-3xl mx-auto px-6 py-8">
    <div class="flex items-center gap-3 mb-6">
      <RouterLink to="/" class="text-muted hover:text-text text-sm">← 返回</RouterLink>
      <h1 class="font-bold text-lg">后台设置</h1>
    </div>

    <!-- 首次运行引导横幅 -->
    <div v-if="isSetup" class="mb-6 rounded-xl border border-accent/30 bg-accent/10 px-4 py-3">
      <div class="text-sm font-semibold text-accent mb-1">👋 欢迎使用 GalGame —— 已内置免费 Agnes，直接就能玩</div>
      <p class="text-xs text-text/70 leading-relaxed">
        默认已配置免费的 Agnes 连接（LLM + 生图都能用），可直接返回首页开玩。若想换用 DeepSeek / Gemini 等自己的模型，在下方「API 配置」添加连接即可。所有配置仅保存在本机，不会上传。
      </p>
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

    <!-- API 配置（连接列表） -->
    <div v-if="activeTab === 'providers'" class="space-y-6">
      <p class="text-xs text-muted/80">
        每个「连接」= 一个 API 来源（名字 + 地址 + Key + 模型）。Agnes 为免费内置连接、开箱即用；你也可以添加任意 OpenAI 兼容 / Gemini 代理，自行命名、测试、启用。
      </p>

      <!-- 叙事模型 (LLM) -->
      <div class="card">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-medium">🎭 叙事模型（LLM）</h3>
          <button class="btn-ghost text-xs" @click="openAdd('llm')">＋ 添加连接</button>
        </div>
        <div class="space-y-3">
          <div
            v-for="p in llmProviders"
            :key="p.id"
            class="provider-block"
            :class="{ active: p.id === activeLlm }"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0">
                <span class="font-medium">{{ p.label }}</span>
                <span v-if="p.builtin" class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent align-middle">免费内置</span>
                <div class="text-xs text-muted truncate mt-0.5">
                  {{ p.model || '—' }}
                  <span v-if="!p.builtin && !p.has_key" class="text-amber-400 ml-1">· 未填 Key</span>
                </div>
              </div>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <button class="toggle-btn" :class="p.id === activeLlm ? 'enabled' : 'disabled'" @click="activate(p)">{{ p.id === activeLlm ? '使用中' : '启用' }}</button>
                <button class="icon-btn" :disabled="testingId === p.id" @click="testConn(p)">{{ testingId === p.id ? '测试中' : '测试' }}</button>
                <button v-if="!p.builtin" class="icon-btn" @click="openEdit(p)">编辑</button>
                <button v-if="!p.builtin" class="icon-btn !text-red-400 hover:!border-red-400/50" @click="removeConn(p)">删除</button>
              </div>
            </div>
            <div v-if="testMsg[p.id]" :class="testOk[p.id] ? 'text-green-400' : 'text-red-400'" class="text-xs mt-2">{{ testMsg[p.id] }}</div>
          </div>
        </div>
      </div>

      <!-- 生图模型 (Image) -->
      <div class="card">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-medium">🎨 生图模型</h3>
          <button class="btn-ghost text-xs" @click="openAdd('image')">＋ 添加连接</button>
        </div>
        <div class="space-y-3">
          <div
            v-for="p in imgProviders"
            :key="p.id"
            class="provider-block"
            :class="{ active: p.id === activeImage }"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0">
                <span class="font-medium">{{ p.label }}</span>
                <span v-if="p.builtin" class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent align-middle">免费内置</span>
                <span class="ml-2 text-[10px] text-muted/60">{{ imgTypeLabel(p.api_type) }}</span>
                <div class="text-xs text-muted truncate mt-0.5">
                  {{ p.model || '—' }}
                  <span v-if="!p.builtin && !p.has_key" class="text-amber-400 ml-1">· 未填 Key</span>
                </div>
              </div>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <button class="toggle-btn" :class="p.id === activeImage ? 'enabled' : 'disabled'" @click="activate(p)">{{ p.id === activeImage ? '使用中' : '启用' }}</button>
                <button class="icon-btn" :disabled="testingId === p.id" @click="testConn(p)">{{ testingId === p.id ? '测试中' : '测试' }}</button>
                <button v-if="!p.builtin" class="icon-btn" @click="openEdit(p)">编辑</button>
                <button v-if="!p.builtin" class="icon-btn !text-red-400 hover:!border-red-400/50" @click="removeConn(p)">删除</button>
              </div>
            </div>
            <div v-if="testMsg[p.id]" :class="testOk[p.id] ? 'text-green-400' : 'text-red-400'" class="text-xs mt-2">{{ testMsg[p.id] }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 提示词编辑器 -->
    <div v-if="activeTab === 'prompts'" class="space-y-4">
      <!-- 模式选择 -->
      <div class="flex items-center gap-2">
        <span class="text-sm text-muted">模式：</span>
        <button
          v-for="m in visibleModes"
          :key="m"
          class="tab-btn text-xs"
          :class="{ active: promptMode === m }"
          @click="switchPromptMode(m)"
        >经典</button>
      </div>
      <div class="flex gap-1 flex-wrap">
        <button
          v-for="name in promptNames"
          :key="name"
          class="tab-btn text-xs"
          :class="{ active: activePrompt === name }"
          @click="loadPrompt(name)"
        >{{ promptLabel(name) }}</button>
      </div>
      <div v-if="promptLoading" class="text-muted text-sm loading-dots py-8 text-center">加载中</div>
      <div v-else-if="activePrompt" class="space-y-3">
        <label class="label">{{ promptMode }}/{{ activePrompt }}.md</label>
        <textarea v-model="promptContent" class="textarea min-h-[400px] font-mono text-sm" />
        <button class="btn-primary" :disabled="savingPrompt" @click="savePrompt">
          {{ savingPrompt ? '保存中…' : '保存提示词' }}
        </button>
        <div v-if="promptMsg" :class="promptError ? 'text-red-400' : 'text-green-400'" class="text-sm">{{ promptMsg }}</div>
      </div>
      <div v-else class="text-muted text-sm py-8 text-center">点击上方标签选择提示词</div>
    </div>

    <!-- 任务监控 -->
    <div v-if="activeTab === 'tasks'" class="space-y-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-muted text-sm">最近后台任务</span>
        <button class="btn-ghost text-xs" @click="loadTasks">刷新</button>
      </div>
      <div v-if="tasks.length === 0" class="text-muted text-sm py-8 text-center">暂无任务</div>
      <div v-for="task in tasks" :key="task.id" class="card text-sm">
        <div class="flex items-center justify-between mb-1">
          <span class="font-mono text-xs text-muted">{{ task.id.slice(0, 16) }}…</span>
          <span class="text-xs px-2 py-0.5 rounded-full border"
            :class="{
              'text-green-400 border-green-700/50': task.status === 'completed',
              'text-red-400 border-red-700/50': task.status === 'failed',
              'text-yellow-400 border-yellow-700/50': task.status === 'running',
              'text-muted border-border': task.status === 'pending',
            }"
          >{{ task.status }}</span>
        </div>
        <div class="text-muted text-xs">类型：{{ task.type }} | 时间：{{ task.created_at }}</div>
        <div v-if="task.error" class="text-red-400 text-xs mt-1">错误：{{ task.error }}</div>
        <div v-if="task.status === 'failed'" class="mt-2">
          <button class="text-xs text-accent hover:underline" @click="retryTask(task.id)">重试</button>
        </div>
      </div>
    </div>

    <!-- 添加 / 编辑连接弹窗 -->
    <Transition name="fade">
      <div
        v-if="showForm"
        class="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
        @click.self="showForm = false"
      >
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
          <div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
            <span class="font-semibold text-sm">{{ formMode === 'add' ? '添加连接' : '编辑连接' }}（{{ form.kind === 'llm' ? '叙事模型' : '生图模型' }}）</span>
            <button class="text-muted hover:text-text text-xl leading-none" @click="showForm = false">×</button>
          </div>
          <div class="px-5 py-4 space-y-3">
            <div>
              <label class="label">名字</label>
              <input v-model="form.label" class="input w-full text-sm" placeholder="例如：我的 DeepSeek / 某代理商" />
            </div>
            <div v-if="form.kind === 'image'">
              <label class="label">类型</label>
              <select v-model="form.api_type" class="input w-full text-sm">
                <option value="openai-image">OpenAI 兼容生图（/images，覆盖 gpt-image/dall-e/多数代理）</option>
                <option value="gemini">Gemini（generateContent）</option>
              </select>
            </div>
            <div>
              <label class="label">Base URL</label>
              <input v-model="form.base_url" class="input w-full text-sm font-mono" placeholder="https://…/v1" />
            </div>
            <div>
              <label class="label">API Key{{ formMode === 'edit' ? '（留空保持原值）' : '' }}</label>
              <input v-model="form.api_key" type="password" class="input w-full text-sm font-mono" :placeholder="formMode === 'edit' ? '留空则不修改' : 'sk-…'" />
            </div>
            <div>
              <label class="label">模型</label>
              <input v-model="form.model" class="input w-full text-sm font-mono" :placeholder="form.kind === 'llm' ? 'deepseek-v4-flash' : 'gpt-image-2 / gemini-3.1-flash-image-preview'" />
            </div>
            <div v-if="formMsg" :class="formOk ? 'text-green-400' : 'text-red-400'" class="text-xs">{{ formMsg }}</div>
          </div>
          <div class="px-5 py-4 border-t border-border flex items-center justify-between">
            <button class="btn-ghost text-xs" @click="testForm">连接测试</button>
            <div class="flex gap-2">
              <button class="btn-ghost text-xs" @click="showForm = false">取消</button>
              <button class="btn-primary text-xs" :disabled="savingForm" @click="saveForm">{{ savingForm ? '保存中…' : '保存' }}</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
// 首次运行引导（router 带 ?setup=1）：默认进入「API 配置」标签
const isSetup = ref(route.query.setup === '1')
const activeTab = ref('providers')
const tabs = [
  { key: 'providers', label: 'API 配置' },
  { key: 'prompts',   label: '提示词编辑' },
  { key: 'tasks',     label: '任务监控' },
]

// ── Provider 连接列表 ─────────────────────────────────────────────────────────
const providersList = ref([])
const activeLlm = ref('')
const activeImage = ref('')
const testingId = ref('')
const testMsg = reactive({})
const testOk = reactive({})

const llmProviders = computed(() => providersList.value.filter(p => p.kind === 'llm'))
const imgProviders = computed(() => providersList.value.filter(p => p.kind === 'image'))

function imgTypeLabel(t) {
  return t === 'gemini' ? 'Gemini' : t === 'agnes-image' ? 'Agnes' : 'OpenAI 兼容'
}

// 添加 / 编辑弹窗
const showForm = ref(false)
const formMode = ref('add')   // 'add' | 'edit'
const form = reactive({ id: '', kind: 'llm', label: '', api_type: 'openai', base_url: '', api_key: '', model: '' })
const savingForm = ref(false)
const formMsg = ref('')
const formOk = ref(false)

// ── 提示词 ────────────────────────────────────────────────────────────────────
// 全年龄向：仅经典模式
const promptMode = ref('classic')
const availableModes = ref(['classic'])
const visibleModes = computed(() => availableModes.value)
const promptNames = ref([])
const activePrompt = ref('')
const promptContent = ref('')
const promptLoading = ref(false)
const savingPrompt = ref(false)
const promptMsg = ref('')
const promptError = ref(false)

const _promptLabels = {
  auto_advance: '自动推进',
  character_gen: '角色生成',
  character_autofill: '角色补全',
  lorebook_inj: '世界书注入',
  memory_mgr: '记忆管理',
  narrator: '叙述者',
  phase_manager: '阶段管理',
  plot_creator: '剧情创建',
  snapshot: '实况生成',
  suggester: '猜你喜欢',
}
function promptLabel(name) { return _promptLabels[name] || name }

const tasks = ref([])

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

// ── Provider 连接管理 ─────────────────────────────────────────────────────────
async function loadProviders() {
  const data = await apiFetch('/admin/providers').catch(() => null)
  if (data) {
    providersList.value = data.providers || []
    activeLlm.value = data.active_llm
    activeImage.value = data.active_image
  }
}

function openAdd(kind) {
  formMode.value = 'add'
  Object.assign(form, {
    id: '', kind, label: '',
    api_type: kind === 'llm' ? 'openai' : 'openai-image',
    base_url: '', api_key: '', model: '',
  })
  formMsg.value = ''; formOk.value = false
  showForm.value = true
}

function openEdit(p) {
  formMode.value = 'edit'
  Object.assign(form, {
    id: p.id, kind: p.kind, label: p.label, api_type: p.api_type,
    base_url: p.base_url, api_key: '', model: p.model,
  })
  formMsg.value = ''; formOk.value = false
  showForm.value = true
}

async function saveForm() {
  if (!form.label.trim()) { formMsg.value = '请填写名字'; formOk.value = false; return }
  savingForm.value = true; formMsg.value = ''
  try {
    if (formMode.value === 'add') {
      await apiFetch('/admin/providers', {
        method: 'POST',
        body: JSON.stringify({ kind: form.kind, label: form.label, api_type: form.api_type, base_url: form.base_url, api_key: form.api_key, model: form.model }),
      })
    } else {
      await apiFetch(`/admin/providers/${form.id}`, {
        method: 'PUT',
        body: JSON.stringify({ label: form.label, api_type: form.api_type, base_url: form.base_url, api_key: form.api_key, model: form.model }),
      })
    }
    await loadProviders()
    showForm.value = false
  } catch (e) {
    formMsg.value = e.message; formOk.value = false
  } finally { savingForm.value = false }
}

async function activate(p) {
  try {
    await apiFetch(`/admin/providers/${p.id}/activate`, { method: 'PUT' })
    if (p.kind === 'llm') activeLlm.value = p.id
    else activeImage.value = p.id
  } catch (e) { alert(e.message) }
}

async function removeConn(p) {
  if (!confirm(`删除连接「${p.label}」？`)) return
  try {
    await apiFetch(`/admin/providers/${p.id}`, { method: 'DELETE' })
    await loadProviders()
  } catch (e) { alert(e.message) }
}

async function testConn(p) {
  testingId.value = p.id; testMsg[p.id] = ''
  try {
    const res = await apiFetch('/admin/providers/test', {
      method: 'POST',
      body: JSON.stringify({ id: p.id, api_type: p.api_type, base_url: p.base_url, model: p.model }),
    })
    testMsg[p.id] = res.msg; testOk[p.id] = res.ok
  } catch (e) {
    testMsg[p.id] = e.message; testOk[p.id] = false
  } finally { testingId.value = '' }
}

// 弹窗内测试（用当前表单值，未保存也能测）
async function testForm() {
  formMsg.value = '测试中…'; formOk.value = false
  try {
    const res = await apiFetch('/admin/providers/test', {
      method: 'POST',
      body: JSON.stringify({ id: form.id, api_type: form.api_type, base_url: form.base_url, api_key: form.api_key, model: form.model }),
    })
    formMsg.value = res.msg; formOk.value = res.ok
  } catch (e) {
    formMsg.value = e.message; formOk.value = false
  }
}

// ── 提示词 ────────────────────────────────────────────────────────────────────
async function switchPromptMode(m) {
  promptMode.value = m
  activePrompt.value = ''
  promptContent.value = ''
  const data = await apiFetch(`/admin/prompts?mode=${m}`)
  promptNames.value = data.prompts
}

async function loadPrompt(name) {
  activePrompt.value = name; promptLoading.value = true
  try {
    const data = await apiFetch(`/admin/prompts/${name}?mode=${promptMode.value}`)
    promptContent.value = data.content
  } finally { promptLoading.value = false }
}

async function savePrompt() {
  savingPrompt.value = true; promptMsg.value = ''; promptError.value = false
  try {
    await apiFetch(`/admin/prompts/${activePrompt.value}?mode=${promptMode.value}`, { method: 'PUT', body: JSON.stringify({ content: promptContent.value }) })
    promptMsg.value = '已保存 ✓'
  } catch (e) {
    promptMsg.value = e.message; promptError.value = true
  } finally { savingPrompt.value = false }
}

async function loadTasks() {
  tasks.value = await apiFetch('/tasks')
}

async function retryTask(taskId) {
  await apiFetch('/tasks/retry', { method: 'POST', body: JSON.stringify({ task_id: taskId }) })
  await loadTasks()
}

onMounted(async () => {
  await loadProviders()

  const prompts = await apiFetch(`/admin/prompts?mode=${promptMode.value}`).catch(() => ({ prompts: [], modes: ['classic'] }))
  promptNames.value = prompts.prompts || []
  if (prompts.modes) availableModes.value = prompts.modes

  await loadTasks()
})
</script>

<style scoped>
.provider-block {
  @apply border border-border rounded-lg p-4 transition-colors;
}
.provider-block.active {
  @apply border-accent/50 bg-accent/5;
}
.toggle-btn {
  @apply text-xs px-3 py-1 rounded-full border transition-colors;
}
.toggle-btn.enabled {
  @apply border-accent text-accent bg-accent/10;
}
.toggle-btn.disabled {
  @apply border-border text-muted hover:border-accent/50 hover:text-accent/70;
}
.icon-btn {
  @apply text-xs px-2 py-1 rounded border border-border text-muted hover:border-accent/50 hover:text-accent transition-colors disabled:opacity-50;
}
</style>