<template>
  <div class="flex flex-col h-[calc(100vh-3.5rem)] relative">

    <!-- 顶部栏 -->
    <div class="relative z-10 flex-shrink-0 flex items-center gap-3 px-5 py-3 border-b border-border bg-bg/70 backdrop-blur-md">
      <RouterLink to="/" class="text-muted hover:text-text text-sm">← 返回</RouterLink>
      <div class="h-4 w-px bg-border" />
      <span class="font-medium text-sm truncate max-w-xs">{{ plot?.title || '加载中…' }}</span>
      <div class="flex-1" />

      <button
        class="btn-ghost text-xs px-3 py-1.5 border border-red-500/20 text-red-400/70 hover:bg-red-900/20 hover:text-red-300 hover:border-red-400/40 transition-all"
        title="清空对话与实况记录，保留角色和设定"
        @click="clearChat"
      >🗑 清空对话</button>

      <button class="btn-ghost text-xs px-3 py-1.5" title="查看记忆（Ctrl+M）" @click="openMemory">🧠 记忆</button>
      <button
        class="btn-ghost text-xs px-2 py-1.5 border transition-all"
        :class="showTurnSep ? 'border-amber-500/30 text-amber-400 bg-amber-900/20' : 'border-border/30 text-muted/50'"
        :title="showTurnSep ? '回合分隔线：开' : '回合分隔线：关'"
        @click="showTurnSep = !showTurnSep"
      >━</button>
      <div class="flex items-center gap-1.5 ml-1" v-if="bgImage" title="背景透明度">
        <span class="text-[10px] text-muted/60 flex-shrink-0">☀</span>
        <input type="range" min="0" max="100" v-model.number="bgOpacity" class="w-14 h-1 accent-accent cursor-pointer flex-shrink-0" />
      </div>
      <button
        class="btn-ghost text-xs px-3 py-1.5 border border-cyan-500/20 text-cyan-400/70 hover:bg-cyan-900/20 hover:text-cyan-300 hover:border-cyan-400/40 transition-all"
        title="编辑故事设定、角色、世界书（Ctrl+B）"
        @click="openWorldRules"
      >🌐 世界书</button>
      <button
        class="text-xs font-semibold px-3.5 py-1.5 rounded-lg text-white bg-gradient-to-r from-fuchsia-600 to-violet-600 hover:from-fuchsia-500 hover:to-violet-500 shadow-lg shadow-violet-900/30 ring-1 ring-white/10 transition-all"
        title="把当前故事打包成一张 GG 卡分享给朋友（Ctrl+S）"
        @click="openExport"
      >🃏 导出 GG 卡</button>
      <button
        class="btn-ghost text-xs px-2 py-1.5"
        :class="showCharSidebar ? 'text-accent' : 'text-muted'"
        title="角色栏"
        @click="showCharSidebar = !showCharSidebar"
      >👥</button>
    </div>

    <!-- 记忆抽屉遮罩 -->
    <Transition name="fade">
      <div
        v-if="showMemory"
        class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        @click="showMemory = false"
      />
    </Transition>

    <!-- 插入角色弹窗 -->
    <Transition name="fade">
      <div v-if="showCharModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showCharModal = false">
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto">
          <h3 class="text-lg font-semibold text-text mb-4">＋ 插入新角色</h3>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-muted block mb-1">角色名</label>
              <div class="flex gap-2">
                <input v-model="newChar.name" class="input flex-1 text-sm" placeholder="例如：柳如烟" />
                <button
                  class="text-xs px-3 py-1.5 rounded-lg border border-amber-500/40 text-amber-300/80 bg-amber-900/20 hover:bg-amber-800/30 hover:border-amber-400/60 transition-all flex-shrink-0"
                  :disabled="!newChar.name.trim() || autofilling"
                  @click="autofillCharacter"
                >{{ autofilling ? '补全中…' : '✨ AI补全' }}</button>
              </div>
            </div>
            <div>
              <label class="text-xs text-muted block mb-1">描述</label>
              <input v-model="newChar.description" class="input w-full text-sm" placeholder="例如：隔壁班的冷面学霸" />
            </div>
            <div>
              <label class="text-xs text-muted block mb-1">性格</label>
              <input v-model="newChar.personality" class="input w-full text-sm" placeholder="例如：高傲冷淡但内心温柔" />
            </div>

            <!-- 头像模式切换 -->
            <div>
              <label class="text-xs text-muted block mb-2">头像</label>
              <div class="flex gap-2">
                <button
                  class="flex-1 text-xs py-1.5 rounded-lg border transition-all"
                  :class="newChar.avatarMode === 'upload' ? 'border-accent bg-accent/10 text-accent' : 'border-border text-muted hover:border-accent/40'"
                  @click="newChar.avatarMode = 'upload'"
                >📷 传图</button>
                <button
                  class="flex-1 text-xs py-1.5 rounded-lg border transition-all"
                  :class="newChar.avatarMode === 'generate' ? 'border-accent bg-accent/10 text-accent' : 'border-border text-muted hover:border-accent/40'"
                  @click="newChar.avatarMode = 'generate'"
                >✨ 文生图</button>
              </div>
            </div>

            <!-- 传图模式 -->
            <template v-if="newChar.avatarMode === 'upload'">
              <div
                class="border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all hover:border-accent/50"
                :class="newChar.avatarPreview ? 'border-accent/30 bg-accent/5' : 'border-border'"
                @click="triggerFileInput"
                @dragover.prevent
                @drop.prevent="onFileDrop"
              >
                <template v-if="newChar.avatarPreview">
                  <img :src="newChar.avatarPreview" class="w-20 h-20 rounded-full object-cover mx-auto mb-2 ring-2 ring-accent/40" />
                  <span class="text-xs text-muted">点击更换图片</span>
                </template>
                <template v-else>
                  <div class="text-3xl mb-2 opacity-30">📷</div>
                  <span class="text-xs text-muted">点击上传或拖拽图片<br>支持 JPG / PNG / WEBP</span>
                </template>
                <input ref="fileInputRef" type="file" accept="image/*" class="hidden" @change="onFilePicked" />
              </div>
            </template>

            <!-- 文生图模式 -->
            <template v-if="newChar.avatarMode === 'generate'">
              <div>
                <label class="text-xs text-muted block mb-1">生图描述</label>
                <input v-model="newChar.image_prompt" class="input w-full text-sm" placeholder="例如：黑长直少女，校服，冷峻眼神" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">风格</label>
                <select v-model="newChar.image_style" class="input w-full text-sm">
                  <option value="">随机</option>
                  <option value="realistic">写实</option>
                  <option value="manhwa">韩漫</option>
                  <option value="anime">日漫</option>
                  <option value="otome3d">乙女3D</option>
                  <option value="donghua3d">国漫3D</option>
                  <option value="donghua2d">国漫2D</option>
                  <option value="comics">美漫</option>
                  <option value="disney3d">3D卡通</option>
                  <option value="manga_bw">黑白漫画</option>
                </select>
              </div>
            </template>
          </div>
          <div class="flex justify-end gap-3 mt-5">
            <button class="btn-ghost text-sm px-4 py-2" @click="showCharModal = false">取消</button>
            <button class="btn-primary text-sm px-4 py-2" :disabled="!canInsertChar || insertingChar" @click="insertCharacter">
              {{ insertingChar ? '插入中…' : '插入角色' }}
            </button>
          </div>
          <!-- 匹配为现有角色 -->
          <div v-if="newChar.name.trim() && characters.length" class="mt-3 pt-3 border-t border-border/30">
            <p class="text-[11px] text-muted/60 mb-2">或者匹配为已有角色（将"{{ newChar.name.trim() }}"作为别名加入）：</p>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="c in characters"
                :key="c.id"
                class="text-[11px] px-2 py-0.5 rounded border transition-colors"
                :class="matchCharTargetInModal === c.id ? 'border-amber-500/40 bg-amber-900/20 text-amber-300' : 'border-border/40 text-muted hover:border-amber-500/30 hover:text-amber-400'"
                @click="matchCharTargetInModal = matchCharTargetInModal === c.id ? null : c.id"
              >{{ c.name }}</button>
            </div>
            <button
              v-if="matchCharTargetInModal"
              class="btn-primary text-xs w-full mt-2 py-1.5"
              @click="confirmMatchInModal"
            >确认匹配为「{{ characters.find(c => c.id === matchCharTargetInModal)?.name }}」</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 记忆弹窗（屏幕居中，与世界书一致） -->
    <Transition name="fade">
      <div
        v-if="showMemory"
        class="fixed inset-0 z-[110] flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
        @click.self="showMemory = false"
      >
       <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <!-- 头部 -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
          <div>
            <span class="font-medium text-sm text-text">🧠 记忆槽位</span>
            <span class="text-[10px] text-muted/60 ml-1" v-if="memoryCurrentRound && !memoryError">第 {{ memoryCurrentRound }} 轮</span>
            <span class="text-[10px] text-red-400/70 ml-1" v-if="memoryError" title="记忆数据加载失败，显示的是过期数据">
              ⚠ 加载失败（点刷新重试）
            </span>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="text-xs px-2 py-1 rounded border transition-all"
              :class="canCheckpoint ? 'border-amber-500/40 text-amber-400 hover:bg-amber-900/30' : 'border-border/30 text-muted/40 cursor-not-allowed'"
              :disabled="!canCheckpoint"
              :title="canCheckpoint ? '将当前记忆手动写入存档' : '已有新对话时可用'"
              @click="triggerCheckpoint"
            >💾 存档</button>
            <button
              class="text-xs text-muted hover:text-accent transition-colors"
              :class="{ 'loading-dots pointer-events-none': memoryLoading }"
              @click="refreshMemory"
            >{{ memoryLoading ? '更新中' : '刷新' }}</button>
            <button class="text-muted hover:text-text text-lg leading-none" @click="showMemory = false">×</button>
          </div>
        </div>

        <!-- 抽屉内容 -->
        <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3">

          <!-- 空状态 -->
          <div v-if="!hasMemory" class="text-center py-12 text-muted">
            <div class="text-3xl mb-3 opacity-30">🧠</div>
            <p class="text-sm">记忆槽位为空</p>
            <p class="text-xs mt-1 opacity-60">对话满 {{ memoryInterval }} 条后自动更新</p>
            <p class="text-[10px] mt-1 opacity-40">当前 {{ memoryCurrentRound }} / {{ memoryInterval }} 轮</p>
          </div>

          <template v-else>
            <!-- 玩家角色 (player) -->
            <div v-if="hasSlot(memorySlots.player)" class="memory-card">
              <div class="memory-card-title">👤 玩家角色</div>
              <div class="memory-rows">
                <div v-if="memorySlots.player?.name" class="memory-row"><span class="memory-label">角色</span><span>{{ memorySlots.player.name }}</span></div>
                <div v-if="memorySlots.player?.state" class="memory-row"><span class="memory-label">状态</span><span>{{ memorySlots.player.state }}</span></div>
                <div v-if="memorySlots.player?.notes" class="memory-row"><span class="memory-label">经历</span><span>{{ memorySlots.player.notes }}</span></div>
              </div>
            </div>

            <!-- 当前场景 (scene) -->
            <div v-if="hasSlot(memorySlots.scene)" class="memory-card">
              <div class="memory-card-title">🌆 当前场景</div>
              <div class="memory-rows">
                <div v-if="memorySlots.scene?.location" class="memory-row"><span class="memory-label">地点</span><span>{{ memorySlots.scene.location }}</span></div>
                <div v-if="memorySlots.scene?.time" class="memory-row"><span class="memory-label">时间</span><span>{{ memorySlots.scene.time }}</span></div>
                <div v-if="memorySlots.scene?.atmosphere" class="memory-row"><span class="memory-label">基调</span><span>{{ memorySlots.scene.atmosphere }}</span></div>
              </div>
            </div>

            <!-- 数值/机制 (mechanics) — 世界书定义的隐藏数值，数字显示为进度条 -->
            <div v-if="memorySlots.mechanics && Object.keys(memorySlots.mechanics).length" class="memory-card">
              <div class="memory-card-title">⚙️ 数值 / 机制</div>
              <div class="space-y-2">
                <div v-for="(val, key) in memorySlots.mechanics" :key="key">
                  <template v-if="statPct(val) !== null">
                    <div class="flex items-center justify-between mb-0.5">
                      <span class="text-xs text-text/80">{{ key }}</span>
                      <span class="text-[11px] font-semibold text-text/90">{{ val }}</span>
                    </div>
                    <div class="h-1.5 rounded-full bg-border/40 overflow-hidden">
                      <div class="h-full rounded-full transition-all" :class="statColor(statPct(val))" :style="{ width: statPct(val) + '%' }"></div>
                    </div>
                  </template>
                  <div v-else class="memory-row"><span class="text-muted flex-shrink-0">{{ key }}</span><span class="text-accent2 ml-auto">{{ val }}</span></div>
                </div>
              </div>
            </div>

            <!-- NPC 状态 (npcs) — 对象，每个 key 一个 NPC -->
            <div v-if="memorySlots.npcs && Object.keys(memorySlots.npcs).length" class="memory-card">
              <div class="memory-card-title">💫 NPC 状态</div>
              <div class="space-y-2">
                <div v-for="(npc, name) in memorySlots.npcs" :key="name" class="memory-rows border-t border-border/40 pt-2 first:border-0 first:pt-0">
                  <div class="memory-row font-medium text-text/90"><span class="memory-label"></span><span>{{ name }}</span></div>
                  <div v-if="npc?.state" class="memory-row"><span class="memory-label">状态</span><span>{{ npc.state }}</span></div>
                  <div v-if="npc?.attitude" class="memory-row"><span class="memory-label">态度</span><span class="text-accent">{{ npc.attitude }}</span></div>
                  <!-- 好感度数值条 -->
                  <div v-if="statPct(npc?.affinity) !== null" class="flex items-center gap-2">
                    <span class="memory-label">好感</span>
                    <div class="flex-1 h-1.5 rounded-full bg-border/40 overflow-hidden">
                      <div class="h-full rounded-full transition-all" :class="statColor(statPct(npc.affinity))" :style="{ width: statPct(npc.affinity) + '%' }"></div>
                    </div>
                    <span class="text-[11px] font-semibold text-text/80 w-7 text-right">{{ statPct(npc.affinity) }}</span>
                  </div>
                  <div v-if="npc?.revealed" class="memory-row"><span class="memory-label">揭示</span><span>{{ npc.revealed }}</span></div>
                </div>
              </div>
            </div>

            <!-- 关系网 (relations) — 数组 -->
            <div v-if="memorySlots.relations?.length" class="memory-card">
              <div class="memory-card-title">💕 关系网 <span class="text-muted font-normal text-xs">({{ memorySlots.relations.length }})</span></div>
              <div class="space-y-1.5">
                <div v-for="(rel, i) in memorySlots.relations" :key="i" class="text-xs">
                  <span class="text-text font-medium">{{ rel.a }} ↔ {{ rel.b }}</span>
                  <span class="text-accent ml-1">{{ rel.type }}</span>
                  <span v-if="rel.tension" class="text-muted ml-1">（{{ rel.tension }}）</span>
                </div>
              </div>
            </div>

            <!-- 悬念线索 (threads) — 只显示进行中 -->
            <div v-if="memorySlots.threads?.filter(t => t.status === '进行中').length" class="memory-card">
              <div class="memory-card-title">🔍 悬念线索</div>
              <div class="space-y-1.5">
                <div v-for="(t, i) in memorySlots.threads.filter(t => t.status === '进行中')" :key="i" class="text-xs text-text/80 flex items-start gap-1.5">
                  <span class="text-accent mt-0.5 flex-shrink-0">·</span>
                  <span>{{ t.title }}</span>
                </div>
              </div>
            </div>

            <!-- 关键事件 (events) -->
            <div v-if="memorySlots.events?.length" class="memory-card">
              <div class="memory-card-title">📅 关键事件 <span class="text-muted font-normal text-xs">({{ memorySlots.events.length }})</span></div>
              <div class="space-y-1.5">
                <div v-for="(e, i) in memorySlots.events" :key="i" class="text-xs text-text/80">
                  <span v-if="e.location" class="text-muted">[{{ e.location }}] </span>
                  <span>{{ e.event }}</span>
                  <span v-if="e.impact" class="text-muted"> → {{ e.impact }}</span>
                </div>
              </div>
            </div>

            <!-- 重要物品 (items) -->
            <div v-if="memorySlots.items?.length" class="memory-card">
              <div class="memory-card-title">🎁 重要物品 <span class="text-muted font-normal text-xs">({{ memorySlots.items.length }})</span></div>
              <div class="space-y-1.5">
                <div v-for="(it, i) in memorySlots.items" :key="i" class="text-xs">
                  <span class="text-text font-medium">{{ it.item }}</span>
                  <span v-if="it.holder" class="text-muted">（{{ it.holder }}）</span>
                  <span v-if="it.note" class="text-muted">：{{ it.note }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 底部提示 -->
        <div class="px-4 py-3 border-t border-border flex-shrink-0 text-xs text-muted text-center">
          每 {{ memoryInterval }} 条消息自动更新 · 当前第 {{ memoryCurrentRound || '…' }} 轮 <span class="text-muted/40">(会话 #{{ sessionId }})</span>
        </div>
       </div>
      </div>
    </Transition>

    <!-- 主体：聊天区 + 角色侧边栏 -->
    <div class="relative z-10 flex-1 flex overflow-hidden">

    <!-- 左侧边栏（角色 + 精彩瞬间） -->
    <Transition name="slide-left">
      <div
        v-if="showCharSidebar"
        class="hidden sm:flex flex-col flex-shrink-0 w-60 border-r border-border bg-bg/50 backdrop-blur-sm overflow-hidden"
      >
        <!-- 上：角色列表 -->
        <div class="flex flex-col border-b border-border/40 flex-shrink-0 overflow-hidden" style="max-height:50%">
          <div class="px-3 py-2.5 flex-shrink-0">
            <span class="text-[10px] text-muted font-medium tracking-widest uppercase">角色</span>
          </div>
          <div class="overflow-y-auto px-2 pb-2 space-y-1">
            <div
              v-for="ch in displayChars"
              :key="ch.id"
              class="group/card flex items-center gap-2.5 px-2 py-2.5 rounded-xl cursor-pointer transition-all"
              :class="ch._playing ? 'bg-amber-900/30 ring-1 ring-amber-500/50' : ch._speaking ? 'bg-accent/10' : 'hover:bg-panel/40'"
              @click="selectedChar = ch"
            >
              <!-- 头像 -->
              <div class="relative flex-shrink-0">
                <img v-if="ch.avatar_url" :src="ch.avatar_url" class="w-10 h-10 rounded-full object-cover ring-2" :class="ch._playing ? 'ring-amber-400/80 shadow-lg shadow-amber-500/20' : ch._speaking ? 'ring-accent/50' : 'ring-border/40'" />
                <div v-else class="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-sm text-accent font-bold ring-1 ring-border/40">{{ ch.name?.[0] }}</div>
                <span v-if="ch._playing" class="absolute -bottom-0.5 -right-0.5 text-[8px] leading-none bg-amber-500 rounded-full w-4 h-4 flex items-center justify-center ring-2 ring-bg">🎭</span>
                <span v-else-if="ch._speaking" class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full ring-1 ring-bg"></span>
                <span v-if="ch.personality_evolved && ch.personality_evolved.trim()" class="absolute -top-0.5 -right-0.5 text-[8px] leading-none bg-accent rounded-full w-4 h-4 flex items-center justify-center ring-2 ring-bg" title="性格/背景已随剧情演变">🌱</span>
              </div>
              <!-- 文字信息 + 扮演按钮 -->
              <div class="min-w-0 flex-1">
                <div class="text-xs font-semibold text-text truncate leading-tight">{{ ch.name }}</div>
                <div class="text-[11px] truncate leading-tight mt-0.5" :class="ch._playing ? 'text-amber-400 font-medium' : 'text-muted/70'">
                  {{ ch._playing ? '🎭 正在扮演' : ch.description?.slice(0, 18) }}
                </div>
              </div>
              <!-- 快速扮演按钮（hover 时出现，已扮演则隐藏） -->
              <button
                v-if="!ch._playing"
                class="flex-shrink-0 opacity-0 group-hover/card:opacity-100 transition-opacity text-[10px] px-1.5 py-0.5 rounded-md bg-amber-800/40 hover:bg-amber-700/60 text-amber-300 border border-amber-700/40"
                title="扮演此角色"
                @click.stop="playerCharId = ch.id"
              >扮演</button>
            </div>
          </div>
          <!-- 角色列表底部：插入新角色 -->
          <div class="px-2 pb-2 pt-1 flex-shrink-0">
            <button
              class="w-full text-[11px] py-1.5 rounded-lg border border-dashed border-border/50 text-muted/60 hover:border-accent/50 hover:text-accent transition-all"
              @click="openCharModal"
            >＋ 插入角色</button>
          </div>
        </div>

        <!-- 下：精彩瞬间时间轴 -->
        <div class="flex flex-col flex-1 min-h-0 overflow-hidden">
          <div class="px-3 py-2 flex-shrink-0 border-b border-border/30">
            <span class="text-[10px] text-muted font-medium tracking-widest uppercase">精彩瞬间</span>
          </div>
          <div v-if="!sidebarImages.length" class="flex-1 flex items-center justify-center px-3">
            <p class="text-[10px] text-muted/40 text-center leading-relaxed">生成实况后<br>将出现在这里</p>
          </div>
          <div v-else class="flex-1 overflow-y-auto px-2 py-2 space-y-2.5">
            <div
              v-for="img in sidebarImages"
              :key="img.id"
              class="group relative cursor-pointer rounded-xl overflow-hidden ring-1 transition-all"
              :class="bgImage === img.content ? 'ring-accent/70' : 'ring-border/30 hover:ring-accent/40'"
              @click="openFullscreen(img.content)"
            >
              <img
                :src="img.content"
                class="w-full object-cover block"
                style="aspect-ratio:16/9"
                loading="lazy"
              />
              <div class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all" />
              <!-- 删除按钮（左上角） -->
              <button
                class="absolute top-1.5 left-1.5 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] w-5 h-5 rounded-full bg-red-700/70 hover:bg-red-600 text-white flex items-center justify-center backdrop-blur-sm"
                title="删除此图"
                @click.stop="deleteSidebarImage(img)"
              >✕</button>
              <button
                class="absolute bottom-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] px-2 py-0.5 rounded-md bg-black/60 hover:bg-accent/80 text-white backdrop-blur-sm"
                :class="bgImage === img.content ? '!opacity-100 bg-accent/60' : ''"
                @click.stop="setBgImage(img.content)"
              >{{ bgImage === img.content ? '✓ 当前背景' : '设为背景' }}</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 移动端：顶部横滚角色条 -->
    <div v-if="showCharSidebar && displayChars.length" class="sm:hidden flex-shrink-0 overflow-x-auto border-b border-border/50 bg-bg/50 px-2 py-2">
      <div class="flex gap-2">
        <div
          v-for="ch in displayChars"
          :key="ch.id"
          class="flex items-center gap-1.5 px-2 py-1 rounded-full border text-xs flex-shrink-0 transition-all"
          :class="ch._speaking ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border/50 text-muted'"
        >
          <img v-if="ch.avatar_url" :src="ch.avatar_url" class="w-5 h-5 rounded-full object-cover" />
          <div v-else class="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center text-xs text-accent font-bold">{{ ch.name?.[0] }}</div>
          <span>{{ ch.name }}</span>
          <span v-if="ch._speaking" class="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
        </div>
      </div>
    </div>

    <!-- 主阅读区 + 输入栏 -->
    <div class="flex-1 flex flex-col min-w-0 relative">

    <!-- 聊天背景图 -->
    <div
      v-if="bgImage"
      class="absolute inset-0 z-0 pointer-events-none"
      :style="`background-image:url(${bgImage});background-size:cover;background-position:center`"
    >
      <div class="absolute inset-0" :style="`background-color:rgba(15,15,15,${bgOpacity / 100})`" />
    </div>

    <!-- 主阅读区 -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto py-8 space-y-7 relative z-10">

      <div v-if="loadingSession" class="text-center py-20 text-muted text-sm loading-dots">加载中</div>

      <template v-else>
        <div class="max-w-3xl mx-auto w-full space-y-7">
        <template v-for="item in displayItems" :key="item.id">

          <!-- ── 回合分隔线（与消息同级，受 space-y-7 控制间距）── -->
          <div v-if="item._newTurn" class="flex items-center gap-2 py-1 animate-fade-in">
            <div class="flex-1 h-px bg-gradient-to-r from-transparent via-amber-500/25 to-transparent" />
            <span class="text-[10px] text-amber-500/40 flex-shrink-0">⏳</span>
            <div class="flex-1 h-px bg-gradient-to-r from-transparent via-amber-500/25 to-transparent" />
          </div>

          <!-- ── 实况图卡片堆叠 ──────────────────────────────────────── -->
          <!-- pl-11 = 44px，与角色文字起始位置对齐（w-8 头像 + gap-3） -->
          <div v-if="item.kind === 'image_group'" class="pl-11 animate-fade-in">
            <div class="relative" style="max-width:340px">
              <!-- 卡片堆叠区（固定 16:9） -->
              <div class="relative" style="aspect-ratio:16/9">
                <!-- 背景卡（最多2张，模拟扇形堆叠） -->
                <div
                  v-for="(img, ii) in [...item.images].reverse().slice(1, 3)"
                  :key="img.id"
                  class="absolute inset-0 rounded-xl overflow-hidden"
                  :style="`transform:rotate(${(ii+1)*1.8}deg) translate(${(ii+1)*3}px,${-(ii+1)*2}px);opacity:${0.45-ii*0.15};z-index:${2-ii}`"
                >
                  <img :src="img.content" class="w-full h-full object-cover" loading="lazy" />
                </div>
                <!-- 当前卡（前景，可点击放大） -->
                <div
                  class="absolute inset-0 rounded-xl overflow-hidden shadow-2xl shadow-black/60 z-10 ring-1 ring-border/20 hover:ring-accent/40 transition-all cursor-pointer"
                  @click="openFullscreen(cardCurrentImg(item))"
                >
                  <img
                    :src="cardCurrentImg(item)"
                    class="w-full h-full object-cover"
                    loading="lazy"
                    alt="场景实况"
                  />
                </div>
              </div>
              <!-- 翻页导航（2张以上才显示） -->
              <div v-if="item.images.length > 1" class="flex items-center justify-between mt-2 px-0.5">
                <button
                  class="text-xs text-muted hover:text-text px-2.5 py-1 rounded-lg hover:bg-panel/40 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
                  :disabled="cardIdx(item) >= item.images.length - 1"
                  @click.stop="cardNav(item, 1)"
                >← 更早</button>
                <span class="text-xs text-muted/60">{{ cardIdx(item) + 1 }} / {{ item.images.length }}</span>
                <button
                  class="text-xs text-muted hover:text-text px-2.5 py-1 rounded-lg hover:bg-panel/40 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
                  :disabled="cardIdx(item) === 0"
                  @click.stop="cardNav(item, -1)"
                >更新 →</button>
              </div>
            </div>
          </div>

          <!-- ── 普通消息 ────────────────────────────────────────────── -->
          <div
            v-else
            :class="item.msg.role === 'user' ? 'flex justify-end items-start gap-2' : ''"
          >
            <!-- 用户消息 -->
            <template v-if="item.msg.role === 'user'">
              <div v-if="item.msg._hidden" />  <!-- 占位制造 turn 分界，不渲染 -->
              <div v-else-if="isAutoPlaceholder(item.msg)" class="flex justify-center py-2">
                <span class="text-[11px] text-muted/40 italic">{{ item.msg.content }}</span>
              </div>
              <div v-else class="group/umsg flex flex-col items-end gap-1">
                <div class="bg-accent/10 border border-accent/20 rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-base text-text/90">
                  {{ item.msg.content }}
                </div>
                <div class="flex items-center gap-2 opacity-0 group-hover/umsg:opacity-100 transition-opacity">
                  <span v-if="item.turn" class="text-[10px] text-muted/50 select-none">#{{ item.turn }}</span>
                  <button
                    class="text-[10px] text-red-400/60 hover:text-red-400 border border-red-700/30 hover:border-red-500/50 rounded px-1.5 py-0.5 transition-all"
                    @click="retractMessage(item.msg)"
                  >撤回</button>
                </div>
              </div>
              <div class="flex-shrink-0 w-8 h-8 rounded-full overflow-hidden ring-1 ring-amber-400/60" :title="msgPlayerChar(item.msg)?.name || '我'">
                <img v-if="msgPlayerChar(item.msg)?.avatar_url" :src="msgPlayerChar(item.msg).avatar_url" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full bg-purple-900/40 flex items-center justify-center text-xs text-purple-300 font-bold">{{ (msgPlayerChar(item.msg)?.name || '我')[0] }}</div>
              </div>
            </template>

            <!-- 系统通知（角色加入等） -->
            <template v-else-if="item.msg.role === 'system'">
              <div class="flex justify-center py-2 animate-fade-in">
                <span class="text-xs text-accent/70 bg-accent/5 border border-accent/20 rounded-full px-4 py-1">{{ item.msg.content }}</span>
              </div>
            </template>

            <!-- 单张 snapshot / 加载中占位 -->
            <template v-else-if="item.msg.role === 'snapshot' || item.msg.role === 'chat_image'">
              <div class="animate-fade-in pl-11" :class="item.msg.role === 'chat_image' ? 'max-w-sm' : 'max-w-md'">
                <div
                  v-if="item.msg.content === '__loading__'"
                  class="w-full rounded-xl bg-panel border border-border overflow-hidden flex flex-col items-center justify-center gap-1.5"
                  style="aspect-ratio:16/9"
                >
                  <span class="text-3xl opacity-20">✦</span>
                  <span class="text-muted text-xs loading-dots">实况生成中</span>
                </div>
                <div v-else-if="item.msg._failed" class="relative">
                  <img
                    :src="item.msg.content"
                    class="w-full rounded-xl shadow-2xl shadow-black/50 opacity-60 cursor-pointer"
                    alt="生图失败"
                    loading="lazy"
                    @click="openFullscreen(item.msg.content)"
                  />
                  <div class="absolute inset-0 flex flex-col items-center justify-center gap-1">
                    <span class="text-2xl">😿</span>
                    <span class="text-xs text-red-300/80 bg-black/40 rounded-full px-3 py-1 backdrop-blur-sm">妈的，没过</span>
                  </div>
                </div>
                <img
                  v-else
                  :src="item.msg.content"
                  class="w-full rounded-xl shadow-2xl shadow-black/50 cursor-pointer hover:ring-2 hover:ring-accent/50 transition-all"
                  alt="场景插图"
                  loading="lazy"
                  @click="openFullscreen(item.msg.content)"
                />
              </div>
            </template>

            <!-- 错误提示 + 重试 -->
            <template v-else-if="item.msg.role === 'error'">
              <div class="flex items-center gap-3 py-1.5">
                <span class="text-xs text-red-400/80">⚠ {{ item.msg.content }}</span>
                <button
                  class="text-xs text-red-400 border border-red-800/50 hover:bg-red-900/30 rounded-lg px-2.5 py-1 transition-all flex-shrink-0"
                  @click="retry(item.msg)"
                >重试</button>
              </div>
            </template>

            <!-- 故事开场（init 消息，仅展示，不渲染叙事格式） -->
            <template v-else-if="item.msg.role === 'init'">
              <div class="mx-1 rounded-xl border border-amber-700/25 bg-amber-950/15 px-4 py-3">
                <div class="text-[10px] font-semibold text-amber-400/50 tracking-widest uppercase mb-2">故事开场</div>
                <p class="text-sm text-text/65 leading-relaxed whitespace-pre-line">{{ item.msg.content.replace(/^【故事背景】\n?/, '').replace(/^【故事开场】\n?/, '') }}</p>
              </div>
            </template>

            <!-- AI 叙事 -->
            <template v-else>
              <div class="group">
                <NarrativeBlock :text="item.msg.content" :characters="characters" :role="item.msg.role" @character-click="onCharAvatarClick" @character-no-avatar="onCharClickInChat" />
                <div class="mt-3 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 pl-1">
                    <span v-if="item.turn" class="text-[10px] text-muted/50 select-none mr-0.5">#{{ item.turn }}</span>
                    <button
                      class="text-xs text-muted hover:text-accent border border-border hover:border-accent/40 rounded-lg px-2.5 py-1 transition-all"
                      :disabled="generatingImages.has(item.msg.id)"
                      @click="genChatImage(item.msg.id)"
                    >✦ 实况</button>
                    <button
                      class="text-xs text-muted hover:text-purple-400 border border-border hover:border-purple-400/40 rounded-lg px-2.5 py-1 transition-all"
                      :disabled="suggestLoading === item.msg.id"
                      @click="toggleSuggest(item.msg.id)"
                    >🎲 {{ suggestLoading === item.msg.id ? '生成中…' : '猜你喜欢' }}</button>
                    <button
                      class="text-xs text-muted hover:text-rose-400 border border-border hover:border-rose-400/40 rounded-lg px-2.5 py-1 transition-all"
                      :disabled="streaming"
                      @click="regenerate(item.msg)"
                    >↺ 重生成</button>
                  </div>
                  <!-- 猜你喜欢面板 -->
                  <div v-if="suggestMsgId === item.msg.id && suggestOptions.length" class="mt-2 animate-fade-in">
                    <div class="flex flex-wrap gap-2">
                      <button
                        v-for="(opt, oi) in suggestOptions"
                        :key="oi"
                        class="text-xs text-left px-3 py-2 rounded-xl border transition-all flex-1 min-w-[120px]"
                        :class="oi === 0
                          ? 'bg-purple-900/20 border-purple-600/40 text-purple-300 hover:bg-purple-900/40'
                          : oi === 1
                          ? 'bg-pink-900/20 border-pink-600/40 text-pink-300 hover:bg-pink-900/40'
                          : 'bg-cyan-900/20 border-cyan-600/40 text-cyan-300 hover:bg-cyan-900/40'"
                        @click="pickSuggestion(opt)"
                      >{{ oi + 1 }}. {{ opt }}</button>
                    </div>
                  </div>
                </div>
            </template>
          </div>

        </template>

        <!-- 流式输出中 -->
        <div v-if="streaming" class="animate-fade-in">
          <NarrativeBlock :text="streamBuffer" :characters="characters" role="assistant" @character-click="onCharAvatarClick" @character-no-avatar="onCharClickInChat" />
          <span class="inline-block w-0.5 h-4 bg-accent animate-pulse ml-1 align-middle mt-1" />
        </div>

        <div v-if="!messages.length && !streaming" class="text-center py-16 text-muted text-sm">
          输入你的行动或对话，开始故事……
        </div>
        </div><!-- end max-w-2xl -->
      </template>
    </div>

    <!-- 底部输入栏 -->
    <div class="relative z-10 flex-shrink-0 border-t border-border bg-bg/80 backdrop-blur-md px-4 py-3">
      <div class="max-w-3xl mx-auto">
        <!-- 输入框 -->
        <div class="flex gap-3 items-end">
          <textarea
            ref="inputEl"
            v-model="userInput"
            class="textarea flex-1 min-h-[2.5rem] max-h-40 resize-none text-sm py-2"
            :placeholder="inputPlaceholder"
            rows="1"
            :disabled="streaming"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoResize"
          />
          <!-- 当前扮演角色头像 -->
          <div v-if="playerCharAvatar" class="flex-shrink-0 self-end mb-0.5" :title="'正在扮演：' + (playerCharName || '')">
            <img :src="playerCharAvatar" class="w-8 h-8 rounded-full object-cover ring-2 ring-amber-400/70" />
          </div>
          <button
            class="btn-primary px-5 py-2 text-sm self-end"
            :disabled="!userInput.trim() || streaming"
            @click="sendMessage"
          >{{ streaming ? '…' : '发送' }}</button>
          <button
            class="btn px-3 py-2 text-sm self-end"
            :class="autoAdvancing ? 'bg-amber-500/20 text-amber-400 border-amber-500/40' : 'btn-ghost'"
            :disabled="streaming"
            :title="autoAdvancing ? '自动推进中…' : 'AI 代你行动并推进剧情'"
            @click="autoAdvance"
          >{{ autoAdvancing ? '⏳' : '▶' }}</button>
        </div>
      </div>
    </div>

    </div><!-- end 主阅读区+输入栏 -->
    </div><!-- end 主体flex容器 -->

    <!-- 角色详情卡片（横向布局：方形图在左，信息在右） -->
    <Transition name="fade">
      <div v-if="selectedChar" class="fixed inset-0 z-[90] flex items-center justify-center bg-black/75 backdrop-blur-sm px-4" @click.self="selectedChar = null">
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-row" style="max-height:85vh">

          <!-- 左：宽度固定，高度跟随右侧内容，图片 object-cover 填满不留空 -->
          <div class="relative flex-shrink-0 bg-black/30 overflow-hidden" style="width:300px">
            <img v-if="charPortraitImg" :src="charPortraitImg" class="absolute inset-0 w-full h-full object-cover cursor-pointer" style="object-position:center top" @click="openFullscreen(charPortraitImg)" />
            <div v-else class="absolute inset-0 flex items-center justify-center bg-accent/5">
              <span class="text-6xl font-bold text-accent/15">{{ selectedChar.name?.[0] }}</span>
            </div>
          </div>

          <!-- 右：信息 + 操作区，独立滚动 -->
          <div class="flex-1 flex flex-col overflow-hidden" style="max-height:85vh">
            <!-- 标题栏 -->
            <div class="flex items-center justify-between px-4 pt-3 pb-2 flex-shrink-0">
              <div class="flex-1 min-w-0 mr-2">
                <template v-if="charEditMode">
                  <input v-model="charEditForm.name" class="input py-0.5 text-base font-bold w-full" placeholder="角色名" />
                </template>
                <template v-else>
                  <h3 class="text-lg font-bold text-text leading-tight truncate">{{ selectedChar.name }}</h3>
                  <div v-if="selectedChar.id === playerCharId" class="text-[10px] text-amber-400 font-medium mt-0.5">🎭 当前扮演中</div>
                </template>
              </div>
              <div class="flex gap-1.5 flex-shrink-0">
                <button
                  v-if="!charEditMode"
                  class="w-7 h-7 rounded-full bg-panel border border-border text-muted hover:text-accent hover:border-accent/40 text-xs flex items-center justify-center transition-all"
                  title="编辑角色"
                  @click="startCharEdit"
                >✎</button>
                <button class="w-7 h-7 rounded-full bg-panel border border-border text-muted hover:text-text hover:border-accent/40 text-sm flex items-center justify-center transition-all" @click="selectedChar = null">✕</button>
              </div>
            </div>

            <!-- 信息滚动区 -->
            <div class="flex-1 overflow-y-auto px-4 pb-2 space-y-2 min-h-0">

              <!-- ── 编辑模式 ── -->
              <template v-if="charEditMode">
                <div class="space-y-2">
                  <div>
                    <label class="text-[11px] text-muted/70 font-medium mb-1 block">外貌 / 背景</label>
                    <textarea v-model="charEditForm.description" class="textarea text-sm min-h-20 w-full" placeholder="外貌、背景描述…" />
                  </div>
                  <div>
                    <label class="text-[11px] text-muted/70 font-medium mb-1 block">性格</label>
                    <textarea v-model="charEditForm.personality" class="textarea text-sm min-h-14 w-full" placeholder="性格特征…" />
                  </div>
                  <div>
                    <label class="text-[11px] text-muted/70 font-medium mb-1 block">别名（逗号分隔）</label>
                    <input v-model="charEditForm.aliases" class="input text-sm w-full" placeholder="例如：老王, 二狗, 狗哥" />
                  </div>
                  <div>
                    <label class="text-[11px] text-muted/70 font-medium mb-1 block">生图描述（用于头像生成）</label>
                    <textarea v-model="charEditForm.image_prompt" class="textarea text-sm min-h-14 w-full" placeholder="生图描述…" />
                  </div>
                </div>
              </template>

              <!-- ── 预览模式 ── -->
              <template v-else>
                <!-- 外貌 / 背景 -->
                <div class="rounded-xl bg-black/15 border border-border/30 px-3 py-2">
                  <div class="text-[11px] text-muted/60 font-medium mb-1">外貌 / 背景</div>
                  <p v-if="selectedChar.description" class="text-sm text-text/70 leading-relaxed whitespace-pre-line">{{ selectedChar.description }}</p>
                  <p v-else class="text-sm text-muted/30 italic">暂无</p>
                </div>

                <!-- 性格 -->
                <div class="rounded-xl bg-black/15 border border-border/30 px-3 py-2">
                  <div class="text-[11px] text-muted/60 font-medium mb-1">性格</div>
                  <p v-if="selectedChar.personality" class="text-sm text-text/70 leading-relaxed whitespace-pre-line">{{ selectedChar.personality }}</p>
                  <p v-else class="text-sm text-muted/30 italic">暂无</p>
                </div>

                <!-- 性格 / 背景演变（随剧情自动累积） -->
                <div v-if="selectedChar.personality_evolved && selectedChar.personality_evolved.trim()" class="rounded-xl bg-accent/8 border border-accent/30 px-3 py-2">
                  <div class="text-[11px] text-accent/90 font-medium mb-1 flex items-center gap-1">
                    <span>🌱 性格 / 背景演变</span>
                    <span class="text-[9px] text-muted/50 font-normal">随剧情发展</span>
                  </div>
                  <p class="text-sm text-accent2/80 leading-relaxed whitespace-pre-line">{{ selectedChar.personality_evolved }}</p>
                </div>

                <!-- 生图描述 -->
                <div class="rounded-xl bg-black/15 border border-border/30 px-3 py-2">
                  <div class="text-[11px] text-muted/60 font-medium mb-1">生图描述</div>
                  <p v-if="selectedChar.image_prompt" class="text-sm text-text/70 leading-relaxed whitespace-pre-line">{{ selectedChar.image_prompt }}</p>
                  <p v-else class="text-sm text-muted/30 italic">暂无</p>
                </div>

                <!-- 别名 -->
                <div class="rounded-xl bg-black/15 border border-border/30 px-3 py-2">
                  <div class="text-[11px] text-muted/60 font-medium mb-1">别名</div>
                  <p v-if="aliasDisplay(selectedChar.aliases || '')" class="text-sm text-accent2/70 leading-relaxed">{{ aliasDisplay(selectedChar.aliases) }}</p>
                  <p v-else class="text-sm text-muted/30 italic">暂无</p>
                </div>
              </template>

            </div>

            <!-- 底部操作栏 -->
            <div class="flex-shrink-0 px-4 pb-3 pt-2 border-t border-border/30 space-y-2">
              <!-- 编辑模式：保存/取消 -->
              <template v-if="charEditMode">
                <div class="flex gap-2">
                  <button class="flex-1 text-sm py-1.5 rounded-xl border border-accent/40 bg-accent/10 text-accent hover:bg-accent/20 transition-all font-medium" :disabled="charSaving" @click="saveCharEdit">
                    {{ charSaving ? '保存中…' : '✓ 保存' }}
                  </button>
                  <button class="text-sm px-4 py-1.5 rounded-xl border border-border text-muted hover:text-text transition-all" @click="charEditMode = false">取消</button>
                </div>
              </template>
              <!-- 正常模式：扮演 -->
              <template v-else>
                <div class="flex items-center gap-2 mb-2">
                  <label class="flex-1 text-center text-xs py-1.5 rounded-lg border border-dashed border-border/60 text-muted cursor-pointer hover:border-accent/50 transition-all relative overflow-hidden">
                    {{ charPortraitImg ? '🖼 换肖像' : '↑ 上传肖像' }}
                    <input v-if="!charPortraitUploading" type="file" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer" @change="onCharPortraitUpload($event, selectedChar)" />
                  </label>
                  <select v-model="genAvatarStyle" class="input text-xs py-1 w-20" :disabled="genAvatarLoading">
                    <option v-for="s in avatarStyleOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                  <button class="text-xs px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/8 text-accent/80 hover:bg-accent/15 whitespace-nowrap" :disabled="genAvatarLoading" @click="generateCharAvatar">{{ genAvatarLoading ? '…' : '✨ 生成' }}</button>
                </div>
                <div v-if="charPortraitMsg || genAvatarMsg" class="text-[10px] rounded px-3 py-1 mb-1 text-center" :class="(charPortraitMsg||genAvatarMsg).startsWith('✗')?'bg-red-900/30 text-red-400':'bg-green-900/30 text-green-400'">{{ charPortraitMsg || genAvatarMsg }}</div>
                <button
                  v-if="selectedChar.id !== playerCharId"
                  class="w-full text-sm py-2 rounded-xl border border-amber-500/50 bg-amber-900/20 text-amber-300 hover:bg-amber-800/30 transition-all font-medium"
                  @click="playerCharId = selectedChar.id; selectedChar = null"
                >🎭 扮演此角色</button>
                <div v-else class="text-center text-xs text-amber-400/80 bg-amber-900/15 border border-amber-500/20 rounded-xl py-2">🎭 当前正在扮演</div>
              </template>
            </div>
          </div>

        </div>
      </div>
    </Transition>

    <!-- ── 世界书编辑弹窗 ────────────────────────────────────────── -->
    <Transition name="fade">
      <div v-if="showWorldRules" class="fixed inset-0 z-[110] flex items-center justify-center bg-black/70 backdrop-blur-sm px-4" @click.self="showWorldRules = false">
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
          <!-- 头部 -->
          <div class="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
            <h3 class="font-bold text-sm">🌐 世界书</h3>
            <div class="flex gap-1 bg-panel rounded-lg p-0.5">
              <button
                v-for="t in worldRuleTabs"
                :key="t.key"
                class="text-xs px-3 py-1 rounded-md transition-all"
                :class="worldRuleTab === t.key ? 'bg-accent/20 text-accent' : 'text-muted hover:text-text'"
                @click="worldRuleTab = t.key"
              >{{ t.label }}</button>
            </div>
            <button class="text-muted hover:text-text text-lg leading-none ml-2" @click="showWorldRules = false">✕</button>
          </div>

          <!-- 内容区 -->
          <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">

            <!-- ── 故事设定 ── -->
            <template v-if="worldRuleTab === 'plot'">
              <div>
                <label class="text-xs text-muted block mb-1">标题</label>
                <input v-model="worldRuleForm.title" class="input text-sm w-full" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">概念</label>
                <textarea v-model="worldRuleForm.concept" class="textarea text-sm min-h-16 w-full" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">Vibe 标签（逗号分隔）</label>
                <input v-model="worldRuleForm.vibeStr" class="input text-sm w-full" placeholder="甜蜜, 悬疑, 奇幻" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">开场</label>
                <textarea v-model="worldRuleForm.opening" class="textarea text-sm min-h-24 w-full" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">背景设定</label>
                <textarea v-model="worldRuleForm.backstory" class="textarea text-sm min-h-24 w-full" />
              </div>
              <div>
                <label class="text-xs text-muted block mb-1">叙事视角</label>
                <select v-model="worldRuleForm.pov" class="input text-sm w-full">
                  <option value="3rd">第三人称</option>
                  <option value="2nd">第二人称</option>
                  <option value="1st">第一人称</option>
                </select>
              </div>
              <button class="btn-primary text-sm w-full py-2" :disabled="worldRuleSaving" @click="saveWorldRulePlot">
                {{ worldRuleSaving ? '保存中…' : '保存故事设定' }}
              </button>
            </template>

            <!-- ── 角色 ── -->
            <template v-if="worldRuleTab === 'chars'">
              <div v-for="(ch, i) in worldRuleChars" :key="ch.id" class="card !p-3 space-y-2">
                <div class="flex items-center gap-2">
                  <img v-if="ch.avatar_url" :src="ch.avatar_url" class="w-8 h-8 rounded-full object-cover" />
                  <span class="text-xs font-medium text-text">{{ ch.name || '未命名' }}</span>
                  <span v-if="ch.is_user" class="text-[10px] text-purple-400 bg-purple-900/30 px-1.5 py-0.5 rounded">用户</span>
                  <div class="flex-1" />
                  <button class="text-[10px] text-muted hover:text-text" @click="worldRuleChars[i]._fold = !worldRuleChars[i]._fold">
                    {{ ch._fold ? '展开' : '收起' }}
                  </button>
                </div>
                <template v-if="!ch._fold">
                  <input v-model="worldRuleChars[i].name" class="input text-xs w-full" placeholder="角色名" />
                  <textarea v-model="worldRuleChars[i].description" class="textarea text-xs min-h-16 w-full" placeholder="外貌/背景描述" />
                  <textarea v-model="worldRuleChars[i].personality" class="textarea text-xs min-h-16 w-full" placeholder="性格" />
                  <input v-model="worldRuleChars[i].aliasesStr" class="input text-xs w-full" placeholder="别名（逗号分隔）" />
                  <button class="text-xs px-3 py-1 rounded-lg bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-all"
                    :disabled="worldRuleSaving" @click="saveWorldRuleChar(ch, i)">
                    {{ ch._saving ? '保存中…' : '保存角色' }}
                  </button>
                </template>
              </div>
            </template>

            <!-- ── 世界书（Lorebook） ── -->
            <template v-if="worldRuleTab === 'lorebook'">
              <!-- 操作栏 -->
              <div class="flex gap-2 mb-3">
                <button class="text-xs px-3 py-1.5 rounded-lg border border-dashed border-amber-500/40 text-amber-300/70 hover:bg-amber-900/20 transition-all"
                  @click="triggerLorebookUpload"
                >📂 导入</button>
                <button class="text-xs px-3 py-1.5 rounded-lg border border-dashed border-accent/40 text-accent/70 hover:bg-accent/10 transition-all"
                  @click="addLorebookEntry"
                >＋ 新增条目</button>
                <input ref="lorebookFileInput" type="file" accept=".json" class="hidden" @change="onLorebookFilePicked" />
              </div>

              <!-- 快速新增条目表单（置顶，点「新增条目」即在此出现，无需翻到底部） -->
              <div v-if="showNewEntryForm" class="card !p-3 space-y-2 mb-3 border-amber-500/30">
                <input v-model="newEntry.keywordsStr" class="input text-xs w-full" placeholder="关键词（逗号分隔）" />
                <textarea v-model="newEntry.content" class="textarea text-xs min-h-20 w-full" placeholder="规则内容..." />
                <div class="flex gap-2">
                  <button class="text-xs px-3 py-1 rounded-lg bg-amber-700/30 text-amber-300 border border-amber-600/30 hover:bg-amber-700/40 transition-all flex-1"
                    :disabled="!newEntry.keywordsStr.trim() || !newEntry.content.trim()" @click="createQuickEntry">
                    创建条目
                  </button>
                  <button class="text-xs px-3 py-1 rounded-lg border border-border text-muted hover:text-text transition-all"
                    @click="showNewEntryForm = false">取消</button>
                </div>
              </div>

              <!-- 搜索：世界书名 + 条目关键词/内容（条目太多时用来筛选定位） -->
              <input
                v-model="lorebookSearch"
                class="input text-xs w-full mb-2"
                placeholder="🔍 筛选：世界书名 / 关键词 / 规则内容…"
              />

              <!-- 空状态 -->
              <div v-if="!filteredLorebooks.length" class="text-center py-8 text-muted text-sm">
                <p v-if="worldRuleLorebooks.length">没有匹配的世界书</p>
                <template v-else>
                  <p>暂无世界书条目</p>
                  <p class="text-xs mt-1 opacity-60">上传 SillyTavern 世界书 JSON 或手动添加条目</p>
                </template>
              </div>

              <!-- Lorebook 列表 -->
              <div v-for="lb in filteredLorebooks" :key="lb.id" class="card !p-3 space-y-2">
                <div class="flex items-center gap-2 cursor-pointer" @click="lb._fold = !lb._fold">
                  <button class="w-7 h-7 flex items-center justify-center rounded-md bg-accent/15 border border-accent/40 text-accent text-lg leading-none hover:bg-accent/25 flex-shrink-0 transition-colors">
                    {{ lb._fold ? '▶' : '▼' }}
                  </button>
                  <span class="text-xs font-medium text-text truncate">📖 {{ lb.title }}</span>
                  <span class="text-[10px] text-muted/50 flex-shrink-0">{{ lb.entries?.length || 0 }}条</span>
                  <div class="flex-1" />
                  <button class="text-xs px-2 py-0.5 rounded-md border border-emerald-500/30 text-emerald-300/70 hover:bg-emerald-900/25 hover:text-emerald-200 flex-shrink-0 transition-all" title="导出这本世界书为 JSON（可分享/再导入）" @click.stop="exportLorebook(lb)">📥 导出</button>
                  <button class="text-xs px-2 py-0.5 rounded-md border border-red-500/30 text-red-400/70 hover:bg-red-900/30 hover:text-red-300 flex-shrink-0 transition-all" title="删除整本世界书" @click.stop="deleteLorebook(lb)">🗑 删除</button>
                </div>
                <!-- 折叠时不显示条目；但只要在搜索就强制展开，让命中的条目能被看到 -->
                <template v-if="!lb._fold || lorebookSearch.trim()">
                  <div v-for="(entry, ei) in lb.entries" :key="ei" v-show="showEntry(lb, entry)" class="border-t border-border/30 pt-2 space-y-1.5">
                    <div class="flex items-center gap-1">
                      <button class="w-6 h-6 flex items-center justify-center rounded-md bg-accent/10 border border-accent/30 text-accent text-base leading-none hover:bg-accent/20 flex-shrink-0 transition-colors" @click="entry._fold = !entry._fold">
                        {{ entry._fold ? '▶' : '▼' }}
                      </button>
                      <input v-model="lb.entries[ei].keywordsStr" class="input text-xs flex-1" placeholder="关键词（逗号分隔）"
                        @focus="entry._fold = false" />
                      <button class="text-[10px] text-red-400/60 hover:text-red-400 px-1 flex-shrink-0" @click="lb.entries.splice(ei, 1)">✕</button>
                    </div>
                    <template v-if="!entry._fold">
                      <textarea v-model="lb.entries[ei].content" class="textarea text-xs min-h-16 w-full" placeholder="规则内容" />
                    </template>
                  </div>
                  <div class="flex gap-2">
                    <button class="text-xs px-3 py-1 rounded-lg bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-all flex-1"
                      :disabled="worldRuleSaving" @click="saveWorldRuleLorebook(lb)">
                      {{ lb._saving ? '保存中…' : '保存' }}
                    </button>
                    <button class="text-xs px-3 py-1 rounded-lg bg-red-900/20 text-red-400/70 border border-red-700/30 hover:bg-red-900/30 transition-all"
                      @click="deleteLorebook(lb)">
                      删除
                    </button>
                  </div>
                </template>
              </div>

            </template>

            <!-- ── 系统提示词 ── -->
            <template v-if="worldRuleTab === 'prompts'">
              <div class="flex gap-2 mb-3">
                <select v-model="promptMode" class="input text-xs w-24" @change="loadPromptList">
                  <option v-for="m in promptModes" :key="m" :value="m">经典</option>
                </select>
                <select v-model="selectedPrompt" class="input text-xs flex-1" @change="loadPromptContent">
                  <option v-for="p in promptList" :key="p" :value="p">{{ promptLabels[p] || p }}</option>
                </select>
              </div>
              <textarea
                v-if="selectedPrompt"
                v-model="promptContent"
                class="textarea text-xs min-h-64 w-full font-mono"
                placeholder="加载中…"
              />
              <p v-else class="text-center py-12 text-muted text-sm">请选择一个提示词文件</p>
              <button v-if="selectedPrompt" class="btn-primary text-sm w-full py-2 mt-3" :disabled="promptSaving" @click="savePrompt">
                {{ promptSaving ? '保存中…' : '保存提示词' }}
              </button>
            </template>

          </div>
        </div>
      </div>
    </Transition>

    <!-- 导出 GG 卡弹窗（屏幕居中） -->
    <Transition name="fade">
      <div
        v-if="showExport"
        class="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
        @click.self="showExport = false"
      >
        <div class="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
          <!-- 头部 -->
          <div class="flex items-center justify-between px-5 py-3.5 border-b border-border flex-shrink-0">
            <div>
              <span class="font-semibold text-sm text-text">🃏 导出 GG 卡</span>
              <span class="text-[11px] text-muted/60 ml-2">把这段故事打包成一张图，发给朋友即可接着玩</span>
            </div>
            <button class="text-muted hover:text-text text-xl leading-none" @click="showExport = false">×</button>
          </div>

          <!-- 内容 -->
          <div class="flex-1 overflow-y-auto px-5 py-4 space-y-5">

            <!-- 卡面 -->
            <section>
              <div class="export-sec-title">🖼 卡面 <span class="text-muted/50 font-normal">（这张图的样子）</span></div>
              <div class="grid grid-cols-4 gap-2">
                <button
                  type="button"
                  class="relative rounded-lg overflow-hidden ring-2 transition-all aspect-square"
                  :class="exCardFace === 'base' ? 'ring-accent' : 'ring-border/40 hover:ring-accent/40'"
                  @click="exCardFace = 'base'"
                >
                  <img :src="baseFaceUrl" class="w-full h-full object-cover" />
                  <span class="absolute bottom-0 inset-x-0 text-[9px] text-white/90 bg-black/50 py-0.5 text-center">默认</span>
                </button>
                <button
                  v-for="img in sidebarImages"
                  :key="img.id"
                  type="button"
                  class="relative rounded-lg overflow-hidden ring-2 transition-all aspect-square"
                  :class="exCardFace === img.content ? 'ring-accent' : 'ring-border/40 hover:ring-accent/40'"
                  @click="exCardFace = img.content"
                >
                  <img :src="img.content" class="w-full h-full object-cover" />
                </button>
              </div>
            </section>

            <!-- 角色卡部分 -->
            <section>
              <div class="export-sec-title">🎭 角色卡部分</div>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="export-pill" :class="exCharText ? 'export-pill-on' : ''" @click="exCharText = !exCharText">角色卡设计</button>
                <button type="button" class="export-pill" :class="exCharImages ? 'export-pill-on' : ''" @click="exCharImages = !exCharImages">角色卡图片</button>
                <button type="button" class="export-pill" :class="exCharEvolution ? 'export-pill-on' : ''" @click="exCharEvolution = !exCharEvolution">角色性格演变 🌱</button>
              </div>
            </section>

            <!-- 聊天轮次 -->
            <section>
              <div class="export-sec-title">💬 聊天轮次 <span class="text-muted/50 font-normal">（导出到第几回合）</span></div>
              <div v-if="maxTurn > 0" class="flex items-center gap-3">
                <input
                  type="range" min="1" :max="maxTurn" v-model.number="exRoundLimit"
                  class="flex-1 h-1.5 accent-accent cursor-pointer"
                />
                <div class="flex items-center gap-1 text-xs text-muted flex-shrink-0">
                  <span>#</span>
                  <input
                    type="number" min="1" :max="maxTurn" v-model.number="exRoundLimit"
                    class="w-16 bg-panel/60 border border-border/50 rounded px-2 py-1 text-text text-center"
                    @change="clampRound"
                  />
                  <span class="text-muted/50">/ {{ maxTurn }}</span>
                </div>
              </div>
              <p v-else class="text-xs text-muted/50">暂无对话记录</p>
            </section>

            <!-- 记忆 -->
            <section class="flex items-center justify-between">
              <div class="export-sec-title mb-0">🧠 记忆 <span class="text-muted/50 font-normal">（当前全部记忆槽位）</span></div>
              <button
                type="button"
                class="relative w-11 h-6 rounded-full transition-colors flex-shrink-0"
                :class="exMemory ? 'bg-accent' : 'bg-border/60'"
                @click="exMemory = !exMemory"
              >
                <span class="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform" :class="exMemory ? 'translate-x-5' : ''"></span>
              </button>
            </section>

            <!-- 世界书 -->
            <section>
              <div class="export-sec-title">🌐 世界书</div>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="export-pill" :class="exLoreOriginal ? 'export-pill-on' : ''" @click="exLoreOriginal = !exLoreOriginal">原设定</button>
                <button type="button" class="export-pill" :class="exLoreRules ? 'export-pill-on' : ''" @click="exLoreRules = !exLoreRules">规则演进 📜</button>
                <button type="button" class="export-pill" :class="exLoreMounted ? 'export-pill-on' : ''" @click="exLoreMounted = !exLoreMounted">挂载世界书</button>
              </div>
            </section>
          </div>

          <!-- 底部：导出按钮 -->
          <div class="px-5 py-4 border-t border-border flex-shrink-0">
            <button
              class="w-full py-3 rounded-xl text-white font-semibold text-sm bg-gradient-to-r from-fuchsia-600 to-violet-600 hover:from-fuchsia-500 hover:to-violet-500 shadow-lg shadow-violet-900/30 ring-1 ring-white/10 transition-all disabled:opacity-60"
              :disabled="exportingCard"
              @click="doExportCard"
            >{{ exportingCard ? '正在打包…' : '🃏 生成并下载 GG 卡' }}</button>
            <p class="text-[10px] text-muted/40 text-center mt-2">数据经 AES-256 加密，仅 GalGame 能读取</p>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 全屏图片预览 -->
    <Transition name="fade">
      <div v-if="fullscreenImg" class="fixed inset-0 z-[100] bg-black/95 flex items-center justify-center backdrop-blur-sm" @click="fullscreenImg = null">
        <button class="absolute top-4 right-4 text-white/60 hover:text-white text-2xl z-10">✕</button>
        <img :src="fullscreenImg" class="max-w-[95vw] max-h-[95vh] object-contain rounded-lg shadow-2xl" @click.stop />
      </div>
    </Transition>

    <!-- 世界書快速搜尋 (Ctrl+F) -->
    <LorebookSearch ref="lorebookSearchRef" :plot-id="plot?.id" />

  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import NarrativeBlock from '../components/NarrativeBlock.vue'
import LorebookSearch from '../components/LorebookSearch.vue'

const route = useRoute()
const router = useRouter()
const sessionId = ref(Number(route.params.sessionId))

const plot = ref(null)
const characters = ref([])
const messages = ref([])
const bgImage = ref('')
const bgOpacity = ref(Number(localStorage.getItem('bgOpacity') || 40))

watch(bgOpacity, (v) => localStorage.setItem('bgOpacity', v))
const playerCharId = ref(null)    // 当前扮演的角色 ID
const loadingSession = ref(true)
const streaming = ref(false)
const autoAdvancing = ref(false)  // 自动推进模式
const showTurnSep = ref(false)    // 回合分隔线开关
const streamBuffer = ref('')
const userInput = ref('')
const generatingImages = ref(new Set())  // 正在生成的 messageId 集合
const scrollEl = ref(null)
const inputEl = ref(null)
const showMemory = ref(false)
const memorySlots = ref({})
const memoryLoading = ref(false)
const memoryCurrentRound = ref(0)
const memoryUpdatedAtRound = ref(0)
const memoryInterval = ref(10)
const memoryError = ref(false)
const mode = ref('classic')
const showCharSidebar = ref(true)  // 角色侧边栏
const fullscreenImg = ref(null)    // 全屏预览图片URL
const exportingCard = ref(false)  // Galgame 卡写入中

// ── 导出 GG 卡弹窗状态 ──────────────────────────────────────────
const baseFaceUrl = '/api/galgame-card/base-face'   // 内置默认卡面预览
const showExport = ref(false)
const exCardFace = ref('base')        // 'base' 或某张实况图的 content URL
const exCharText = ref(true)
const exCharImages = ref(true)
const exCharEvolution = ref(true)
const exMemory = ref(true)
const exLoreOriginal = ref(true)
const exLoreRules = ref(true)
const exLoreMounted = ref(true)
const exRoundLimit = ref(0)

// 最大对话回合（与 displayItems 的 turn 一致）
const maxTurn = computed(() => {
  let t = 0
  for (const m of messages.value) if (m.role === 'user') t++
  return t
})

function clampRound() {
  const mx = maxTurn.value
  let v = Number(exRoundLimit.value) || 1
  exRoundLimit.value = Math.max(1, Math.min(mx, v))
}

function openExport() {
  // 默认：卡面选已有实况图中最新一张，否则用 BASE
  exCardFace.value = sidebarImages.value[0]?.content || 'base'
  exRoundLimit.value = maxTurn.value
  showExport.value = true
}
const selectedChar = ref(null)     // 角色详情卡片
const charPortraitUploading = ref(false)
const charPortraitMsg = ref('')   // 上传后的状态提示
let charPortraitMsgTimer = null

function showCharMsg(msg, isError = false) {
  charPortraitMsg.value = (isError ? '✗ ' : '✓ ') + msg
  if (charPortraitMsgTimer) clearTimeout(charPortraitMsgTimer)
  charPortraitMsgTimer = setTimeout(() => { charPortraitMsg.value = '' }, 3000)
}

// 当前预览角色的肖像 URL
const charPortraitImg = computed(() =>
  selectedChar.value ? (selectedChar.value.avatar_url || selectedChar.value.image_url || '') : ''
)

// 描述/性格折叠状态（selectedChar 变化时重置）
const showFullDesc = ref(false)
const showFullPersonality = ref(false)

function aliasDisplay(raw) {
  try { return JSON.parse(raw || '[]').join('、') } catch { return raw || '' }
}

// 角色详情编辑态
const charEditMode = ref(false)
const charEditForm = ref({ name: '', description: '', personality: '', first_mes: '', aliases: '' })
const charSaving = ref(false)

// 角色生图（per-character 状态，避免多角色弹窗串扰）
const genAvatarStyle = ref('')
// charId → { loading, msg }
const genAvatarState = ref({})
const avatarStyleOptions = [
  { key: '',          label: '随机' },
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
// 当前弹窗角色的生图状态（computed shortcut）
const genAvatarLoading = computed(() => !!genAvatarState.value[selectedChar.value?.id]?.loading)
const genAvatarMsg = computed(() => genAvatarState.value[selectedChar.value?.id]?.msg || '')

async function generateCharAvatar() {
  const charId = selectedChar.value?.id
  if (!charId || genAvatarLoading.value) return
  genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: true, msg: '' } }
  try {
    const { task_id } = await apiFetch(`/characters/${charId}/regenerate-avatar`, {
      method: 'POST',
      body: JSON.stringify({ image_style: genAvatarStyle.value }),
    })
    // 轮询任务完成（关闭弹窗不影响，charId 是闭包变量）
    let attempts = 0
    const poll = setInterval(async () => {
      attempts++
      if (attempts > 60) {
        clearInterval(poll)
        genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: false, msg: '✗ 超时，请稍后重试' } }
        return
      }
      try {
        const t = await apiFetch(`/tasks/${task_id}`)
        if (t.status === 'completed') {
          clearInterval(poll)
          // 无论弹窗是否打开，都更新 characters 数组
          const c = characters.value.find(x => x.id === charId)
          if (c) c.avatar_url = t.result_url
          // 如果弹窗仍在显示该角色，同步更新
          if (selectedChar.value?.id === charId) selectedChar.value = { ...selectedChar.value, avatar_url: t.result_url }
          genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: false, msg: '✓ 生成完成' } }
          setTimeout(() => {
            genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: false, msg: '' } }
          }, 3000)
        } else if (t.status === 'failed') {
          clearInterval(poll)
          genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: false, msg: '✗ 生成失败，请重试' } }
        }
      } catch {}
    }, 3000)
  } catch (e) {
    genAvatarState.value = { ...genAvatarState.value, [charId]: { loading: false, msg: '✗ ' + (e.message || '请求失败') } }
  }
}

function startCharEdit() {
  const c = selectedChar.value
  charEditForm.value = {
    name: c.name || '',
    description: c.description || '',
    personality: c.personality || '',
    image_prompt: c.image_prompt || '',
    first_mes: c.first_mes || '',
    aliases: (() => { try { return JSON.parse(c.aliases || '[]').join('，') } catch { return c.aliases || '' } })(),
  }
  charEditMode.value = true
}

async function saveCharEdit() {
  if (!selectedChar.value) return
  charSaving.value = true
  try {
    const updates = { ...charEditForm.value }
    // 别名转为 JSON 数组
    if (updates.aliases) {
      updates.aliases = JSON.stringify(
        updates.aliases.split(/[,，]/).map(s => s.trim()).filter(Boolean)
      )
    }
    await apiFetch(`/characters/${selectedChar.value.id}`, { method: 'PUT', body: JSON.stringify(updates) })
    _applyCharUpdates(selectedChar.value.id, updates)
    charEditMode.value = false
    showCharMsg('已保存')
  } catch (e) {
    showCharMsg('保存失败：' + e.message, true)
  } finally {
    charSaving.value = false
  }
}
watch(selectedChar, () => {
  showFullDesc.value = false
  showFullPersonality.value = false
  charPortraitMsg.value = ''
  charEditMode.value = false
})

// 插入角色弹窗
const showCharModal = ref(false)
const insertingChar = ref(false)
const autofilling = ref(false)
const matchCharTargetInModal = ref(null)  // 弹窗内匹配目标角色id

async function confirmMatchInModal() {
  const char = characters.value.find(c => c.id === matchCharTargetInModal.value)
  if (!char) return
  const alias = newChar.value.name.trim()
  try {
    const existingAliases = (() => { try { return JSON.parse(char.aliases || '[]') } catch { return [] } })()
    if (!existingAliases.includes(alias)) existingAliases.push(alias)
    await apiFetch(`/characters/${char.id}`, {
      method: 'PUT',
      body: JSON.stringify({ aliases: JSON.stringify(existingAliases) }),
    })
    const updated = await apiFetch(`/plots/${plot.value.id}`)
    characters.value = updated.characters || []
    showCharModal.value = false
    matchCharTargetInModal.value = null
    newChar.value = { name: '', description: '', personality: '', avatarMode: 'upload', avatarPreview: '', avatarFile: null, image_prompt: '', image_style: '' }
  } catch (e) {
    console.error('匹配失败:', e)
  }
}

// 有头像的角色 → 打开角色详情卡片
function onCharAvatarClick(name) {
  const char = characters.value.find(c => c.name === name)
  if (char) selectedChar.value = char
}

