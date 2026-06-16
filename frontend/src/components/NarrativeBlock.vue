<template>
  <div class="narrative-content space-y-4 animate-fade-in">
    <template v-for="(block, i) in parsedBlocks" :key="i">

      <!-- ① 旁白层：环境描写 / 氛围渲染（含角色名的整句提亮，角色名加重） -->
      <div v-if="block.type === 'narration'" class="pl-3 border-l border-text/12">
        <p class="text-[15px] leading-[2] tracking-[0.02em] font-sans">
          <template v-for="(seg, si) in narrationSegments(block.content)" :key="si"><span :class="seg.hot ? 'text-text/95 font-normal' : 'text-text/60 font-light'"><template v-for="(p, pi) in seg.parts" :key="pi"><span v-if="p.isName" class="text-accent font-semibold">{{ p.text }}</span><template v-else>{{ p.text }}</template></template></span></template>
        </p>
      </div>

      <!-- ② 心理描写层：内心独白 -->
      <div
        v-else-if="block.type === 'inner'"
        class="mx-1 px-3.5 py-2 rounded-xl bg-purple-950/25 border border-purple-700/20"
      >
        <span v-if="block.name" class="text-[11px] font-semibold text-purple-400/60 mr-1.5 font-sans">{{ block.name }}</span>
        <span class="text-[14px] italic text-purple-300/70 leading-relaxed font-sans">{{ block.content }}</span>
      </div>

      <!-- ③-a 玩家角色行（_player:true）：右对齐，琥珀色系 -->
      <div v-else-if="block.type === 'character' && block._player" class="flex items-start gap-3.5 flex-row-reverse">
        <!-- 头像（右侧） -->
        <div
          class="flex-shrink-0 mt-0.5 cursor-pointer hover:ring-2 hover:ring-amber-400/60 rounded-full transition-all"
          @click.stop="getAvatar(block.name) ? emit('character-click', block.name) : emit('character-no-avatar', block.name)"
        >
          <img
            v-if="getAvatar(block.name)"
            :src="getAvatar(block.name)"
            class="w-11 h-11 rounded-full object-cover ring-2 ring-amber-500/60 shadow-lg shadow-black/40"
          />
          <div
            v-else-if="block.name"
            class="w-11 h-11 rounded-full bg-gradient-to-br from-amber-600/40 to-amber-400/20 flex items-center justify-center text-[15px] font-bold text-amber-300/90 ring-1 ring-amber-500/30 font-sans"
          >{{ block.name[0] }}</div>
        </div>
        <!-- 文字内容（右对齐） -->
        <div class="flex-1 min-w-0 space-y-2 flex flex-col items-end">
          <div v-if="block.name">
            <span
              class="text-[11px] font-semibold tracking-widest uppercase text-amber-400/85 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 font-sans cursor-pointer hover:bg-amber-500/20 transition-colors"
              @click.stop="getAvatar(block.name) ? emit('character-click', block.name) : emit('character-no-avatar', block.name)"
            >{{ block.name }}</span>
          </div>
          <p v-if="block.action" class="w-full text-[15px] text-text/90 font-normal leading-[1.9] font-sans text-left">{{ block.action }}</p>
          <div v-if="block.dialogue">
            <div class="inline-block max-w-full rounded-2xl rounded-tr-sm px-4 py-2.5 bg-amber-500/10 border border-amber-500/20">
              <p class="text-[15px] text-amber-200/90 leading-relaxed font-sans">{{ block.dialogue }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ③-b NPC 角色行：头像在左，左对齐 -->
      <div v-else-if="block.type === 'character'" class="flex items-start gap-3.5">

        <!-- 头像：仅真实角色渲染；代词/引号/符号/无名 → 不渲染头像，只出气泡 -->
        <div
          v-if="isRealCharacter(block.name)"
          class="flex-shrink-0 mt-0.5 cursor-pointer hover:ring-2 hover:ring-accent/60 rounded-full transition-all"
          @click.stop="getAvatar(block.name) ? emit('character-click', block.name) : emit('character-no-avatar', block.name)"
        >
          <img
            v-if="getAvatar(block.name)"
            :src="getAvatar(block.name)"
            class="w-11 h-11 rounded-full object-cover ring-2 ring-border/60 shadow-lg shadow-black/40"
          />
          <div
            v-else
            class="w-11 h-11 rounded-full bg-gradient-to-br from-accent/30 to-accent2/20 flex items-center justify-center text-[15px] font-bold text-accent/90 ring-1 ring-accent/25 font-sans"
          >{{ block.name[0] }}</div>
        </div>

        <!-- 文字内容 -->
        <div class="flex-1 min-w-0 space-y-2">
          <!-- 角色名标签：仅真实角色才显示 -->
          <div v-if="isRealCharacter(block.name)">
            <span
              class="text-[11px] font-semibold tracking-widest uppercase text-accent/85 px-2 py-0.5 rounded-md bg-accent/10 border border-accent/20 font-sans cursor-pointer hover:bg-accent/20 transition-colors"
              @click.stop="getAvatar(block.name) ? emit('character-click', block.name) : emit('character-no-avatar', block.name)"
            >
              {{ block.name }}
            </span>
          </div>
          <!-- 行动描写 -->
          <p v-if="block.action" class="text-[15px] text-text/90 font-normal leading-[1.9] font-sans">{{ block.action }}</p>
          <!-- 对白气泡 -->
          <div v-if="block.dialogue" class="relative">
            <div class="inline-block max-w-full rounded-2xl rounded-tl-sm px-4 py-2.5 bg-accent2/10 border border-accent2/20">
              <p class="text-[15px] text-accent2/92 leading-relaxed font-sans">{{ block.dialogue }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ④ 用户消息 -->
      <p v-else-if="block.type === 'user-text'" class="text-[15px] text-text/80 leading-relaxed font-sans">{{ block.content }}</p>

    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { jsonrepair } from 'jsonrepair'

const props = defineProps({
  text: { type: String, required: true },
  characters: { type: Array, default: () => [] },
  role: { type: String, default: 'assistant' },
})

const emit = defineEmits(['character-click', 'character-no-avatar'])

const avatarMap = computed(() => {
  const m = {}
  for (const c of props.characters) {
    if (c.name && c.avatar_url) m[c.name] = c.avatar_url
    // 别名也映射到同一头像
    if (c.avatar_url) {
      try {
        const aliases = JSON.parse(c.aliases || '[]')
        for (const a of aliases) {
          if (a && !m[a]) m[a] = c.avatar_url
        }
      } catch {}
    }
  }
  return m
})

function getAvatar(name) { return avatarMap.value[name] || null }

// 已知角色名（含别名），供散文兜底归属说话人
const knownNames = computed(() => {
  const names = []
  for (const c of props.characters) {
    if (c.name) names.push(c.name)
    try {
      for (const a of JSON.parse(c.aliases || '[]')) if (a) names.push(a)
    } catch {}
  }
  return names
})

// 是否为真实角色（在角色列表里，按名或别名匹配）。
// 代词(他/她/它/女人)、引号、特殊符号、空名都不算 —— 这类只渲染对话气泡，不渲染头像/名签。
function isRealCharacter(name) {
  return !!name && knownNames.value.includes(name)
}

// 旁白行为高亮：把旁白切句，含已知角色名/别名的整句提亮，句中角色名再加重。
// 让用户一眼看到"谁做了关键行为"，而不是只盯着对白气泡。
function _escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }
const _nameRe = computed(() => {
  const names = [...new Set(knownNames.value.filter(n => n && n.length >= 2))]
    .sort((a, b) => b.length - a.length).map(_escapeRe)
  return names.length ? new RegExp(`(${names.join('|')})`, 'g') : null
})
const _SENT_SPLIT = /([。！？!?…]+|[；;]|\n)/
function narrationSegments(content) {
  if (!content) return []
  const re = _nameRe.value
  // 切句（保留句末标点）
  const raw = content.split(_SENT_SPLIT)
  const sentences = []
  for (let i = 0; i < raw.length; i += 2) {
    const full = (raw[i] || '') + (raw[i + 1] || '')
    if (full) sentences.push(full)
  }
  return sentences.map(s => {
    if (!re) return { hot: false, parts: [{ text: s, isName: false }] }
    re.lastIndex = 0
    const hot = re.test(s)
    if (!hot) return { hot: false, parts: [{ text: s, isName: false }] }
    const parts = []
    let last = 0, m
    re.lastIndex = 0
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) parts.push({ text: s.slice(last, m.index), isName: false })
      parts.push({ text: m[0], isName: true })
      last = m.index + m[0].length
    }
    if (last < s.length) parts.push({ text: s.slice(last), isName: false })
    return { hot: true, parts }
  })
}

