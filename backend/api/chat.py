import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from db.database import get_db
from core.llm import stream as llm_stream, chat as llm_chat
from core.prompt_loader import load
from core.memory import get_context_messages, count_messages, SLOT_UPDATE_INTERVAL
from core.lorebook_inj import scan, build_injection
from tasks.worker import enqueue

logger = logging.getLogger("galgame.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatBody(BaseModel):
    session_id: int
    user_input: str
    mode: str = "classic"
    player_character_id: int | None = None
    auto_advance: bool = False  # 自动推进模式：LLM 扮演用户角色+NPC


class SuggestBody(BaseModel):
    session_id: int
    mode: str = "classic"
    player_character_id: int | None = None


@router.post("/suggest")
async def suggest_options(body: SuggestBody):
    """根据当前对话上下文生成 5 个故事走向建议"""
    db = await get_db()

    async with db.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 全年龄向：固定使用 classic 模式
    suggest_mode = "classic"

    summary, history = await get_context_messages(body.session_id)
    if not history:
        return {"options": ["继续", "观察周围环境中的细节", "更粗暴的对待对方", "使用身上的物品试探对方", "对刚才的行为深感不安"]}

    # 查询玩家角色信息（必须限定当前 plot，防止跨项目 ID 碰撞）
    player_char = None
    if body.player_character_id:
        async with db.execute(
            "SELECT name, description, personality, aliases FROM characters WHERE id=? AND plot_id=?",
            (body.player_character_id, session["plot_id"]),
        ) as cur:
            row = await cur.fetchone()
        if row:
            player_char = dict(row)

    # 读取剧情背景（用于提供故事上下文）
    async with db.execute("SELECT * FROM plots WHERE id=?", (session["plot_id"],)) as cur:
        plot = await cur.fetchone()
    plot = dict(plot) if plot else {}

    # 获取同剧情所有角色（用于关系参考）
    async with db.execute(
        "SELECT name, personality FROM characters WHERE plot_id=? AND id != ?",
        (session["plot_id"], body.player_character_id or 0),
    ) as cur:
        other_chars = [dict(r) for r in await cur.fetchall()]

    suggester = await load("suggester", suggest_mode)
    recent = "\n".join(h["content"][:400] for h in history[-10:])

    # 构建丰富的角色上下文
    if player_char:
        name = player_char["name"]
        personality = (player_char.get("personality") or "").strip()
        desc = (player_char.get("description") or "").strip()
        aliases_raw = player_char.get("aliases", "[]")
        try:
            aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
        except Exception:
            aliases = []
        alias_str = f"，也被称为{'、'.join(aliases)}" if aliases else ""

        char_ctx = f"用户当前正在扮演【{name}】{alias_str}，用户就是【{name}】本人。"
        if personality:
            char_ctx += f"\n{name}的性格：{personality}"
        if desc:
            char_ctx += f"\n{name}的背景：{desc[:400]}"

        # 添加剧情背景
        if plot.get("backstory"):
            char_ctx += f"\n\n【世界背景】{plot['backstory'][:500]}"
        if plot.get("opening"):
            char_ctx += f"\n【故事开场】{plot['opening'][:400]}"

        # 添加场上其他角色
        if other_chars:
            others = "、".join(f"{c['name']}({c.get('personality','')[:20]})" for c in other_chars[:5])
            char_ctx += f"\n\n【场上其他角色】{others}"

        char_ctx += (
            f"\n\n【核心要求】"
            f"请以【{name}】的第一人称视角，生成 5 个【{name}】接下来可能采取的行动或会说的话语。"
            f"选项必须符合【{name}】的性格、背景和在世界中的地位。"
            f"禁止将【{name}】作为第三方角色提及。"
        )
        prompt_text = f"{char_ctx}\n\n最近的对话历史：\n{recent}"
    else:
        prompt_text = f"请根据以下对话历史，生成 5 个后续故事走向选项：\n\n{recent}"

    msgs = [{"role": "user", "content": prompt_text}]

    try:
        result = await llm_chat(
            messages=msgs,
            system=suggester,
            temperature=0.95,
        )
        import re
        match = re.search(r'\[[^\]]*\]', result, re.DOTALL)
        if match:
            options = json.loads(match.group())
            if isinstance(options, list) and len(options) >= 3:
                return {"options": options[:3]}
        lines = [l.strip().strip('"').strip('0123456789.、， ') for l in result.split("\n") if l.strip() and len(l.strip()) > 5]
        if len(lines) >= 3:
            return {"options": lines[:3]}
        return {"options": ["继续", "观察周围环境中的细节", "更粗暴的对待对方", "使用身上的物品试探对方", "对刚才的行为深感不安"]}
    except Exception as e:
        logger.warning("Suggest failed: %s", e)
        return {"options": ["继续", "观察周围环境中的细节", "更粗暴的对待对方", "使用身上的物品试探对方", "对刚才的行为深感不安"]}


async def _get_user_gender() -> str:
    db = await get_db()
    async with db.execute("SELECT value FROM settings WHERE key='user_gender'") as cur:
        row = await cur.fetchone()
    return (row["value"] if row else "") or ""


def _sub_char_fields(text: str, char_name: str, user_name: str = "你") -> str:
    """在组装 LLM 上下文时替换角色字段里残留的占位符"""
    for pat in ('{{char}}', '{{Char}}', '{{CHAR}}',
                '{char}', '{Char}', '{CHAR}',
                '<char>', '<Char>', '<CHAR>',
                '<bot>', '<Bot>', '<BOT>',
                '<assistant>', '<Assistant>'):
        text = text.replace(pat, char_name)
    for pat in ('{{user}}', '{{User}}', '{{USER}}',
                '{user}', '{User}', '{USER}',
                '<user>', '<User>', '<USER>',
                '<human>', '<Human>', '<HUMAN>'):
        text = text.replace(pat, user_name)
    return text


async def _build_system_prompt(plot: dict, characters: list, summary: str, mode: str = "classic", player_char_id: int | None = None) -> str:
    """构建系统提示词（不含 lorebook，保持静态以最大化 KV 缓存命中率）"""
    narrator = await load("narrator", mode)
    user_gender = await _get_user_gender()

    # 确定玩家角色（用户正在扮演的角色）
    player_char = None
    if player_char_id:
        player_char = next((c for c in characters if c['id'] == player_char_id), None)
    if player_char is None:
        player_char = next((c for c in characters if c.get('is_user')), None)

    char_desc = ""
    user_display_name = player_char['name'] if player_char else "你"
    for c in characters:
        cname = c['name'] or ''
        cdesc = _sub_char_fields(c.get('description') or '', cname, user_display_name)
        cpers = _sub_char_fields(c.get('personality') or '', cname, user_display_name)
        cevo = _sub_char_fields(c.get('personality_evolved') or '', cname, user_display_name)
        evo_suffix = f"\n  【性格/背景演变（随剧情发展，优先于原始设定）】\n{cevo}" if cevo.strip() else ""
        if player_char and c['id'] == player_char['id']:
            char_desc += f"\n【玩家角色·用户扮演】{cname}：{cdesc} 性格：{cpers}{evo_suffix}"
        elif not c.get("is_user"):
            char_desc += f"\n角色【{cname}】：{cdesc} 性格：{cpers}{evo_suffix}"

    pov = json.loads(plot.get("style_settings") or "{}").get("pov", "3rd")
    pov_str = {"1st": "第一人称", "2nd": "第二人称", "3rd": "第三人称"}.get(pov, "第三人称")

    gender_map = {"female": "女性", "女": "女性", "male": "男性", "男": "男性"}
    gender_str = gender_map.get(user_gender, "")

    system = narrator
    system += f"\n\n【故事标题】{plot['title']}"
    system += f"\n【叙事视角】{pov_str}"
    if gender_str:
        system += f'\n【用户性别】{gender_str}'
    if player_char:
        system += (
            f'\n【当前玩家角色】用户正在扮演【{player_char["name"]}】'
            f'（{player_char.get("description", "")}）。'
            f'用户的输入代表该角色的行动与对白，由用户主导，你不控制该角色。'
            f'叙事中提及该角色时使用其姓名【{player_char["name"]}】，不使用"你"。'
        )
    else:
        if gender_str:
            system += f'（故事中"你"为{gender_str}，叙事中必须与此一致）'
    if char_desc:
        system += f"\n\n【角色设定】{char_desc}"
    if plot.get("opening"):
        system += f"\n\n【故事开场】\n{plot['opening']}"
    if plot.get("backstory"):
        system += f"\n\n【世界背景】\n{plot['backstory']}"
    if summary:
        system += f"\n\n【历史记忆摘要】\n{summary}"

    # 🚨 关键规则必须放在系统提示词最末尾（LLM 对末尾指令的注意力最高）
    system += (
        "\n\n🚨🚨🚨 最优先规则 · 放在最后以确保执行 🚨🚨🚨"
        "\n1. 用户的每一条消息都代表已经发生的行动和对白。你的回复是 NPC 对这些已发生事件的反应。"
        "\n2. 绝对禁止把用户的话语或动作嵌入你的叙事中重新叙述。"
        "\n   错误：用户说'你觉得呢？' → 你写'他转头看向她：你觉得呢？' ← 这是复读，删除。"
        "\n   正确：用户说'你觉得呢？' → 你写'她没有立刻回答，手指在茶杯边缘慢慢画着圈。' ← NPC 反应。"
        "\n3. 你的回复直接从 NPC 的身体反应、表情变化或对白开始。不以任何形式的场景复述或动作回放开头。"
        "\n4. 不用 narration 行复述场景中已经发生的事。narration 只用于：NPC 的感官体验、环境变化、动作过渡。"
        "\n5. 【输出格式·不可违背】整条回复必须是 NDJSON：每行一个合法 JSON 对象，"
        '旁白写 {"type":"narration","content":"..."}，角色写 {"type":"character","name":"角色名","action":"动作","dialogue":"对白"}。'
        "严禁输出任何非 JSON 的散文段落、markdown 或代码块标记。"
        '对白与动作中若出现引号，必须用中文引号「」或转义，绝不能在 JSON 字符串里直接写未转义的 " 。'
    )

    return system


def _build_user_message(user_input: str, lorebook_injection: str) -> str:
    """将 lorebook 注入拼到用户消息头部（不进系统提示词，维持 KV 缓存稳定）"""
    result = ""
    if lorebook_injection:
        result += lorebook_injection.strip() + "\n\n"
    result += user_input
    return result


# 反复读前缀——直接注入到 user 消息末尾，LLM 生成前最后看到的字
_ANTI_REPEAT_PREFIX = (
    "\n\n[系统：以上用户消息中的内容已经发生，你的回复只需写NPC的反应——身体反应、行动、对白。"
    "禁止复述或转述用户说过的任何话、做过的任何动作。不要以用户角色为主语进行叙事。"
    "直接从NPC的回应开始写。]"
)

# 自动推进指令——每轮都是它，必须强制"实质进展 + 不自我复读"，否则静止场景会原地打转
_AUTO_ADVANCE_INSTRUCTION = (
    "（自动推进剧情。本轮必须让故事发生【新的实质进展】：让某个角色说出新的话、做出新的决定或行动、"
    "或触发新的事件，或让场景/时间/关系/局势发生改变。"
    "【严禁原地踏步】：不要重复或换一种措辞重写上几轮已经描写过的场景、姿态、动作或氛围"
    "（例如上一轮已经写过某人正在做的事，本轮绝不能再描写一遍）。"
    "若场景陷入静止，就主动引入推动力——有人开口挑起话题、有人起身离开或靠近、外部有人闯入或传来消息、时间推移。"
    "每一轮都要把故事往前推一步，而不是停留描写。）"
)


@router.post("")
async def chat_stream(body: ChatBody):
    db = await get_db()

    # 加载会话
    async with db.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session = dict(session)

    # 加载剧情和角色
    async with db.execute("SELECT * FROM plots WHERE id=?", (session["plot_id"],)) as cur:
        plot = await cur.fetchone()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情不存在")
    plot = dict(plot)

    async with db.execute(
        "SELECT * FROM characters WHERE plot_id=? ORDER BY id", (session["plot_id"],)
    ) as cur:
        characters = [dict(r) for r in await cur.fetchall()]

    # 加载挂载的 lorebook 条目
    async with db.execute(
        """SELECT le.keywords, le.content
           FROM lorebook_entries le
           JOIN lorebooks lb ON lb.id = le.lorebook_id
           JOIN plot_lorebooks pl ON pl.lorebook_id = lb.id
           WHERE pl.plot_id=?""",
        (session["plot_id"],),
    ) as cur:
        lb_entries = [dict(r) for r in await cur.fetchall()]

    # 全年龄向：固定使用 classic 模式
    mode = "classic"
    logger.info("chat  session=%d  mode=%s", body.session_id, mode)

    # 获取上下文消息
    summary, history = await get_context_messages(body.session_id)

    # Lorebook 注入
    scan_text = body.user_input
    if history:
        scan_text += " " + history[-1].get("content", "")
    matched = scan(scan_text, lb_entries)
    injection = build_injection(matched)

    # 构建系统提示词（静态：narrator + plot + chars + memory，不含 lorebook）
    system = await _build_system_prompt(plot, characters, summary, mode, player_char_id=body.player_character_id)

    # 自动推进模式：让 LLM 先扮演用户角色说/做一件事，再推进 NPC 反应
    auto_user_content = body.user_input  # 保存原始用户输入用于入库
    if body.auto_advance:
        auto_system = await load("auto_advance", mode)
        if not auto_system:
            auto_system = await load("auto_advance", "classic")

        player_char = None
        if body.player_character_id:
            player_char = next((c for c in characters if c['id'] == body.player_character_id), None)
        if player_char is None:
            player_char = next((c for c in characters if c.get('is_user')), None)
        pc_name = player_char['name'] if player_char else "主角"
        auto_system = auto_system.replace("玩家角色名", pc_name)
        system += f"\n\n{auto_system}"

    # 当前轮次 user 消息加角色前缀（让 LLM 明确知道谁在说话）
    player_char_for_prefix = None
    if body.player_character_id:
        player_char_for_prefix = next((c for c in characters if c['id'] == body.player_character_id), None)
    if player_char_for_prefix is None:
        player_char_for_prefix = next((c for c in characters if c.get('is_user')), None)
    player_name_prefix = f"【{player_char_for_prefix['name']}】：" if player_char_for_prefix else ""

    # lorebook 注入到当前用户消息，不动系统提示词 → KV 缓存命中历史对话
    if body.auto_advance:
        user_msg = _build_user_message(_AUTO_ADVANCE_INSTRUCTION, injection)
    else:
        user_msg = _build_user_message(player_name_prefix + body.user_input, injection)
    if not body.auto_advance:
        user_msg += _ANTI_REPEAT_PREFIX
    messages = history + [{"role": "user", "content": user_msg}]

    # 保存用户消息（含扮演角色元数据）—— 自动推进模式延迟到解析后再保存
    if not body.auto_advance:
        user_meta: dict = {}
        if body.player_character_id:
            user_meta["player_character_id"] = body.player_character_id
        await db.execute(
            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
            (body.session_id, body.user_input, "user", json.dumps(user_meta)),
        )
        await db.commit()

    async def event_generator():
        full_response = []
        try:
            async for chunk in llm_stream(messages, system=system):
                full_response.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            response_text = "".join(full_response)
            if response_text:
                _db = await get_db()

                # 自动推进模式
                if body.auto_advance:
                    # 占位 user 消息（保证轮次计数）
                    # 必须带 player_character_id，否则页面刷新后 _restorePlayerCharId 会 fallback 到 is_user=1
                    pn = player_char_for_prefix["name"] if player_char_for_prefix else "主角"
                    placeholder_meta: dict = {}
                    if body.player_character_id:
                        placeholder_meta["player_character_id"] = body.player_character_id
                    await _db.execute(
                        "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
                        (body.session_id, f"（{pn}默默观察着局势）", "user", json.dumps(placeholder_meta)),
                    )

                    # 完整 NDJSON 存为一条 assistant（保留 _player 供前端渲染）
                    # ⚠️ 不能用严格 json.loads 过滤——对白里未转义引号/缺括号的行虽然 parse 失败，
                    #    但仍是有效剧情，前端有 jsonrepair 容错。形似 JSON 的行一律原样保留，绝不丢内容。
                    cl = []
                    for l in response_text.split('\n'):
                        l = l.strip()
                        if not l:
                            continue
                        try:
                            json.loads(l)
                            cl.append(l)
                            continue
                        except Exception:
                            pass
                        # 解析失败但形似 NDJSON 行 → 原样保留，交给前端容错修复
                        if l.startswith('{') and '"type"' in l:
                            cl.append(l)

                    if cl:
                        am = json.dumps({"auto_advance": True}, ensure_ascii=False)
                        await _db.execute(
                            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
                            (body.session_id, '\n'.join(cl), "assistant", am),
                        )
                    else:
                        # 兜底：LLM 未输出合法 NDJSON，保存原始文本以免内容丢失
                        logger.warning("auto_advance: no valid NDJSON found, saving raw text  len=%d", len(response_text))
                        await _db.execute(
                            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
                            (body.session_id, response_text, "assistant", "{}"),
                        )
                    await _db.commit()

                    yield f"data: {json.dumps({'auto_advance_done': True}, ensure_ascii=False)}\n\n"
                else:
                    await _db.execute(
                        "INSERT INTO messages (session_id, content, role) VALUES (?,?,?)",
                        (body.session_id, response_text, "assistant"),
                    )
                    await _db.commit()

                # 每 SLOT_UPDATE_INTERVAL 轮对话触发一次记忆槽位更新
                msg_count = await count_messages(body.session_id)
                if msg_count > 0 and msg_count % SLOT_UPDATE_INTERVAL == 0:
                    logger.info("Memory update trigger  session=%d  round=%d", body.session_id, msg_count)
                    asyncio.create_task(
                        enqueue("memory_update", {"session_id": body.session_id})
                    )
                else:
                    logger.debug("Memory update skip  session=%d  round=%d  next_at=%d",
                                 body.session_id, msg_count,
                                 ((msg_count // SLOT_UPDATE_INTERVAL) + 1) * SLOT_UPDATE_INTERVAL)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )