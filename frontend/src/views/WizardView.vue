<template>
  <div class="max-w-5xl mx-auto px-8 py-10">
    <!-- 进度条 -->
    <div class="mb-10">
      <div class="flex items-center justify-between mb-3">
        <span class="text-muted">步骤 {{ step }} / 6</span>
        <span class="gradient-text font-medium">{{ stepTitles[step - 1] }}</span>
      </div>
      <div class="h-1 bg-panel rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-violet-600 to-pink-500 transition-all duration-500"
          :style="{ width: `${(step / 6) * 100}%` }"
        />
      </div>
    </div>

    <!-- 步骤内容 -->
    <div class="card animate-slide-up p-8" :key="step">

      <!-- Step 1: 故事概念 -->
      <template v-if="step === 1">
        <h2 class="text-2xl font-bold mb-2">你的故事概念</h2>
        <p class="text-muted mb-6">用一句话或几句话描述你想要的故事氛围和核心关系。</p>
        <textarea
          v-model="concept"
          class="textarea min-h-40 text-base"
          placeholder="例如：一个冷酷的CEO和他的新助理之间，因一次深夜加班引发的禁忌情愫……"
        />
        <div class="mt-4 flex justify-end">
          <button class="btn-primary" :disabled="!concept.trim() || loading" @click="doStep1">
            {{ loading ? '生成中…' : '下一步 →' }}
          </button>
        </div>

        <!-- 分隔线 -->
        <div class="flex items-center gap-4 my-6">
          <div class="flex-1 h-px bg-border"></div>
          <span class="text-muted text-sm">或者</span>
          <div class="flex-1 h-px bg-border"></div>
        </div>

        <!-- 导入 GG 卡（直接读取已有存档，跳过创建） -->
        <div class="rounded-xl border border-accent/30 bg-accent/5 px-6 py-5">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="font-semibold text-text mb-1">🃏 导入 GG 卡</div>
              <p class="text-sm text-muted leading-relaxed">已有别人分享的 GG 卡 PNG？直接导入即可跳过创建，从对方的进度接着玩</p>
            </div>
            <label class="relative flex-shrink-0">
              <span
                class="btn-ghost text-sm cursor-pointer whitespace-nowrap flex items-center gap-1.5"
                :class="importingCard ? 'opacity-50 pointer-events-none' : ''"
              >
                <span v-if="!importingCard">🃏 导入 GG 卡</span>
                <span v-else class="loading-dots">导入中</span>
              </span>
              <input
                v-if="!importingCard"
                type="file"
                accept="image/png"
                class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                @change="fromGalgameCard"
              />
            </label>
          </div>
        </div>

        <!-- 从酒馆卡创建 -->
        <div class="rounded-xl border border-border/50 bg-panel/40 px-6 py-5 mt-3">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="font-semibold text-text mb-1">从酒馆角色卡创建</div>
              <p class="text-sm text-muted leading-relaxed">上传 SillyTavern 角色卡 PNG，自动提取世界观和角色设定，直接跳到角色确认步骤</p>
            </div>
            <label class="relative flex-shrink-0">
              <span
                class="btn-ghost text-sm cursor-pointer whitespace-nowrap flex items-center gap-1.5"
                :class="loading ? 'opacity-50 pointer-events-none' : ''"
              >
                <span v-if="!loading">📎 上传角色卡</span>
                <span v-else class="loading-dots">解析中</span>
              </span>
              <input
                v-if="!loading"
                type="file"
                accept="image/png"
                class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                @change="fromTavernCard"
              />
            </label>
          </div>
        </div>
      </template>

      <!-- Step 2: 情感氛围 -->
      <template v-if="step === 2">
        <h2 class="text-2xl font-bold mb-1">情感氛围</h2>
        <p class="text-muted mb-6">选择你想要的故事基调（可多选）</p>
        <div class="flex flex-wrap gap-3 mb-8">
          <button
            v-for="v in vibeOptions"
            :key="v"
            class="px-4 py-2 rounded-full border transition-all"
            :class="selectedVibe.includes(v)
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-border text-muted hover:border-accent/50'"
            @click="toggleVibe(v)"
          >{{ v }}</button>
        </div>
        <div class="flex justify-between">
          <button class="btn-ghost" @click="step--">← 返回</button>
          <button class="btn-primary" :disabled="loading" @click="doStep2">
            {{ loading ? '生成中…' : '下一步 →' }}
          </button>
        </div>
      </template>

      <!-- Step 3: 选择开场 -->
      <template v-if="step === 3">
        <h2 class="text-2xl font-bold mb-1">选择开场</h2>
        <p class="text-muted mb-6">AI 为你生成了 3 种开场风格，选择最打动你的那个</p>
        <div v-if="loading" class="text-center py-16 text-muted loading-dots">正在构思开场</div>
        <div v-else-if="stepError" class="text-center py-10">
          <p class="text-red-400 mb-4">{{ stepError }}</p>
          <button class="btn-ghost" @click="retryStep3">↺ 重试</button>
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="(opt, i) in options"
            :key="i"
            class="p-5 rounded-xl border cursor-pointer transition-all"
            :class="selectedOption === i
              ? 'border-accent bg-accent/5'
              : 'border-border hover:border-accent/40'"
            @click="selectedOption = i"
          >
            <div class="font-semibold mb-2">{{ opt.title }}</div>
            <p class="text-muted text-sm leading-relaxed">{{ opt.content }}</p>
          </div>
          <!-- 自定义开场 -->
          <div
            class="rounded-xl border transition-all overflow-hidden"
            :class="selectedOption === 'custom'
              ? 'border-amber-600/60 bg-amber-950/20'
              : 'border-border hover:border-amber-700/40'"
            @click="selectedOption = 'custom'"
          >
            <div class="flex items-center gap-2 px-5 pt-4 pb-2 cursor-pointer">
              <span class="text-sm font-semibold text-amber-400/80">✏️ 自己写</span>
              <span class="text-xs text-muted/50">选中后在下方编辑</span>
            </div>
            <div v-if="selectedOption === 'custom'" class="px-5 pb-4" @click.stop>
              <textarea
                v-model="customOpening"
                class="textarea text-sm min-h-32 w-full"
                placeholder="写的什么B玩意，老子自己来"
                autofocus
              />
            </div>
          </div>
        </div>
        <div v-if="!loading && !stepError" class="flex justify-between mt-6">
          <button class="btn-ghost" @click="step--">← 返回</button>
          <button
            class="btn-primary"
            :disabled="selectedOption === null || (selectedOption === 'custom' && !customOpening.trim())"
            @click="doStep3"
          >下一步 →</button>
        </div>
        <div v-if="!loading && stepError" class="flex justify-between mt-6">
          <button class="btn-ghost" @click="step--">← 返回</button>
        </div>
      </template>

      <!-- Step 4: 选择背景 -->
      <template v-if="step === 4">
        <h2 class="text-2xl font-bold mb-1">选择背景设定</h2>
        <p class="text-muted mb-6">为故事选择世界观和角色关系背景</p>
        <div v-if="loading" class="text-center py-16 text-muted loading-dots">正在编织背景</div>
        <div v-else-if="stepError" class="text-center py-10">
          <p class="text-red-400 mb-4">{{ stepError }}</p>
          <button class="btn-ghost" @click="retryStep4">↺ 重试</button>
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="(opt, i) in options"
            :key="i"
            class="p-5 rounded-xl border cursor-pointer transition-all"
            :class="selectedOption === i
              ? 'border-accent bg-accent/5'
              : 'border-border hover:border-accent/40'"
            @click="selectedOption = i"
          >
            <div class="font-semibold mb-2">{{ opt.title }}</div>
            <p class="text-muted text-sm leading-relaxed">{{ opt.content }}</p>
          </div>
          <!-- 自定义背景 -->
          <div
            class="rounded-xl border transition-all overflow-hidden"
            :class="selectedOption === 'custom'
              ? 'border-amber-600/60 bg-amber-950/20'
              : 'border-border hover:border-amber-700/40'"
            @click="selectedOption = 'custom'"
          >
            <div class="flex items-center gap-2 px-5 pt-4 pb-2 cursor-pointer">
              <span class="text-sm font-semibold text-amber-400/80">✏️ 自己写</span>
              <span class="text-xs text-muted/50">选中后在下方编辑</span>
            </div>
            <div v-if="selectedOption === 'custom'" class="px-5 pb-4" @click.stop>
              <textarea
                v-model="customBackstory"
                class="textarea text-sm min-h-32 w-full"
                placeholder="写的什么B玩意，老子自己来"
                autofocus
              />
            </div>
          </div>
        </div>
        <div v-if="!loading && !stepError" class="flex justify-between mt-6">
          <button class="btn-ghost" @click="step--">← 返回</button>
          <button
            class="btn-primary"
            :disabled="selectedOption === null || (selectedOption === 'custom' && !customBackstory.trim())"
            @click="doStep4"
          >下一步 →</button>
        </div>
        <div v-if="!loading && stepError" class="flex justify-between mt-6">
          <button class="btn-ghost" @click="step--">← 返回</button>
        </div>
      </template>

      <!-- Step 5: 角色设计 -->
      <template v-if="step === 5">
        <h2 class="text-2xl font-bold mb-1">角色设计</h2>
        <p class="text-muted mb-6">选择你要扮演的角色，所有角色均可上传参考图（支持酒馆角色卡 PNG 智能导入）或修改形象描述。</p>
        <div v-if="loading" class="text-center py-16 text-muted loading-dots">正在提取角色</div>
        <div v-else class="space-y-5">

          <!-- 酒馆卡内容预览（仅从酒馆卡导入时显示） -->
          <div
            v-if="isTavernImport && (tavernCardOpening || tavernCardBackstory)"
            class="rounded-xl border border-cyan-700/30 bg-cyan-950/20 p-4"
          >
            <div class="flex items-center gap-2 mb-3">
              <span class="text-sm font-semibold text-cyan-400/80">📖 酒馆卡内容（已跳过步骤3–4）</span>
              <span class="text-xs text-muted">可在故事编辑中修改</span>
            </div>
            <div class="grid gap-3" :class="tavernCardOpening && tavernCardBackstory ? 'grid-cols-2' : 'grid-cols-1'">
              <div v-if="tavernCardOpening">
                <div class="text-xs text-muted mb-1">开场白</div>
                <div class="rounded-lg bg-surface/50 border border-border/40 p-3 text-sm text-text/80 max-h-32 overflow-y-auto leading-relaxed whitespace-pre-wrap">{{ tavernCardOpening }}</div>
              </div>
              <div v-if="tavernCardBackstory">
                <div class="text-xs text-muted mb-1">世界背景 / 角色设定</div>
                <div class="rounded-lg bg-surface/50 border border-border/40 p-3 text-sm text-text/80 max-h-32 overflow-y-auto leading-relaxed whitespace-pre-wrap">{{ tavernCardBackstory }}</div>
              </div>
            </div>
          </div>

          <!-- 角色卡片 -->
          <div
            v-for="(char, i) in characters"
            :key="i"
            class="bg-panel rounded-xl p-5 border transition-all"
            :class="playerCharIdx === i ? 'border-purple-600/60 ring-1 ring-purple-700/40' : 'border-border'"
          >
            <!-- 顶部：头像 + 名字/按钮 + 字段 -->
            <div class="flex items-start gap-5 mb-4">
              <!-- 参考图上传区（更大） -->
              <div class="flex-shrink-0 flex flex-col items-center gap-2">
                <label class="block w-28 h-36 rounded-xl border-2 border-dashed border-border cursor-pointer overflow-hidden hover:border-accent/60 transition-colors relative">
                  <img v-if="char.reference_image" :src="char.reference_image" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex flex-col items-center justify-center text-muted gap-2">
                    <span class="text-2xl">↑</span>
                    <span class="text-xs text-center leading-tight">上传参考图<br/>或酒馆卡</span>
                  </div>
                  <input type="file" accept="image/*" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer" @change="onCharImageUpload($event, i)" />
                </label>
              </div>

              <!-- 字段区 -->
              <div class="flex-1 min-w-0">
                <!-- 名字 + 操作按钮 -->
                <div class="flex items-center justify-between mb-3 gap-3">
                  <input v-model="char.name" class="input py-2 text-base font-semibold flex-1 max-w-[220px]" placeholder="角色名" />
                  <div class="flex items-center gap-2 flex-shrink-0">
                    <button
                      class="text-sm px-3 py-1.5 rounded-full border transition-all"
                      :class="playerCharIdx === i
                        ? 'border-purple-600 bg-purple-900/30 text-purple-300'
                        : 'border-border text-muted hover:border-purple-600/50 hover:text-purple-400'"
                      @click="playerCharIdx = i"
                    >🎭 {{ playerCharIdx === i ? '扮演中' : '扮演' }}</button>
                    <button class="text-muted hover:text-red-400" @click="characters.splice(i, 1); if(playerCharIdx >= characters.length) playerCharIdx = 0">删除</button>
                  </div>
                </div>
                <!-- 外貌 + 性格并排 -->
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <div class="text-xs text-muted mb-1">外貌描述</div>
                    <textarea v-model="char.description" class="textarea text-sm min-h-24" placeholder="身形、发色、眼神、服装等外貌特征…" />
                  </div>
                  <div>
                    <div class="text-xs text-muted mb-1">性格特征</div>
                    <textarea v-model="char.personality" class="textarea text-sm min-h-24" placeholder="性格、行为习惯、说话方式等…" />
                  </div>
                </div>
              </div>
            </div>

            <!-- 底部：生图设置 or 参考图提示 -->
            <div v-if="char.reference_image" class="text-sm text-green-400/80 bg-green-900/10 border border-green-700/20 rounded-lg px-4 py-2 flex items-center gap-3">
              <span>✓ 已上传参考图，将直接作为角色头像</span>
              <span v-if="char.alternate_greetings?.length" class="text-xs text-blue-400/70 border-l border-green-700/30 pl-3">· {{ char.alternate_greetings.length }} 条备用开场</span>
            </div>
            <template v-else>
              <div class="border-t border-border/50 pt-4">
                <div class="text-xs text-muted mb-2">生图风格</div>
                <div class="flex flex-wrap gap-2 mb-3">
                  <button
                    v-for="s in styleOptions"
                    :key="s.key"
                    class="text-xs px-3 py-1.5 rounded-full border transition-all"
                    :class="char.image_style === s.key
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border text-muted hover:border-accent/40'"
                    @click="char.image_style = char.image_style === s.key ? '' : s.key"
                  >{{ s.label }}</button>
                  <span v-if="!char.image_style" class="text-xs text-muted/50 self-center">不选则随机</span>
                </div>
                <div class="text-xs text-muted mb-1">生图描述（英文效果更佳）</div>
                <textarea v-model="char.image_prompt" class="textarea text-sm min-h-16" placeholder="角色外貌的英文描述，用于生成头像…" />
              </div>
            </template>
          </div>

          <button class="btn-ghost w-full py-3" @click="addCharacter">＋ 添加角色</button>
        </div>
        <div v-if="!loading" class="flex justify-between mt-6">
          <button class="btn-ghost" @click="step--">← 返回</button>
          <button class="btn-primary" :disabled="characters.length === 0" @click="doStep5">下一步 →</button>
        </div>
      </template>

      <!-- Step 6: 生成头像 -->
      <template v-if="step === 6">
        <h2 class="text-2xl font-bold mb-2">生成角色头像</h2>
        <p class="text-muted mb-6">正在为你的角色生成形象，这可能需要一点时间</p>
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div
            v-for="task in avatarTasks"
            :key="task.character_id"
            class="bg-panel rounded-xl p-4 flex flex-col items-center gap-3 border border-border"
          >
            <div class="w-24 h-24 rounded-xl overflow-hidden bg-surface flex items-center justify-center flex-shrink-0">
              <img v-if="task.avatar_url" :src="task.avatar_url" class="w-full h-full object-cover" />
              <span v-else class="text-muted text-sm">…</span>
            </div>
            <div class="text-center">
              <div class="font-medium mb-1">{{ task.name }}</div>
              <div class="text-sm text-muted">
                <span v-if="task.status === 'completed'" class="text-green-400">✓ 完成</span>
                <template v-else-if="task.status === 'failed'">
                  <span class="text-red-400 mr-2">✗ 失败</span>
                  <button
                    class="text-accent hover:underline text-xs"
                    :disabled="task.retrying"
                    @click="retryAvatar(task)"
                  >{{ task.retrying ? '重试中…' : '重试' }}</button>
                </template>
                <span v-else class="loading-dots">生成中</span>
              </div>
            </div>
          </div>
        </div>
        <div class="mt-8 flex justify-between">
          <div class="flex gap-2">
            <button class="btn-ghost" @click="goBackToStep5">← 返回修改</button>
            <button class="btn-ghost" @click="skipAvatars">跳过，直接进入</button>
          </div>
          <button
            class="btn-primary"
            :disabled="pendingTasks > 0"
            @click="finishWizard"
          >
            {{ pendingTasks > 0 ? `等待生成（${pendingTasks}）` : '开始故事 →' }}
          </button>
        </div>
      </template>

    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="mt-4 p-3 rounded-lg border border-red-800/50 bg-red-900/10 text-red-300 text-sm">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const step = ref(1)
const loading = ref(false)
const error = ref('')
const plotId = ref(route.query.plot_id ? Number(route.query.plot_id) : null)

const concept = ref('')
const selectedVibe = ref([])
const options = ref([])
const selectedOption = ref(null)
const stepError = ref('')
const customOpening = ref('')
const customBackstory = ref('')
const characters = ref([])
const avatarTasks = ref([])
const playerCharIdx = ref(0)  // 用户选择扮演的角色下标
const isTavernImport = ref(false)
const tavernCardOpening = ref('')
const tavernCardBackstory = ref('')
let pollTimer = null

const styleOptions = [
  { key: 'realistic', label: '写实' },
  { key: 'manhwa',    label: '韩漫' },
  { key: 'anime',     label: '日漫' },
  { key: 'otome3d',   label: '乙女3D' },
  { key: 'donghua3d', label: '国漫3D' },
  { key: 'donghua2d', label: '国漫2D' },
  { key: 'comics',    label: '美漫' },
  { key: 'disney3d',  label: '3D卡通' },
  { key: 'manga_bw',  label: '黑白漫画' },
]

const vibeOptions = [
  '都市悬疑', '腹黑反派', '甜蜜温柔', '热血冒险',
  '权力博弈', '身份反差', '命运纠缠', '异世界情缘',
  '复仇与爱', '错位邂逅', '纯爱校园', '成熟睿智',
]