// 无头像的角色 → 新增或匹配
function onCharClickInChat(name) {
  const exists = characters.value.some(c => c.name === name)
  if (exists) {
    const char = characters.value.find(c => c.name === name)
    const alias = prompt(`将匹配为【${char.name}】，输入该角色在对话中使用的别名（点取消放弃）：`, '')
    if (alias === null) return
    const aliasTrimmed = alias.trim()
    if (aliasTrimmed) {
      try {
        const existingAliases = (() => { try { return JSON.parse(char.aliases || '[]') } catch { return [] } })()
        if (!existingAliases.includes(aliasTrimmed)) existingAliases.push(aliasTrimmed)
        apiFetch(`/characters/${char.id}`, {
          method: 'PUT',
          body: JSON.stringify({ aliases: JSON.stringify(existingAliases) }),
        }).then(async () => {
          const updated = await apiFetch(`/plots/${plot.value.id}`)
          characters.value = updated.characters || []
        })
      } catch {}
    }
    return
  }
  // 角色不存在 → 预填名字，打开新增弹窗
  newChar.value = { name, description: '', personality: '', avatarMode: 'upload', avatarPreview: '', avatarFile: null, image_prompt: '', image_style: '' }
  showCharModal.value = true
}

const fileInputRef = ref(null)
const newChar = ref({
  name: '', description: '', personality: '',
  avatarMode: 'upload',   // 'upload' | 'generate'
  avatarPreview: '',       // base64 data URI preview
  avatarFile: null,        // File object for upload
  image_prompt: '',
  image_style: '',
})

const canInsertChar = computed(() => {
  if (!newChar.value.name.trim()) return false
  if (newChar.value.avatarMode === 'upload') return !!newChar.value.avatarFile
  if (newChar.value.avatarMode === 'generate') return !!newChar.value.image_prompt.trim()
  return false
})

// 猜你喜欢
const suggestMsgId = ref(null)
const suggestOptions = ref([])
const suggestLoading = ref(null)  // 正在加载的消息 id

let bgPollTimer = null
let chatImgPollTimers = {}               // messageId → intervalId

/**
 * 把消息列表转为"展示单元"：
 * 同一 ref_message_id 的连续 chat_image 消息合并为 image_group（卡片堆叠）。
 * 其余消息保持原样作为 { kind:'msg', msg } 单元。
 */
const displayItems = computed(() => {
  const result = []
  const msgs = messages.value
  let i = 0
  let turnCounter = 0
  let lastTurnInResult = null
  while (i < msgs.length) {
    const msg = msgs[i]
    if (msg.role === 'user') turnCounter++
    const turn = (msg.role === 'user' || msg.role === 'assistant') ? turnCounter : null
    const _newTurn = showTurnSep.value && turn !== null && turn !== lastTurnInResult && lastTurnInResult !== null
    if (turn !== null) lastTurnInResult = turn
    if (msg.role === 'chat_image' && msg.content !== '__loading__') {
      let refId = null
      try { refId = JSON.parse(msg.metadata || '{}').ref_message_id } catch {}
      const group = [msg]
      let j = i + 1
      while (j < msgs.length && msgs[j].role === 'chat_image' && msgs[j].content !== '__loading__') {
        let nextRefId = null
        try { nextRefId = JSON.parse(msgs[j].metadata || '{}').ref_message_id } catch {}
        if (nextRefId !== refId) break
        group.push(msgs[j])
        j++
      }
      if (group.length >= 1) {
        result.push({ kind: 'image_group', images: group, id: `grp_${msg.id}`, _newTurn })
        i = j
      } else {
        result.push({ kind: 'msg', msg, id: msg.id, turn, _newTurn })
        i++
      }
    } else {
      result.push({ kind: 'msg', msg, id: msg.id, turn, _newTurn })
      i++
    }
  }
  return result
})