function isNDJSON(text) {
  // 只要任意一行是合法的 {type:...} JSON 对象就认为是 NDJSON 格式
  // 避免 LLM 在第一行输出非 JSON 前缀导致整体走 parseLegacy
  return text.split('\n').some(line => {
    const t = line.trim()
    return t.startsWith('{') && t.includes('"type"')
  })
}

// 容错归一化 type：LLM 偶尔把 type 拼错(characvter/caracter/chronation 等)，
// 严格相等会导致整行被丢弃、内容"被吞"。这里宽容匹配 + 按字段兜底推断。
// 仍返回 null 的(真正未知且无有效字段)按原逻辑丢弃，保证纯 NDJSON 行为不变。
function coerceType(o) {
  if (!o || typeof o !== 'object') return null
  const t = String(o.type || '').toLowerCase()
  if (/narrat|chron|旁白|叙述/.test(t)) return 'narration'
  if (/char|carac|角色|对白|对话/.test(t)) return 'character'
  if (/inner|心声|内心|独白/.test(t)) return 'inner'
  // 字段兜底：有名字且有动作/对白 → 角色；只有 content → 旁白
  if (o.name && (o.dialogue || o.action)) return 'character'
  if (o.content && !o.name) return 'narration'
  return null
}

// 字段名归一化：LLM 偶尔把 key 拼错/大小写错(naem/Dialouge/actoin)，
// 这层把它们映射回规范键。语义层，JSON 修复库管不了(那些是合法 JSON key)。
const _CANON_KEYS = ['type', 'name', 'action', 'dialogue', 'content', '_player']
const _KEY_ALIAS = {
  type: 'type', tpye: 'type', typ: 'type',
  name: 'name', naem: 'name', nmae: 'name', names: 'name',
  action: 'action', actoin: 'action', acton: 'action', act: 'action',
  dialogue: 'dialogue', dialog: 'dialogue', dialouge: 'dialogue', dialgue: 'dialogue', dia: 'dialogue', speech: 'dialogue', say: 'dialogue',
  content: 'content', contetn: 'content', contnet: 'content', text: 'content', narration: 'content',
  _player: '_player', player: '_player', isplayer: '_player', is_player: '_player',
}
function _editDist1(a, b) {
  // 仅判断编辑距离是否 ≤1（够用且快）
  if (a === b) return true
  const la = a.length, lb = b.length
  if (Math.abs(la - lb) > 1) return false
  let i = 0, j = 0, edits = 0
  while (i < la && j < lb) {
    if (a[i] === b[j]) { i++; j++; continue }
    if (++edits > 1) return false
    if (la > lb) i++
    else if (la < lb) j++
    else { i++; j++ }
  }
  if (i < la || j < lb) edits++
  return edits <= 1
}
function normalizeKeys(o) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return o
  const out = {}
  for (const [k, v] of Object.entries(o)) {
    const lk = k.toLowerCase().replace(/[\s_-]/g, m => (m === '_' ? '_' : ''))
    let canon = _KEY_ALIAS[k.toLowerCase()] || _KEY_ALIAS[lk]
    if (!canon) canon = _CANON_KEYS.find(ck => _editDist1(lk.replace(/^_/, ''), ck.replace(/^_/, '')))
    out[canon || k] = v
  }
  return out
}