const stepTitles = ['故事概念', '情感氛围', '选择开场', '背景设定', '角色设计', '生成形象']

const pendingTasks = computed(() =>
  avatarTasks.value.filter(t => t.status !== 'completed' && t.status !== 'failed').length
)

function toggleVibe(v) {
  const i = selectedVibe.value.indexOf(v)
  if (i >= 0) selectedVibe.value.splice(i, 1)
  else selectedVibe.value.push(v)
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || e.error || `HTTP ${res.status}`)
  }
  return res.json()
}

async function doStep1() {
  if (!concept.value.trim()) return
  loading.value = true; error.value = ''
  try {
    const data = await apiFetch('/plots/wizard/1', {
      method: 'POST',
      body: JSON.stringify({ concept: concept.value, plot_id: plotId.value }),
    })
    plotId.value = data.plot_id
    step.value = 2
  } catch (e) { error.value = e.message } finally { loading.value = false }
}

// 导入 GG 卡：直接解码已有存档并跳转，跳过整个创建流程（复用 HomeView 的导入接口）
const importingCard = ref(false)
async function fromGalgameCard(event) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
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
    router.push(`/read/${session_id}`)
  } catch (e) {
    alert('导入 GG 卡失败：' + e.message)
  } finally {
    importingCard.value = false
  }
}