// 当前扮演角色的头像（用于输入栏旁的头像）
const userAvatar = computed(() => {
  if (playerCharId.value) {
    return characters.value.find(c => c.id === playerCharId.value)?.avatar_url || ''
  }
  return characters.value.find(c => c.is_user)?.avatar_url || ''
})

const playerCharAvatar = computed(() => {
  const pc = characters.value.find(c => c.id === playerCharId.value)
  return pc?.avatar_url || ''
})

const playerCharName = computed(() => {
  const pc = characters.value.find(c => c.id === playerCharId.value)
  return pc?.name || ''
})

const inputPlaceholder = computed(() => {
  const name = playerCharName.value
  return name ? `以 ${name} 的身份说话…（Enter 发送，Shift+Enter 换行）` : '你的行动或话语…（Enter 发送，Shift+Enter 换行）'
})

const primaryChar = computed(() => characters.value.find(c => !c.is_user) || null)

/** 获取某条用户消息发送时扮演的角色对象（用于该轮次的头像显示） */
function msgPlayerChar(msg) {
  if (!msg) return null
  let meta = {}
  try { meta = JSON.parse(msg.metadata || '{}') } catch {}
  const pcId = meta.player_character_id
  if (pcId) return characters.value.find(c => c.id === pcId) || null
  // fallback: is_user character
  return characters.value.find(c => c.is_user) || null
}

/** 检测自动推进的占位 user 消息（格式：以（开头的中文括号文本）） */
function isAutoPlaceholder(msg) {
  if (!msg || msg.role !== 'user') return false
  const c = (msg.content || '').trim()
  return c.startsWith('（') && c.endsWith('）') && c.length < 30
}

/** 从历史消息中恢复玩家角色选择（上次对话选择的角色） */
function restorePlayerChar() {
  const userMsgs = [...messages.value].filter(m => m.role === 'user').reverse()
  for (const msg of userMsgs) {
    let meta = {}
    try { meta = JSON.parse(msg.metadata || '{}') } catch {}
    if (meta.player_character_id) {
      playerCharId.value = meta.player_character_id
      return
    }
  }
  // fallback: use is_user character
  const isUserChar = characters.value.find(c => c.is_user)
  if (isUserChar) playerCharId.value = isUserChar.id
}

// ── 实况图卡片堆叠状态 ──────────────────────────────────────────────
const cardGroupIdx = ref({})   // { groupId: currentIndex }  0 = 最新

function cardIdx(item) {
  return cardGroupIdx.value[item.id] ?? 0
}

function cardCurrentImg(item) {
  // images 按时间顺序（旧→新），reversed 后 index 0 = 最新
  const reversed = [...item.images].reverse()
  return reversed[cardIdx(item)]?.content ?? ''
}

function cardNav(item, delta) {
  const cur = cardIdx(item)
  const next = Math.max(0, Math.min(item.images.length - 1, cur + delta))
  cardGroupIdx.value = { ...cardGroupIdx.value, [item.id]: next }
}

/** 所有已完成的图片消息，按时间倒序排列（最新在最上） */
const sidebarImages = computed(() =>
  messages.value.filter(m =>
    (m.role === 'snapshot' || m.role === 'chat_image') &&
    m.content && m.content !== '__loading__' && !m._failed
  ).reverse()
)

/**
 * 从消息文本中提取所有 **角色名**，返回对应的角色对象数组（用于多头像显示）
 * 也会匹配纯文本中的角色名提及（如"雪儿 盯在那"中的"雪儿"）
 */
function speakingChars(text) {
  if (!text || !characters.value.length) return []
  const seen = new Set()
  const result = []

  // 排除当前玩家角色（用户扮演的角色不出现在 AI 消息的头像组里）
  const isPlayerChar = (c) => c.id === playerCharId.value || (!playerCharId.value && !!c.is_user)

  // 1. 先匹配 **角色名** 格式
  const boldRe = /\*\*(.+?)\*\*/g
  let m
  while ((m = boldRe.exec(text)) !== null) {
    const name = m[1]
    if (seen.has(name)) continue
    seen.add(name)
    const ch = characters.value.find(c => c.name === name && !c.is_user && !isPlayerChar(c))
    if (ch) result.push(ch)
  }

  // 2. 如果没匹配到 **角色名**，回退到纯文本角色名扫描
  if (!result.length) {
    for (const ch of characters.value) {
      if (ch.is_user || isPlayerChar(ch) || seen.has(ch.name)) continue
      if (text.includes(ch.name)) {
        seen.add(ch.name)
        result.push(ch)
      }
    }
  }
  return result
}

/** 所有角色列表，带 _speaking / _playing 标记（用于侧边栏显示） */
const displayChars = computed(() => {
  return characters.value.map(c => ({
    ...c,
    _speaking: !c.is_user && messages.value.slice(-3).some(m =>
      m.role === 'assistant' && m.content?.includes(c.name)
    ),
    _playing: c.id === playerCharId.value || (!playerCharId.value && !!c.is_user),
  }))
})

/** 提取某个角色的所有图片消息（snapshot/chat_image，按时间排序，去重） */
function charImages(name) {
  const seen = new Set()
  return messages.value
    .filter(m =>
      (m.role === 'snapshot' || m.role === 'chat_image') &&
      m.content && !m.content.startsWith('__') && !m.content.startsWith('/gen_failed') &&
      !seen.has(m.content)
    )
    .filter(m => { seen.add(m.content); return true })
    .filter(m => {
      // 查找该图片附近是否有该角色名出现
      const idx = messages.value.indexOf(m)
      const context = messages.value.slice(Math.max(0, idx - 2), idx + 3)
      return context.some(cm => cm.content?.includes(name))
    })
    .slice(-8) // 最多 8 张
    .reverse()
}

function openFullscreen(url) {
  fullscreenImg.value = url
}

