<template>
  <div class="max-w-2xl mx-auto px-6 py-12 space-y-12">
    <!-- 头部 -->
    <div class="text-center">
      <h1 class="text-2xl font-bold gradient-text mb-2">GalGame · 新手必读</h1>
      <p class="text-muted text-sm">读完这页，你就是高手 ✨</p>
    </div>

    <!-- ── 这是什么 ── -->
    <section class="card !p-6 space-y-4">
      <h2 class="text-lg font-bold flex items-center gap-2">
        <span class="text-xl">🎭</span> 这是什么？
      </h2>
      <p class="text-sm text-text/80 leading-relaxed">
        一句话：<strong class="text-accent">这是一个能陪你"演故事"的 AI。</strong>
        你给它一个世界和一群角色，它就能和你一起把故事一幕幕演下去——角色会说话、会反抗、会记仇、会随剧情慢慢变成另一个人。
      </p>
      <p class="text-sm text-muted">不是聊天机器人，不是看小说。是<strong class="text-text/80">你当主角、AI 演活所有人</strong>的互动叙事游戏。</p>

      <div class="grid gap-2 sm:grid-cols-2">
        <div class="bg-black/15 border border-border/30 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🧠 会记忆</p>
          <p class="text-xs text-muted">角色记得你做过/说过什么，不会失忆</p>
        </div>
        <div class="bg-black/15 border border-accent/25 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🌱 会成长</p>
          <p class="text-xs text-muted">角色性格随剧情真的改变，忠臣能被逼黑化</p>
        </div>
        <div class="bg-black/15 border border-border/30 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🎨 会画画</p>
          <p class="text-xs text-muted">一键生成当前场景配图，文字变画面</p>
        </div>
        <div class="bg-black/15 border border-border/30 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🎭 有主见</p>
          <p class="text-xs text-muted">角色会拒绝、会对抗、有自己的目的</p>
        </div>
        <div class="bg-black/15 border border-border/30 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🃏 能分享</p>
          <p class="text-xs text-muted">整个故事存进一张图，发给朋友接着玩</p>
        </div>
        <div class="bg-black/15 border border-border/30 rounded-lg px-3 py-2">
          <p class="text-sm font-medium">🎲 不卡壳</p>
          <p class="text-xs text-muted">没思路？「猜你喜欢」给选项，或让 AI 自动演一段</p>
        </div>
      </div>
    </section>

    <!-- ── 3 步开玩 ── -->
    <section class="card !p-6 space-y-4">
      <h2 class="text-lg font-bold flex items-center gap-2">
        <span class="text-xl">🚀</span> 怎么开始玩？
      </h2>
      <div class="space-y-3">
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">1</div>
          <div>
            <p class="text-sm font-medium">不用填 Key，开箱即玩</p>
            <p class="text-xs text-muted">已内置免费的 <a href="https://platform.agnes-ai.com/settings/apiKeys" target="_blank" rel="noopener noreferrer" class="font-semibold text-accent hover:text-accent2 underline underline-offset-2 transition-colors">Agnes ↗</a> 连接（文字+画图都能用，公共 Key 共用）。想要更稳/更好的文笔画质，可在「管理后台 → API 配置」<strong class="text-text/80">添加自己的连接</strong>（DeepSeek、gpt-image-2 等）。Key 只存你本机，不上传。</p>
          </div>
        </div>
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">2</div>
          <div>
            <p class="text-sm font-medium">捏个新世界，或玩现成的</p>
            <p class="text-xs text-muted">「＋ 新建故事」跟 6 步向导走（一句话概念 → AI 生成开场/世界/角色）；或把朋友发的 <strong>GG 卡</strong> 在首页 / 向导第 ① 步「🃏 导入 GG 卡」秒进故事。</p>
          </div>
        </div>
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">3</div>
          <div>
            <p class="text-sm font-medium">开玩！打字 = 你的角色说话/行动</p>
            <p class="text-xs text-muted">回车发送；不想打字点 <code class="text-accent/70">▶ 自动推进</code> 让 AI 演；没思路点 <code class="text-accent/70">🎲 猜你喜欢</code> 选一个；想看画面点 <code class="text-accent/70">✦ 实况</code>。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ── GG 卡创建与分享 ── -->
    <section class="card !p-6 space-y-4">
      <h2 class="text-lg font-bold flex items-center gap-2">
        <span class="text-xl">🃏</span> GG 卡创建与分享
      </h2>
      <p class="text-sm text-muted">GG 卡是一张包含完整故事数据的加密 PNG，可以导出分享给朋友，导入即玩。</p>

      <div class="space-y-3">
        <!-- 步骤1 -->
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">1</div>
          <div>
            <p class="text-sm font-medium">在故事中玩到满意的进度</p>
            <p class="text-xs text-muted">确认角色、剧情、记忆都已生成</p>
          </div>
        </div>
        <!-- 步骤2 -->
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">2</div>
          <div>
            <p class="text-sm font-medium">顶栏「🃏 导出 GG 卡」或快捷键 <code class="text-accent">Ctrl+S</code></p>
            <p class="text-xs text-muted">弹窗里自由勾选：卡面（默认卡面或某张实况图）、角色卡（设计/图片/性格演变）、聊天轮次（滑块/输入）、记忆、世界书（原设定/规则演进/挂载）→ 生成并下载 PNG</p>
            <p class="text-[10px] text-amber-400/60 mt-0.5">数据 AES-256 加密；勾选的内容才会被打包进卡</p>
          </div>
        </div>
        <!-- 步骤3 -->
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">3</div>
          <div>
            <p class="text-sm font-medium">把 PNG 发给朋友</p>
            <p class="text-xs text-muted">数据 AES-256-GCM 加密嵌入图片，外部工具只能看到图</p>
          </div>
        </div>
        <!-- 步骤4 -->
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-bold">4</div>
          <div>
            <p class="text-sm font-medium">朋友在首页 或 新建向导第 ① 步 → 🃏 导入 GG 卡 → 选择 PNG</p>
            <p class="text-xs text-muted">自动恢复完整故事：剧情 + 角色 + 聊天记录 + 记忆 + 世界书，从你的进度接着玩</p>
          </div>
        </div>
      </div>

      <div class="bg-amber-900/15 border border-amber-500/20 rounded-lg px-3 py-2 text-xs text-amber-300/80">
        💡 <strong>珍藏夹：</strong><code class="text-amber-300">GG_cards/</code> 文件夹存放珍藏 GG 卡，Push 到 GitHub 永久保存。
      </div>
    </section>

    <!-- ── 隐藏交互 ── -->
    <section class="card !p-6 space-y-4">
      <h2 class="text-lg font-bold flex items-center gap-2">
        <span class="text-xl">🪄</span> 你可能不知道的隐藏操作
      </h2>

      <div class="space-y-2">
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">🔍</span>
          <div>
            <p class="text-sm font-medium">悬停用户消息</p>
            <p class="text-xs text-muted">显示「撤回」按钮，撤回该消息及之后所有对话，内容回填输入框</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">🔄</span>
          <div>
            <p class="text-sm font-medium">悬停 AI 消息</p>
            <p class="text-xs text-muted">显示「重生成」按钮，不满意可以重来</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">🖼</span>
          <div>
            <p class="text-sm font-medium">悬停故事卡片</p>
            <p class="text-xs text-muted">显示 ✎ 编辑 / ✕ 删除按钮</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">🖱</span>
          <div>
            <p class="text-sm font-medium">点击故事标题</p>
            <p class="text-xs text-muted">直接内联编辑标题，✓ 确认 ✕ 取消</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">👤</span>
          <div>
            <p class="text-sm font-medium">点击聊天中无头像角色名 / 首字母头像</p>
            <p class="text-xs text-muted">角色不在列表 → 快捷新增；角色已在列表 → 输入别名快速匹配合并</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">👤</span>
          <div>
            <p class="text-sm font-medium">点击聊天中有头像角色名 / 头像</p>
            <p class="text-xs text-muted">打开角色详情卡片，查看外貌/性格/开场白，可编辑和保存</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">✏️</span>
          <div>
            <p class="text-sm font-medium">点击故事卡片缩略图</p>
            <p class="text-xs text-muted">设为聊天背景；点击全屏图片 × 关闭，底部 🗑 可删除</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">━</span>
          <div>
            <p class="text-sm font-medium">顶部工具栏 ━ 按钮</p>
            <p class="text-xs text-muted">开启回合分隔线，每轮对话之间显示 ⏳ 虚线标记，长剧情不迷路</p>
          </div>
        </div>
        <div class="flex items-start gap-3 py-2 border-b border-border/40 last:border-0">
          <span class="text-accent text-sm mt-0.5">▶</span>
          <div>
            <p class="text-sm font-medium">输入框右侧 ▶ 按钮（自动推进）</p>
            <p class="text-xs text-muted">AI 替你扮演角色并推进剧情，不想打字就看 AI 自己演。不会自动滚屏</p>
          </div>
        </div>
      </div>

      <!-- 快捷键（突出显示） -->
      <div class="mt-4 rounded-xl border border-accent/30 bg-accent/[0.06] p-4">
        <p class="text-sm font-bold text-text flex items-center gap-2 mb-3">
          <span class="text-base">⌨️</span> 快捷键
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div v-for="k in shortcuts" :key="k.combo"
               class="flex items-center gap-2.5 rounded-lg bg-bg/40 border border-border/50 px-3 py-2">
            <kbd class="flex-shrink-0 inline-flex items-center px-2 py-1 rounded-md bg-panel border border-border text-accent font-mono text-xs font-semibold shadow-sm whitespace-nowrap">{{ k.combo }}</kbd>
            <span class="text-xs text-text/85 leading-tight">
              {{ k.desc }}
              <span v-if="k.tag" class="ml-1 text-[9px] align-middle px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">{{ k.tag }}</span>
            </span>
          </div>
        </div>
        <p class="text-[11px] text-muted/70 mt-2.5">💬 聊天输入 <code class="text-accent/70">Enter</code> 发送 · <code class="text-accent/70">Shift+Enter</code> 换行；弹窗均可 <code class="text-accent/70">Esc</code> 或点遮罩关闭。</p>
      </div>
    </section>

    <!-- ── 常见疑问 ── -->
    <section class="card !p-6 space-y-4">
      <h2 class="text-lg font-bold flex items-center gap-2">
        <span class="text-xl">❓</span> 常见疑问
      </h2>
      <div class="space-y-4">
        <div>
          <p class="text-sm font-semibold text-text">什么是 GG 卡？我的卡会被别人破解吗？</p>
          <p class="text-xs text-muted leading-relaxed mt-1">
            GG 卡就是一张<strong class="text-text/80">看起来普通、其实藏了整个故事的 PNG 图片</strong>——剧情、角色、对话、记忆、世界书全在里面，一张图 = 一个完整存档。
            里面的数据经过 <strong class="text-amber-300/80">AES-256 加密</strong>，用微信、PS、系统看图等任何外部工具打开都<strong>只能看到一张图，读不出内容</strong>，对普通人和外部软件是安全的。（实话：它防的是"随手就能看/改"，不是军用级保险箱，但挡住非 GalGame 用户完全够用。）
          </p>
        </div>
        <div class="border-t border-border/40 pt-3">
          <p class="text-sm font-semibold text-text">能用酒馆（SillyTavern）角色卡吗？怎么快速导入？</p>
          <p class="text-xs text-muted leading-relaxed mt-1">
            <strong class="text-accent">完全兼容</strong>酒馆角色卡 PNG。最快：新建故事 → 第 ① 步点「📎 上传角色卡」→ 选酒馆 PNG → AI 自动提取角色、开场、世界观，直接生成能玩的故事。阅读页/编辑器也能随时追加导入；还支持导入酒馆<strong>世界书 JSON</strong>。
          </p>
        </div>
        <div class="border-t border-border/40 pt-3">
          <p class="text-sm font-semibold text-text">我可以"攻略"角色吗？角色会自动记住吗？</p>
          <p class="text-xs text-muted leading-relaxed mt-1">
            可以。角色对你的<strong class="text-text/80">好感、态度、信任、关系张力</strong>都会被真实追踪（还有好感度/忠诚度这类隐藏数值）。记忆<strong>每 10 轮自动更新</strong>（也能随时手动「🧠 记忆 → 存档」）。更进一步——角色性格会<strong class="text-accent">随剧情演变</strong>（头像出现 🌱）：你把人攻略到位、或逼到极端，ta 是真的会变成另一个样子。
          </p>
        </div>
        <div class="border-t border-border/40 pt-3">
          <p class="text-sm font-semibold text-text">攻略不动某个角色怎么办？</p>
          <p class="text-xs text-muted leading-relaxed mt-1">
            可以"作弊"：左侧角色栏点任意角色的<strong class="text-accent">「扮演」</strong>，<strong class="text-text/80">主动扮演其他角色</strong>替你说话办事——比如借对方闺蜜/上司/对手之口推动关系，再切回自己，往往能撬开僵局。角色的好感、态度会随这些互动真实变化。
          </p>
        </div>
        <div class="border-t border-border/40 pt-3">
          <p class="text-sm font-semibold text-text">要花钱吗？故事会上传网上吗？</p>
          <p class="text-xs text-muted leading-relaxed mt-1">
            不用钱。软件免费开源，还内置了免费的公共 Agnes Key，下载就能玩；只有想要更顶的画质/文笔、或公共 Key 被限流时，才需在「API 配置」加一个自己的连接（按量付费、很便宜）。所有故事数据<strong class="text-text/80">只存在你自己电脑上</strong>，完全本地运行，不上传。Windows / Mac 之间用 GG 卡互通。
          </p>
        </div>
      </div>
    </section>

    <!-- 底部 -->
    <p class="text-center text-xs text-muted/40">
      完整文档见 <a href="https://github.com/chenpipi0807/Galgame-SFW" class="text-accent/60 hover:text-accent" target="_blank">GitHub README</a>
    </p>
  </div>
</template>

<script setup>
const shortcuts = [
  { combo: 'Ctrl+M', desc: '唤起记忆面板' },
  { combo: 'Ctrl+B', desc: '唤起世界书' },
  { combo: 'Ctrl+S', desc: '导出 GG 卡' },
  { combo: 'Ctrl+F', desc: '快速搜索世界书', tag: 'NEW' },
]
</script>