async function fromTavernCard(event) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  loading.value = true; error.value = ''
  try {
    // 读取文件为 base64
    const b64 = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })

    // 1. 解析酒馆卡
    const parsed = await apiFetch('/characters/parse-tavern-card', {
      method: 'POST',
      body: JSON.stringify({ data: b64 }),
    })
    if (!parsed.is_tavern_card) {
      error.value = '未检测到有效的酒馆角色卡数据（PNG 中没有 chara 字段）'
      return
    }

    // 2. 创建草稿剧情
    const conceptText = (parsed.description || parsed.first_mes || parsed.name || '').slice(0, 500)
    const plotData = await apiFetch('/plots/wizard/1', {
      method: 'POST',
      body: JSON.stringify({ concept: conceptText }),
    })
    plotId.value = plotData.plot_id

    // 3. 保存空 vibe
    await apiFetch('/plots/wizard/2', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, vibe: [] }),
    })

    // 4. 一次 LLM：从 raw_json 提取所有角色 + opening + backstory
    let imported = { characters: [], opening: parsed.first_mes || '', backstory: parsed.description || '' }
    try {
      imported = await apiFetch('/plots/wizard/import-tavern', {
        method: 'POST',
        body: JSON.stringify({
          plot_id: plotId.value,
          raw_json: parsed.raw_json,
          fallback_name: parsed.name,
          fallback_description: parsed.description || '',
          fallback_personality: parsed.personality || '',
          fallback_first_mes: parsed.first_mes || '',
        }),
      })
    } catch { /* LLM 失败已降级，不阻塞流程 */ }

    // 5. 组装角色列表：LLM 全权负责角色提取，不再手动构建 mainChar
    //    酒馆卡图片默认给玩家角色（用户扮演的那个）
    const allExtracted = imported.characters || []
    const extractedPlayerChar = allExtracted.find(c => c.is_user) || null
    const npcList = allExtracted.filter(c => !c.is_user && c.name)
    const playerChar = {
      name: extractedPlayerChar?.name || '你',
      description: extractedPlayerChar?.description || '',
      personality: extractedPlayerChar?.personality || '',
      image_prompt: '',
      image_style: '',
      reference_image: parsed.image_url || '',  // 卡图默认给玩家角色
    }

    characters.value = [...npcList, playerChar]
    playerCharIdx.value = characters.value.length - 1
    isTavernImport.value = true
    tavernCardOpening.value = imported.opening || parsed.first_mes || ''
    tavernCardBackstory.value = imported.backstory || parsed.description || ''
    step.value = 5
  } catch (e) {
    error.value = '解析失败：' + e.message
  } finally {
    loading.value = false
  }
}