// ── NDJSON 容错修复（仅在 JSON.parse 失败的行上触发，纯 NDJSON 永不进入）────────
// 把一行原文解析成的对象转成 block，沿用与主路径完全一致的接受规则
function objToBlock(raw) {
  const o = normalizeKeys(raw)
  if (!o || typeof o !== 'object') return null
  const t = coerceType(o)
  if (t === 'narration' && o.content) return { type: 'narration', content: o.content }
  if (t === 'inner' && o.content) return { type: 'inner', name: o.name || '', content: o.content }
  if (t === 'character' && o.name) return { type: 'character', name: o.name, action: o.action || '', dialogue: o.dialogue || '', _player: !!o._player }
  return null
}

// 修复一行损坏的类 JSON：交给成熟库 jsonrepair(单引号/缺括号/粘连/尾逗号/截断等)，
// 再走 normalizeKeys + coerceType 语义归一。粘连的 }{ 会被修成数组，统一遍历。
function repairLine(trimmed) {
  const out = []
  const pushB = (b) => { if (b) { if (b.type === 'character' && !b.action && !b.dialogue) return; out.push(b) } }
  let parsed
  try {
    parsed = JSON.parse(jsonrepair(trimmed))
  } catch {
    // jsonrepair 不自动拆单行粘连的多个对象(}{)，包成数组(并把 }{ 补成 },{)再修
    try {
      const wrapped = '[' + trimmed.replace(/\}\s*,?\s*\{/g, '},{') + ']'
      parsed = JSON.parse(jsonrepair(wrapped))
    } catch {
      return out
    }
  }
  const objs = Array.isArray(parsed) ? parsed : [parsed]
  for (const o of objs) pushB(objToBlock(o))
  return out
}