async function doExportCard() {
  if (exportingCard.value) return
  clampRound()
  exportingCard.value = true
  try {
    const res = await fetch('/api/galgame-card/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        card_face: exCardFace.value,
        include_char_text: exCharText.value,
        include_char_images: exCharImages.value,
        include_char_evolution: exCharEvolution.value,
        round_limit: maxTurn.value > 0 ? exRoundLimit.value : null,
        include_memory: exMemory.value,
        include_lore_original: exLoreOriginal.value,
        include_lore_rules: exLoreRules.value,
        include_lore_mounted: exLoreMounted.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `导出失败 (${res.status})`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // 从 Content-Disposition 提取文件名
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename\*=(?:UTF-8''|)(.+?)(?:;|$)/i)
        || disposition.match(/filename="?(.+?)"?$/i)
    a.download = match ? decodeURIComponent(match[1]) : `${plot.value?.title || 'galgame'}_galgamecard.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    showExport.value = false
  } catch (e) {
    alert('写入 Galgame 卡失败：' + e.message)
  } finally {
    exportingCard.value = false
  }
}

async function deleteSidebarImage(img) {
  if (!confirm('删除这张实况图？'))
    return
  try {
    // 如果是数字 ID（服务端消息），调 API 删除
    if (typeof img.id === 'number') {
      await apiFetch(`/sessions/${sessionId.value}/messages/${img.id}`, { method: 'DELETE' })
    }
    // 从本地消息列表移除
    const idx = messages.value.findIndex(m => m.id === img.id)
    if (idx >= 0) messages.value.splice(idx, 1)
  } catch (e) {
    alert('删除失败：' + e.message)
  }
}

/** 更新 characters 数组中的角色，并同步 selectedChar */
function _applyCharUpdates(charId, updates) {
  const c = characters.value.find(x => x.id === charId)
  if (c) Object.assign(c, updates)
  if (selectedChar.value?.id === charId) {
    selectedChar.value = { ...selectedChar.value, ...updates }
  }
}

async function onCharPortraitUpload(event, char) {
  const file = event.target.files?.[0]
  if (!file || !char) return
  event.target.value = ''
  charPortraitUploading.value = true
  const reader = new FileReader()
  reader.onload = async () => {
    try {
      const b64 = reader.result
      // PNG 先尝试酒馆卡解析
      if (file.type === 'image/png' || file.name.endsWith('.png')) {
        const res = await fetch('/api/characters/parse-tavern-card', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: b64 }),
        })
        const parsed = await res.json()
        if (parsed.is_tavern_card) {
          // 更新角色所有字段
          const updates = { avatar_url: parsed.image_url, image_url: parsed.image_url, reference_image: parsed.image_url }
          if (parsed.name && !char.name) updates.name = parsed.name
          if (parsed.description) updates.description = parsed.description
          if (parsed.personality) updates.personality = parsed.personality
          if (parsed.first_mes) updates.first_mes = parsed.first_mes
          await apiFetch(`/characters/${char.id}`, { method: 'PUT', body: JSON.stringify(updates) })
          _applyCharUpdates(char.id, updates)
          showCharMsg('酒馆角色卡解析成功，已更新角色信息')
          return
        }
      }
      // 普通图片：上传到 uploads
      const uploadRes = await fetch('/api/uploads/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: b64 }),
      })
      const { url } = await uploadRes.json()
      await apiFetch(`/characters/${char.id}`, {
        method: 'PUT',
        body: JSON.stringify({ avatar_url: url, image_url: url, reference_image: url }),
      })
      _applyCharUpdates(char.id, { avatar_url: url, image_url: url, reference_image: url })
      showCharMsg('肖像已更新')
    } catch (e) {
      showCharMsg('上传失败：' + e.message, true)
      console.error('肖像上传失败', e)
    } finally {
      charPortraitUploading.value = false
    }
  }
  reader.readAsDataURL(file)
}

const hasMemory = computed(() => {
  const s = memorySlots.value
  return (
    hasSlot(s.player) || hasSlot(s.scene) ||
    (s.npcs && Object.keys(s.npcs).length) ||
    s.relations?.length || s.events?.length ||
    s.threads?.length || s.items?.length
  )
})

function hasSlot(obj) {
  return obj && Object.values(obj).some(v => v)
}

// 数值条：把值解析成 0-100 百分比（用于好感度/暴虐值等进度条）。非数值返回 null。
function statPct(v) {
  let n = null
  if (typeof v === 'number') n = v
  else if (typeof v === 'string') {
    const m = v.match(/-?\d+(\.\d+)?/)
    if (m) n = parseFloat(m[0])
  }
  if (n === null || isNaN(n)) return null
  return Math.max(0, Math.min(100, n))
}
// 进度条颜色：低红、中黄、高绿（中性数值统一用 accent）
function statColor(pct) {
  if (pct === null) return 'bg-accent'
  if (pct < 30) return 'bg-red-400/80'
  if (pct < 60) return 'bg-amber-400/80'
  return 'bg-emerald-400/80'
}

const canCheckpoint = computed(() => memoryCurrentRound.value > memoryUpdatedAtRound.value)

async function loadMemory() {
  try {
    const data = await apiFetch(`/sessions/${sessionId.value}/memory`)
    memorySlots.value = data.slots || {}
    memoryCurrentRound.value = data.current_round || 0
    memoryUpdatedAtRound.value = data.updated_at_round || 0
    memoryInterval.value = data.interval || 10
    memoryError.value = false
  } catch (e) {
    console.error('[记忆] 加载失败:', e)
    memoryError.value = true
  }
}

async function triggerCheckpoint() {
  if (!canCheckpoint.value) return
  memoryLoading.value = true
  try {
    await apiFetch(`/sessions/${sessionId.value}/memory/checkpoint`, { method: 'POST' })
    // 等待 worker 处理完成
    await new Promise(r => setTimeout(r, 2000))
    await loadMemory()
  } catch (e) {
    try { alert(JSON.parse(e.message).detail || '存档失败') } catch { alert('存档失败') }
  } finally {
    memoryLoading.value = false
  }
}

async function openMemory() {
  showMemory.value = true
  await loadMemory()
}

async function refreshMemory() {
  if (memoryLoading.value) return
  memoryLoading.value = true
  await loadMemory()
  memoryLoading.value = false
}

// ── 世界规则 ─────────────────────────────────────────────────
const showWorldRules = ref(false)
const worldRuleTab = ref('plot')
const worldRuleTabs = [
  { key: 'plot', label: '故事设定' },
  { key: 'chars', label: '角色' },
  { key: 'lorebook', label: '世界书' },
  { key: 'prompts', label: '系统提示词' },
]
const worldRuleForm = ref({ title: '', concept: '', vibeStr: '', opening: '', backstory: '', pov: '3rd' })
const worldRuleChars = ref([])
const worldRuleLorebooks = ref([])
const worldRuleSaving = ref(false)

// ── 系统提示词编辑 ────────────────────────────────────────────
const promptMode = ref('classic')
const promptModes = ref(['classic'])
const promptList = ref([])
const selectedPrompt = ref('')
const promptContent = ref('')
const promptSaving = ref(false)
const promptLabels = {
  narrator: '叙述者',
  auto_advance: '自动推进',
  character_gen: '角色生成',
  character_autofill: '角色补全',
  memory_mgr: '记忆管理',
  lorebook_inj: '世界书注入',
  plot_creator: '剧情创建',
  snapshot: '实况生成',
  suggester: '猜你喜欢',
}

async function loadPromptList() {
  const data = await apiFetch(`/admin/prompts?mode=${promptMode.value}`)
  promptList.value = data.prompts || []
  promptModes.value = data.modes || ['classic']
}

async function loadPromptContent() {
  if (!selectedPrompt.value) return
  const data = await apiFetch(`/admin/prompts/${selectedPrompt.value}?mode=${promptMode.value}`)
  promptContent.value = data.content || ''
}

async function savePrompt() {
  promptSaving.value = true
  try {
    await apiFetch(`/admin/prompts/${selectedPrompt.value}?mode=${promptMode.value}`, {
      method: 'PUT',
      body: JSON.stringify({ content: promptContent.value }),
    })
    alert('提示词已保存')
  } catch (e) { alert('保存失败：' + e.message) }
  finally { promptSaving.value = false }
}

async function openWorldRules() {
  // 初始化表单
  if (plot.value) {
    let vibeArr = []
    try { vibeArr = JSON.parse(plot.value.vibe || '[]') } catch {}
    let style = {}
    try { style = JSON.parse(plot.value.style_settings || '{}') } catch {}
    worldRuleForm.value = {
      title: plot.value.title || '',
      concept: plot.value.concept || '',
      vibeStr: vibeArr.join('，'),
      opening: plot.value.opening || '',
      backstory: plot.value.backstory || '',
      pov: style.pov || '3rd',
    }
  }
  worldRuleChars.value = characters.value.map(c => ({
    ...c,
    _fold: true,
    _saving: false,
    aliasesStr: (() => { try { return JSON.parse(c.aliases || '[]').join('，') } catch { return c.aliases || '' } })(),
  }))
  await loadWorldRuleLorebooks()
  worldRuleTab.value = 'plot'
  loadPromptList()
  showWorldRules.value = true
}

async function saveWorldRulePlot() {
  worldRuleSaving.value = true
  try {
    const f = worldRuleForm.value
    let style = {}
    try { style = JSON.parse(plot.value.style_settings || '{}') } catch {}
    style.pov = f.pov
    await apiFetch(`/plots/${plot.value.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        title: f.title,
        concept: f.concept,
        vibe: f.vibeStr.split(/[,，]/).map(s => s.trim()).filter(Boolean),
        opening: f.opening,
        backstory: f.backstory,
        style_settings: style,
      }),
    })
    // 刷新本地
    plot.value = { ...plot.value, title: f.title, concept: f.concept, opening: f.opening, backstory: f.backstory, style_settings: JSON.stringify(style) }
    alert('故事设定已保存')
  } catch (e) { alert('保存失败：' + e.message) }
  finally { worldRuleSaving.value = false }
}

async function saveWorldRuleChar(ch, idx) {
  worldRuleChars.value[idx]._saving = true
  try {
    const body = {
      name: ch.name,
      description: ch.description,
      personality: ch.personality,
      first_mes: ch.first_mes,
    }
    if (ch.aliasesStr !== undefined) {
      body.aliases = JSON.stringify(
        (ch.aliasesStr || '').split(/[,，]/).map(s => s.trim()).filter(Boolean)
      )
    }
    await apiFetch(`/characters/${ch.id}`, { method: 'PUT', body: JSON.stringify(body) })
    const c = characters.value.find(x => x.id === ch.id)
    if (c) {
      c.name = ch.name
      c.description = ch.description
      c.personality = ch.personality
      c.first_mes = ch.first_mes
      if (ch.aliasesStr !== undefined) c.aliases = body.aliases
    }
    worldRuleChars.value[idx]._saving = false
    alert(`角色「${ch.name}」已保存`)
  } catch (e) {
    worldRuleChars.value[idx]._saving = false
    alert('保存失败：' + e.message)
  }
}

async function saveWorldRuleLorebook(lb) {
  lb._saving = true
  try {
    const entries = lb.entries.map(e => {
      let kw = e.keywordsStr || ''
      if (Array.isArray(kw)) kw = kw.join('，')
      if (typeof kw !== 'string') kw = String(kw || '')
      return {
        ...e,
        keywords: kw.split(/[,，]/).map(s => s.trim()).filter(Boolean),
      }
    })
    await apiFetch(`/lorebooks/${lb.id}`, {
      method: 'PUT',
      body: JSON.stringify({ entries }),
    })
    lb._saving = false
    alert(`规则「${lb.title}」已保存`)
  } catch (e) {
    lb._saving = false
    alert('保存失败：' + e.message)
  }
}

// ── 世界规则：上传JSON / 手写条目 ──────────────────────────────
const lorebookFileInput = ref(null)
const showNewEntryForm = ref(false)
const newEntry = ref({ keywordsStr: '', content: '' })
const lorebookSearch = ref('')

// 单个条目是否命中筛选（关键词或规则内容）
function entryMatches(entry) {
  const q = lorebookSearch.value.trim().toLowerCase()
  if (!q) return true
  return (entry.keywordsStr || '').toLowerCase().includes(q)
      || (entry.content || '').toLowerCase().includes(q)
}

// 条目是否显示：无筛选/世界书名命中→整本展示；否则按条目命中
function showEntry(lb, entry) {
  const q = lorebookSearch.value.trim().toLowerCase()
  if (!q) return true
  if ((lb.title || '').toLowerCase().includes(q)) return true
  return entryMatches(entry)
}

const filteredLorebooks = computed(() => {
  const q = lorebookSearch.value.trim().toLowerCase()
  if (!q) return worldRuleLorebooks.value
  // 世界书名命中 → 整本保留；否则只要有条目命中也保留（条目层由 entryMatches 控制显隐）
  return worldRuleLorebooks.value.filter(lb =>
    lb.title.toLowerCase().includes(q) ||
    (lb.entries || []).some(e => entryMatches(e))
  )
})

function triggerLorebookUpload() {
  lorebookFileInput.value?.click()
}

function toggleAllEntries(lb) {
  lb._foldAll = !lb._foldAll
  lb.entries.forEach(e => { e._fold = lb._foldAll })
}

async function onLorebookFilePicked(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  try {
    const text = await file.text()
    const name = file.name.replace(/\.json$/i, '')
    await apiFetch(`/plots/${plot.value.id}/lorebooks/import`, {
      method: 'POST',
      body: JSON.stringify({ name, file_content: text }),
    })
    // 刷新列表
    await loadWorldRuleLorebooks()
    alert('导入成功')
  } catch (err) {
    alert('导入失败：' + err.message)
  }
}

function addLorebookEntry() {
  newEntry.value = { keywordsStr: '', content: '' }
  showNewEntryForm.value = true
}

async function createQuickEntry() {
  const kw = newEntry.value.keywordsStr.trim()
  const ct = newEntry.value.content.trim()
  if (!kw || !ct) return
  try {
    // 直接用简易格式创建 lorebook
    const data = {
      entries: [{
        key: kw.split(/[,，]/).map(s => s.trim()).filter(Boolean),
        content: ct,
      }],
    }
    await apiFetch(`/plots/${plot.value.id}/lorebooks/import`, {
      method: 'POST',
      body: JSON.stringify({ name: '手写规则', data }),
    })
    showNewEntryForm.value = false
    await loadWorldRuleLorebooks()
  } catch (err) {
    alert('创建失败：' + err.message)
  }
}

// 导出单本世界书为 SillyTavern 兼容 JSON（可分享 / 可再导入）
function exportLorebook(lb) {
  const entries = {}
  let idx = 0
  for (const e of (lb.entries || [])) {
    const keys = (e.keywordsStr || '').split(/[,，]/).map(s => s.trim()).filter(Boolean)
    const content = (e.content || '').trim()
    if (!content) continue
    entries[idx] = { key: keys, keysecondary: [], comment: lb.title || '', content, constant: false, selective: keys.length > 0 }
    idx++
  }
  if (idx === 0) { alert('这本世界书没有可导出的条目'); return }
  const sanitize = s => (s || '世界书').replace(/[\\/:*?"<>|]/g, '_').trim()
  const fname = `${sanitize(lb.title)}_GG_worldbook.json`
  const data = { name: lb.title || '世界书', entries }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fname
  a.click()
  URL.revokeObjectURL(url)
}

async function deleteLorebook(lb) {
  if (!confirm(`删除规则「${lb.title}」？`)) return
  try {
    await apiFetch(`/plots/${plot.value.id}/lorebooks/${lb.id}`, { method: 'DELETE' })
    await loadWorldRuleLorebooks()
  } catch (err) {
    alert('删除失败：' + err.message)
  }
}

async function loadWorldRuleLorebooks() {
  try {
    const lbs = await apiFetch(`/plots/${plot.value.id}/lorebooks`)
    for (const lb of lbs) {
      const lbData = await apiFetch(`/lorebooks/${lb.id}`)
      lb.entries = (lbData.entries || []).map(e => ({
        ...e,
        keywordsStr: (() => {
          const kw = e.keywords
          if (Array.isArray(kw)) return kw.join('，')
          if (typeof kw === 'string') {
            try { return JSON.parse(kw).join('，') } catch { return kw }
          }
          return ''
        })(),
        _fold: true,   // 每条默认折叠
      }))
      lb._fold = true       // 整本默认折叠
      lb._foldAll = true    // 展开全部按钮状态
      lb._saving = false
    }
    worldRuleLorebooks.value = lbs
  } catch { worldRuleLorebooks.value = [] }
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    ...opts,
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * 把 chat_image 消息按 ref_message_id 插到对应对话后面，
 * 而不是按 DB 插入顺序留在末尾。
 */
function sortMessages(msgs) {
  const images = msgs.filter(m => m.role === 'chat_image')
  if (!images.length) return msgs

  const rest = msgs.filter(m => m.role !== 'chat_image')
  const result = [...rest]

  for (const img of images) {
    let meta = {}
    try { meta = JSON.parse(img.metadata || '{}') } catch {}
    const refId = meta.ref_message_id
    const idx = refId ? result.findIndex(m => m.id === refId) : -1
    if (idx >= 0) {
      result.splice(idx + 1, 0, img)
    } else {
      result.push(img)
    }
  }
  return result
}

async function loadSession(id) {
  loadingSession.value = true
  try {
    const session = await apiFetch(`/sessions/${id}`)
    messages.value = sortMessages(session.messages || [])
    bgImage.value = session.bg_image_url || ''

    if (!plot.value || plot.value.id !== session.plot_id) {
      plot.value = await apiFetch(`/plots/${session.plot_id}`)
      characters.value = plot.value.characters || []
    }

    restorePlayerChar()

    // 如果还没有背景图，轮询等待
    if (!bgImage.value) pollBgImage(id)
  } finally {
    loadingSession.value = false
    await nextTick(); scrollToBottom()
  }
}

async function setBgImage(url) {
  bgImage.value = url
  try {
    await apiFetch(`/sessions/${sessionId.value}`, {
      method: 'PATCH',
      body: JSON.stringify({ bg_image_url: url }),
    })
  } catch {}
}

function pollBgImage(id) {
  if (bgPollTimer) clearInterval(bgPollTimer)
  let attempts = 0
  bgPollTimer = setInterval(async () => {
    attempts++
    if (attempts > 30) { clearInterval(bgPollTimer); return }
    try {
      const session = await apiFetch(`/sessions/${id}`)
      if (session.bg_image_url) {
        bgImage.value = session.bg_image_url
        clearInterval(bgPollTimer)
        bgPollTimer = null
      }
    } catch {}
  }, 3000)
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || streaming.value) return
  userInput.value = ''
  autoResize()
  await _doChat(text, false)
}

async function autoAdvance() {
  if (streaming.value) return
  autoAdvancing.value = true
  await _doChat('', true)
  autoAdvancing.value = false
}

async function _doChat(text, isAutoAdvance) {
  // 自动推进 + 分隔线开启：插入隐藏占位制造 turn 分界，流结束后服务端消息替换
  if (isAutoAdvance && showTurnSep.value) {
    messages.value.push({ id: Date.now(), role: 'user', content: '', _hidden: true, metadata: playerCharId.value ? JSON.stringify({ player_character_id: playerCharId.value }) : null })
  } else if (!isAutoAdvance) {
    messages.value.push({ id: Date.now(), role: 'user', content: text, _temp: true, metadata: playerCharId.value ? JSON.stringify({ player_character_id: playerCharId.value }) : null })
    await nextTick(); scrollToBottom()
  }

  streaming.value = true
  streamBuffer.value = ''
  let finalForceScroll = false   // 出错时强制滚到底显示错误

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId.value, user_input: text, mode: mode.value, player_character_id: playerCharId.value, auto_advance: isAutoAdvance }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (raw === '[DONE]') continue
        try {
          const chunk = JSON.parse(raw)
          if (chunk.error) {
            throw new Error(chunk.error)
          }
          if (chunk.content) {
            // 流式中【绝不主动滚动】——用户在阅读，想看更多自己往下滑。
            streamBuffer.value += chunk.content
          }
        } catch (parseErr) {
          if (parseErr.message && !parseErr.message.startsWith('JSON')) throw parseErr
        }
      }
    }
    // 流结束后从服务端拉真实消息（不滚动，保持用户当前阅读位置）
    const session = await apiFetch(`/sessions/${sessionId.value}`)
    messages.value = sortMessages(session.messages || [])
  } catch (e) {
    messages.value.push({ id: Date.now() + 2, role: 'error', content: e.message, retryInput: text })
    finalForceScroll = true
  } finally {
    streaming.value = false
    streamBuffer.value = ''
    // 仅出错时滚到底（让用户看到错误）；正常流式/自动播放一律不滚
    if (finalForceScroll) { await nextTick(); scrollToBottom() }
  }
}