async function doStep2() {
  loading.value = true; error.value = ''; stepError.value = ''
  try {
    await apiFetch('/plots/wizard/2', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, vibe: selectedVibe.value }),
    })
    step.value = 3
    options.value = []
    selectedOption.value = null
    await _loadStep3Options()
  } catch (e) { error.value = e.message } finally { loading.value = false }
}

async function _loadStep3Options() {
  loading.value = true; stepError.value = ''
  try {
    const data = await apiFetch('/plots/wizard/3', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value }),
    })
    options.value = data.options
  } catch (e) {
    stepError.value = e.message
  } finally { loading.value = false }
}

async function retryStep3() {
  options.value = []
  selectedOption.value = null
  await _loadStep3Options()
}

const _lastOpening = ref('')

async function doStep3() {
  const opening = selectedOption.value === 'custom'
    ? customOpening.value.trim()
    : options.value[selectedOption.value]?.content
  if (!opening) return
  _lastOpening.value = opening
  step.value = 4
  options.value = []
  selectedOption.value = null
  loading.value = true; stepError.value = ''
  try {
    const data = await apiFetch('/plots/wizard/4', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, opening }),
    })
    options.value = data.options
  } catch (e) {
    stepError.value = e.message
  } finally { loading.value = false }
}

async function retryStep4() {
  options.value = []
  selectedOption.value = null
  loading.value = true; stepError.value = ''
  try {
    const data = await apiFetch('/plots/wizard/4', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, opening: _lastOpening.value }),
    })
    options.value = data.options
  } catch (e) {
    stepError.value = e.message
  } finally { loading.value = false }
}