// ── 散文兜底（LLM 完全没按格式输出时，尽量救出对白气泡）──────────────────────
const SPEECH_VERB = '(?:说道|说|道|沉声道|沉声说|低声道|低声说|开口道|开口|应道|答道|问道|笑道|轻声道|喝道|叹道|续道|补充道|沉声应道|轻声说)'
function looksLikeDialogueParagraph(p) {
  // 只在「段落以引号开头」或「名：引号」时判为对白，避免把叙事中引用的引号误判
  const startsQuote = /^[“"]/.test(p)
  const nameColon = p.match(/^([一-龥]{1,6})[：:]\s*(?=[“"])/)
  if (!startsQuote && !nameColon) return null
  const body = nameColon ? p.slice(nameColon[0].length) : p
  const spans = []
  let action = ''
  const re = /[“"]([^”"]*)[”"]/g
  let last = 0, m
  while ((m = re.exec(body)) !== null) { action += body.slice(last, m.index); if (m[1]) spans.push(m[1]); last = re.lastIndex }
  action += body.slice(last)
  if (!spans.length) return null
  return { text: spans.join(' '), action: action.trim(), name: nameColon ? nameColon[1] : '' }
}
function findSpeakerInPrev(prevText, known) {
  if (!prevText) return ''
  known = known || []
  // 上一段叙事以已知角色名开头 → 该角色说话
  if (known.length) { for (const n of known) { if (n && prevText.startsWith(n)) return n } }
  // 结尾「名+说话动词」且名在已知列表中
  const reKnown = new RegExp('([\\u4e00-\\u9fa5]{2,4})' + SPEECH_VERB + '[。.！!，,]?\\s*$')
  const mk = prevText.match(reKnown)
  if (mk && mk[1] && known.includes(mk[1])) return mk[1]
  if (!known.length) {
    const re = new RegExp('(?:^|[，。、；：])([\\u4e00-\\u9fa5]{2,4})' + SPEECH_VERB + '[。.！!，,]?\\s*$')
    const m = prevText.match(re)
    if (m && m[1]) return m[1]
  }
  return ''  // 归属不确定 → 无名气泡（仍渲染气泡，只是不带头像标签）
}
function parseProse(text, known = []) {
  const blocks = []
  let paras = text.split(/\n{2,}/).map(s => s.trim()).filter(Boolean)
  if (paras.length <= 1) paras = text.split(/\n/).map(s => s.trim()).filter(Boolean)
  let lastNarration = ''
  for (const p of paras) {
    const md = p.match(/^[【\*]{1,2}([^】\*：:]{1,12})[】\*]{1,2}\s*[:：]?\s*(.*)$/)
    if (md && (p.startsWith('【') || p.startsWith('**'))) {
      const rest = md[2].trim()
      const q = rest.match(/[“"]([^”"]*)[”"]/)
      blocks.push({ type: 'character', name: md[1].trim(), action: q ? rest.replace(/[“"][^”"]*[”"]/, '').trim() : '', dialogue: q ? q[1] : rest })
      lastNarration = ''
      continue
    }
    const iN = p.match(/^[（(]([^：:）)]{1,10})[：:](.+)[）)]$/)
    if (iN) { blocks.push({ type: 'inner', name: iN[1].trim(), content: iN[2].trim() }); lastNarration = ''; continue }
    const iP = p.match(/^[（(]([^（）()]{4,})[）)]$/)
    if (iP) { blocks.push({ type: 'inner', name: '', content: iP[1].trim() }); lastNarration = ''; continue }
    const dlg = looksLikeDialogueParagraph(p)
    if (dlg) {
      const name = dlg.name || findSpeakerInPrev(lastNarration, known)
      blocks.push({ type: 'character', name: name || '', action: dlg.action || '', dialogue: dlg.text })
      continue
    }
    blocks.push({ type: 'narration', content: p })
    lastNarration = p
  }
  return blocks
}

// 是否含 legacy markdown 标记 → 走精确的旧 parseLegacy，保证向后兼容
function hasLegacyMarkers(text) {
  return text.split('\n').some(l => {
    const t = l.trim()
    return /^\*\*.+?\*\*/.test(t) || /^>\s*/.test(t) || t === '---'
      || /^[（(][^：:）)]{1,10}[：:].+[）)]$/.test(t) || /^[（(][^（）()]{4,}[）)]$/.test(t)
  })
}

function parseLegacy(text) {
  const blocks = []
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (!t) continue

    // 心理描写：（角色名：内容）或 （内容）
    const innerNamed = t.match(/^[（(]([^：:）)]{1,10})[：:](.+)[）)]$/)
    if (innerNamed) {
      blocks.push({ type: 'inner', name: innerNamed[1].trim(), content: innerNamed[2].trim() })
      continue
    }
    const innerPlain = t.match(/^[（(]([^（）()]{4,})[）)]$/)
    if (innerPlain) {
      blocks.push({ type: 'inner', name: '', content: innerPlain[1].trim() })
      continue
    }

    // 角色行动：**名** 行动
    const actionMatch = t.match(/^\*\*(.+?)\*\*\s*(.*)$/)
    if (actionMatch) {
      blocks.push({ type: 'character', name: actionMatch[1], action: actionMatch[2], dialogue: '' })
      continue
    }

    // 对白：> "..." 或 > "..."
    const dialogueMatch = t.match(/^>\s*["""「『]?(.+?)["""」』]?\s*$/)
    if (dialogueMatch) {
      const last = blocks[blocks.length - 1]
      if (last?.type === 'character' && !last.dialogue) {
        last.dialogue = dialogueMatch[1]
      } else {
        blocks.push({ type: 'character', name: '', action: '', dialogue: dialogueMatch[1] })
      }
      continue
    }

    if (t === '---') continue
    blocks.push({ type: 'narration', content: t })
  }
  return blocks
}

const parsedBlocks = computed(() => {
  if (props.role === 'user') {
    return [{ type: 'user-text', content: props.text }]
  }

  // 始终解析完整 props.text（含正在流式的半行），保证流式逐字可见
  const text = props.text

  // 非 NDJSON：含 markdown 标记走精确旧逻辑（向后兼容），否则走散文兜底
  if (!isNDJSON(text)) {
    if (hasLegacyMarkers(text)) return parseLegacy(text)
    return parseProse(text, knownNames.value)
  }

  // NDJSON 路径：每行先严格 JSON.parse（纯 NDJSON 永不进入修复分支），
  // 失败且形似 JSON 的行才尝试容错修复(jsonrepair)
  const blocks = []
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      const obj = JSON.parse(trimmed)
      const b = objToBlock(obj)   // normalizeKeys(字段名) + coerceType(type值) + 接受门槛
      if (b) blocks.push(b)
      continue
    } catch {
      // 解析失败，进入修复
    }
    if (!(trimmed.startsWith('{') && trimmed.includes('"type"'))) continue
    for (const b of repairLine(trimmed)) blocks.push(b)
  }
  return blocks
})
</script>