async function retractMessage(userMsg) {
  if (streaming.value) return
  if (!confirm('撤回此消息及之后的所有对话？')) return

  const msgIdx = messages.value.findIndex(m => m.id === userMsg.id)
  if (msgIdx < 0) return

  const content = userMsg.content
  // 后端删除该消息及之后所有；rollback=1 → 连带回滚记忆/演变/世界规则
  if (typeof userMsg.id === 'number') {
    await apiFetch(`/sessions/${sessionId.value}/messages/from/${userMsg.id}?rollback=1`, { method: 'DELETE' }).catch(() => {})
  }
  // 本地截断
  messages.value.splice(msgIdx)
  // 把撤回的内容放回输入框
  userInput.value = content
  await nextTick(); scrollToBottom()
}

async function regenerate(aiMsg) {
  if (streaming.value) return
  // 找到该 AI 消息前最近的一条用户消息
  const aiIdx = messages.value.findIndex(m => m.id === aiMsg.id)
  if (aiIdx < 0) return
  let userMsg = null
  for (let i = aiIdx - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') { userMsg = messages.value[i]; break }
  }
  if (!userMsg) return

  // 从该 AI 消息起截断本地状态
  messages.value.splice(aiIdx)

  // 后端也删掉（非临时消息才需要）
  if (typeof aiMsg.id === 'number') {
    await apiFetch(`/sessions/${sessionId.value}/messages/from/${aiMsg.id}`, { method: 'DELETE' }).catch(() => {})
  }

  // 用原用户输入重新发送
  userInput.value = userMsg.content
  await sendMessage()
}

async function retry(errorMsg) {
  const errIdx = messages.value.findIndex(m => m.id === errorMsg.id)
  if (errIdx >= 0) {
    // Remove error message and the preceding _temp user message together
    if (errIdx > 0 && messages.value[errIdx - 1]._temp) {
      messages.value.splice(errIdx - 1, 2)
    } else {
      messages.value.splice(errIdx, 1)
    }
  }
  userInput.value = errorMsg.retryInput
  await sendMessage()
}

async function genChatImage(messageId) {
  if (generatingImages.value.has(messageId)) return
  generatingImages.value = new Set([...generatingImages.value, messageId])

  // 立即插入占位图（跟在触发消息之后）
  const placeholderId = `ph_${messageId}_${Date.now()}`
  const triggerIdx = messages.value.findIndex(m => m.id === messageId)
  if (triggerIdx >= 0) {
    messages.value.splice(triggerIdx + 1, 0, {
      id: placeholderId, role: 'chat_image', content: '__loading__',
    })
  }
  await nextTick(); scrollToBottom()

  const cleanup = () => {
    const s = new Set(generatingImages.value)
    s.delete(messageId)
    generatingImages.value = s
    if (chatImgPollTimers[messageId]) {
      clearInterval(chatImgPollTimers[messageId])
      delete chatImgPollTimers[messageId]
    }
  }

  const removePlaceholder = () => {
    const idx = messages.value.findIndex(m => m.id === placeholderId)
    if (idx >= 0) messages.value.splice(idx, 1)
  }

  const failPlaceholder = () => {
    const idx = messages.value.findIndex(m => m.id === placeholderId)
    if (idx >= 0) {
      messages.value[idx] = {
        ...messages.value[idx],
        content: '/gen_failed.png',
        role: 'chat_image',
        _failed: true,
      }
    }
  }

  try {
    const { task_id } = await apiFetch('/image/from-chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId.value, message_id: messageId, player_character_id: playerCharId.value || null }),
    })

    chatImgPollTimers[messageId] = setInterval(async () => {
      const task = await apiFetch(`/tasks/${task_id}`)
      if (task.status === 'completed') {
        cleanup()
        // 用服务端真实数据替换（worker 已将 chat_image 写入 DB）
        const session = await apiFetch(`/sessions/${sessionId.value}`)
        messages.value = session.messages || []
        await nextTick(); scrollToBottom()
      } else if (task.status === 'failed') {
        cleanup()
        failPlaceholder()
      }
    }, 2000)
  } catch {
    cleanup()
    failPlaceholder()
  }
}

async function toggleSuggest(messageId) {
  // 如果已经在显示这个消息的建议，关闭
  if (suggestMsgId.value === messageId) {
    suggestMsgId.value = null
    suggestOptions.value = []
    return
  }
  // 开始加载
  suggestMsgId.value = messageId
  suggestOptions.value = []
  suggestLoading.value = messageId
  try {
    const data = await apiFetch('/chat/suggest', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId.value, mode: mode.value, player_character_id: playerCharId.value }),
    })
    suggestOptions.value = data.options || []
  } catch {
    suggestOptions.value = ['继续当前话题', '换个方向探索', '观察周围环境']
  } finally {
    suggestLoading.value = null
  }
}

function pickSuggestion(option) {
  userInput.value = option
  suggestMsgId.value = null
  suggestOptions.value = []
  sendMessage()
}


async function clearChat() {
  if (!confirm('清空当前会话的所有对话和实况记录？角色、设定、世界书不受影响。')) return
  await apiFetch(`/sessions/${sessionId.value}/messages/clear`, { method: 'DELETE' }).catch(() => {})
  // 本地保留开场白
  messages.value = messages.value.filter(m => m.role === 'init' || m.role === 'system')
  userInput.value = ''
  bgImage.value = ''
  streamBuffer.value = ''
  await nextTick(); scrollToBottom()
}

function scrollToBottom() {
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

// 全年龄向：固定经典模式
async function loadMode() {
  mode.value = 'classic'
  localStorage.setItem('narrative_mode', 'classic')
}

function openCharModal() {
  matchCharTargetInModal.value = null
  newChar.value = {
    name: '', description: '', personality: '',
    avatarMode: 'upload',
    avatarPreview: '',
    avatarFile: null,
    image_prompt: '',
    image_style: '',
  }
  showCharModal.value = true
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFilePicked(e) {
  const file = e.target.files?.[0]
  if (!file) return
  loadAvatarFile(file)
}

function onFileDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  loadAvatarFile(file)
}

function loadAvatarFile(file) {
  if (!file.type.startsWith('image/')) {
    alert('请上传图片文件')
    return
  }
  newChar.value.avatarFile = file
  const reader = new FileReader()
  reader.onload = () => {
    newChar.value.avatarPreview = reader.result
  }
  reader.readAsDataURL(file)
}

async function autofillCharacter() {
  if (!newChar.value.name.trim() || autofilling.value) return
  autofilling.value = true
  try {
    const data = await apiFetch('/characters/autofill', {
      method: 'POST',
      body: JSON.stringify({
        plot_id: plot.value.id,
        name: newChar.value.name.trim(),
        session_id: sessionId.value,
      }),
    })
    if (data.description) newChar.value.description = data.description
    if (data.personality) newChar.value.personality = data.personality
    if (data.image_prompt) {
      newChar.value.image_prompt = data.image_prompt
      // 自动切到文生图模式以显示生图描述字段
      if (newChar.value.avatarMode === 'upload') {
        newChar.value.avatarMode = 'generate'
      }
    }
  } catch (e) {
    alert('AI 补全失败：' + e.message)
  } finally {
    autofilling.value = false
  }
}

async function insertCharacter() {
  if (!newChar.value.name.trim() || insertingChar.value) return
  insertingChar.value = true
  try {
    let reference_image = ''
    let avatar_url = ''

    // 传图模式：先上传图片
    if (newChar.value.avatarMode === 'upload' && newChar.value.avatarFile) {
      const base64 = await fileToBase64(newChar.value.avatarFile)
      const uploadRes = await apiFetch('/uploads/image', {
        method: 'POST',
        body: JSON.stringify({ data: base64 }),
      })
      reference_image = uploadRes.url
      avatar_url = uploadRes.url
    }

    // 创建角色
    const { id } = await apiFetch('/characters', {
      method: 'POST',
      body: JSON.stringify({
        plot_id: plot.value.id,
        name: newChar.value.name.trim(),
        description: newChar.value.description.trim(),
        personality: newChar.value.personality.trim(),
        image_prompt: newChar.value.avatarMode === 'generate' ? newChar.value.image_prompt.trim() : '',
        image_style: newChar.value.avatarMode === 'generate' ? newChar.value.image_style : '',
        reference_image,
      }),
    })

    // 传图模式：直接设置 avatar_url（图片即头像）
    if (avatar_url) {
      await apiFetch(`/characters/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ image_prompt: '', image_style: '', reference_image: avatar_url }),
      })
    }

    // 文生图模式：触发异步头像生成
    let taskNotify = ''
    if (newChar.value.avatarMode === 'generate' && newChar.value.image_prompt.trim()) {
      try {
        const { task_id } = await apiFetch(`/characters/${id}/regenerate-avatar`, { method: 'POST' })
        taskNotify = '，头像生成中…'
        // 后台轮询更新头像（30s 超时）
        pollCharAvatar(id, task_id)
      } catch {}
    }

    // 刷新角色列表
    const updated = await apiFetch(`/plots/${plot.value.id}`)
    characters.value = updated.characters || []

    // 在消息流中插入系统通知
    messages.value.push({
      id: `sys_char_${Date.now()}`,
      role: 'system',
      content: `🔔 新角色「${newChar.value.name.trim()}」加入了故事${taskNotify}`,
    })
    showCharModal.value = false
    await nextTick(); scrollToBottom()
  } catch (e) {
    alert('插入角色失败：' + e.message)
  } finally {
    insertingChar.value = false
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function pollCharAvatar(charId, taskId, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      const task = await apiFetch(`/tasks/${taskId}`)
      if (task.status === 'completed') {
        const updated = await apiFetch(`/plots/${plot.value.id}`)
        characters.value = updated.characters || []
        return
      }
      if (task.status === 'failed') return
    } catch { return }
  }
  // 輪詢結束後做最終檢查
  try {
    const task = await apiFetch(`/tasks/${taskId}`)
    if (task.status === 'completed') {
      const updated = await apiFetch(`/plots/${plot.value.id}`)
      characters.value = updated.characters || []
    }
  } catch {
    // 忽略
  }
}

// ── 世界書快速搜尋 shortcut (Ctrl+F) ──────────────────────────
const lorebookSearchRef = ref(null)
function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault()
    lorebookSearchRef.value?.open()
  }
  // Ctrl+M：唤起/关闭记忆面板
  if ((e.ctrlKey || e.metaKey) && (e.key === 'm' || e.key === 'M')) {
    e.preventDefault()
    if (showMemory.value) showMemory.value = false
    else openMemory()
  }
  // Ctrl+B：唤起/关闭世界书面板
  if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
    e.preventDefault()
    if (showWorldRules.value) showWorldRules.value = false
    else openWorldRules()
  }
  // Ctrl+S：唤起/关闭导出 GG 卡弹窗（拦截浏览器保存）
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
    e.preventDefault()
    if (showExport.value) showExport.value = false
    else openExport()
  }
}

onMounted(async () => {
  await Promise.all([loadSession(sessionId.value), loadMode()])
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  if (bgPollTimer) clearInterval(bgPollTimer)
  Object.values(chatImgPollTimers).forEach(t => clearInterval(t))
})
</script>

<style scoped>
.memory-card {
  @apply bg-panel/40 border border-border/60 rounded-xl p-3.5 space-y-2.5;
}
.memory-card-title {
  @apply text-[13px] font-bold text-text/85 pb-1.5 mb-0.5 border-b border-border/40;
}
.memory-rows {
  @apply space-y-1.5;
}
.memory-row {
  @apply flex gap-2 text-xs text-text/80;
}
.memory-label {
  @apply text-muted flex-shrink-0 w-8;
}

/* 导出 GG 卡弹窗 */
.export-sec-title {
  @apply text-[13px] font-semibold text-text/85 mb-2;
}
.export-pill {
  @apply text-xs px-3 py-1.5 rounded-lg border border-border/50 text-muted/70 bg-panel/30 transition-all;
}
.export-pill-on {
  @apply border-accent/60 text-accent bg-accent/10;
}

/* 右侧抽屉滑入动画（记忆面板） */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

/* 左侧边栏滑入动画 */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.25s ease;
}
.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
}

/* 遮罩淡入动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>