async function doStep4() {
  const backstory = selectedOption.value === 'custom'
    ? customBackstory.value.trim()
    : options.value[selectedOption.value]?.content
  if (!backstory) return
  loading.value = true; stepError.value = ''
  step.value = 5
  characters.value = []
  try {
    const data = await apiFetch('/plots/wizard/5', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, backstory }),
    })
    characters.value = data.characters
    playerCharIdx.value = 0  // 默认扮演第一个角色
  } catch (e) { error.value = e.message } finally { loading.value = false }
}

async function doStep5() {
  loading.value = true; error.value = ''
  try {
    const data = await apiFetch('/plots/wizard/6', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId.value, characters: characters.value, player_char_index: playerCharIdx.value }),
    })
    // 构建头像任务列表（task_id 为 null 表示直接用参考图，标为已完成）
    avatarTasks.value = data.task_ids.map(t => ({
      ...t,
      name: '加载中',
      status: t.task_id === null ? 'completed' : 'pending',
      avatar_url: t.avatar_url || '',
    }))
    // 加载角色信息来获取名字
    await loadCharacterNames()
    step.value = 6
    startPollAvatars(data.task_ids)
  } catch (e) { error.value = e.message } finally { loading.value = false }
}

async function loadCharacterNames() {
  try {
    const plot = await apiFetch(`/plots/${plotId.value}`)
    const chars = plot.characters || []
    avatarTasks.value = avatarTasks.value.map(t => {
      const c = chars.find(c => c.id === t.character_id)
      return { ...t, name: c?.name || '角色' }
    })
  } catch {}
}

function startPollAvatars(taskIds) {
  if (!taskIds.length) return
  pollTimer = setInterval(async () => {
    for (const t of avatarTasks.value) {
      if (t.status === 'completed' || t.status === 'failed') continue
      if (!t.task_id) { t.status = 'completed'; continue }  // 参考图直用，无需轮询
      try {
        const data = await apiFetch(`/tasks/${t.task_id}`)
        t.status = data.status
        if (data.status === 'completed') {
          const plot = await apiFetch(`/plots/${plotId.value}`)
          const char = plot.characters.find(c => c.id === t.character_id)
          if (char) t.avatar_url = char.avatar_url
        }
      } catch {}
    }
    if (pendingTasks.value === 0) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 3000)
}

function addCharacter() {
  characters.value.push({ name: '', description: '', personality: '', image_prompt: '', image_style: '', reference_image: '' })
}

function onCharImageUpload(event, index) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  const reader = new FileReader()
  reader.onload = async () => {
    const b64 = reader.result
    // PNG 先尝试酒馆卡解析
    if (file.type === 'image/png' || file.name.endsWith('.png')) {
      try {
        const res = await fetch('/api/characters/parse-tavern-card', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: b64 }),
        })
        const parsed = await res.json()
        if (parsed.is_tavern_card) {
          const char = characters.value[index]
          if (parsed.name) char.name = parsed.name
          if (parsed.description) char.description = parsed.description
          if (parsed.personality) char.personality = parsed.personality
          if (parsed.first_mes) char.first_mes = parsed.first_mes
          if (parsed.alternate_greetings?.length) char.alternate_greetings = parsed.alternate_greetings
          char.reference_image = parsed.image_url
          return  // 完成，不再走普通上传
        }
      } catch { /* 解析失败，继续普通上传 */ }
    }
    // 普通图片上传
    try {
      const res = await fetch('/api/uploads/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: b64 }),
      })
      const data = await res.json()
      characters.value[index].reference_image = data.url
    } catch {
      characters.value[index].reference_image = b64
    }
  }
  reader.readAsDataURL(file)
}

async function retryAvatar(task) {
  task.retrying = true
  task.status = 'pending'
  task.avatar_url = ''
  try {
    const data = await apiFetch(`/characters/${task.character_id}/regenerate-avatar`, { method: 'POST' })
    task.task_id = data.task_id
    task.retrying = false
    // 如果轮询已停止则重启
    if (!pollTimer) startPollAvatars([task])
  } catch (e) {
    task.status = 'failed'
    task.retrying = false
  }
}

function goBackToStep5() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  avatarTasks.value = []
  step.value = 5
}

async function skipAvatars() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  await finishWizard()
}

async function finishWizard() {
  await apiFetch(`/plots/${plotId.value}/publish`, { method: 'PUT' })
  const { session_id } = await apiFetch('/sessions', {
    method: 'POST',
    body: JSON.stringify({ plot_id: plotId.value }),
  })
  router.push(`/read/${session_id}`)
}

onMounted(async () => {
  if (plotId.value) {
    try {
      const plot = await apiFetch(`/plots/${plotId.value}`)
      concept.value = plot.concept || ''
      if (plot.vibe) {
        try { selectedVibe.value = JSON.parse(plot.vibe) } catch {}
      }
    } catch {}
  }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>
