import json
import logging
from db.database import get_db
from core.llm import chat
from core.prompt_loader import load

logger = logging.getLogger("galgame.memory")

WINDOW = 40  # 上下文消息窗口大小（宏大场景需要更多上下文）
SLOT_UPDATE_INTERVAL = 10  # 每 N 轮对话（user 消息）触发一次槽位更新


def _format_slots(slots: dict) -> str:
    """将记忆槽位 JSON 格式化为可注入系统提示的可读文本"""
    if not slots:
        return ""

    parts = []

    # 玩家角色状态
    player = slots.get("player", {})
    if player and any(player.values()):
        parts.append(f"【玩家角色·{player.get('name', '未知')}】")
        if player.get("state"):  parts.append(f"  当前状态：{player['state']}")
        if player.get("notes"):  parts.append(f"  重要经历：{player['notes']}")

    # NPC 状态（以角色名为 key 的字典）
    npcs = slots.get("npcs", {})
    if npcs:
        parts.append("【NPC 状态】")
        for name, npc in npcs.items():
            if not isinstance(npc, dict):
                continue
            line = f"  {name}："
            bits = []
            if npc.get("state"):    bits.append(f"状态·{npc['state']}")
            if npc.get("attitude"): bits.append(f"态度·{npc['attitude']}")
            if npc.get("revealed"): bits.append(f"已揭示·{npc['revealed']}")
            parts.append(line + "　".join(bits))

    # 角色关系网
    relations = slots.get("relations", [])
    if relations:
        parts.append("【关系网】")
        for rel in relations:
            a = rel.get("a", "")
            b = rel.get("b", "")
            rtype = rel.get("type", "")
            tension = rel.get("tension", "")
            line = f"  {a} ↔ {b}：{rtype}"
            if tension:
                line += f"（{tension}）"
            parts.append(line)

    # 当前场景
    scene = slots.get("scene", {})
    if scene and any(scene.values()):
        parts.append("【当前场景】")
        if scene.get("location"):   parts.append(f"  地点：{scene['location']}")
        if scene.get("time"):       parts.append(f"  时间：{scene['time']}")
        if scene.get("atmosphere"): parts.append(f"  基调：{scene['atmosphere']}")

    # 关键事件
    events = slots.get("events", [])
    if events:
        parts.append("【关键事件】")
        for e in events[-5:]:
            line = e.get("event", "")
            if e.get("location"):
                line = f"[{e['location']}] {line}"
            if e.get("impact"):
                line += f"→{e['impact']}"
            parts.append(f"  · {line}")

    # 悬念线索
    threads = slots.get("threads", [])
    active_threads = [t for t in threads if t.get("status") == "进行中"]
    if active_threads:
        parts.append("【悬念线索】")
        for t in active_threads:
            parts.append(f"  · {t.get('title', '')}")

    # 重要物品
    items = slots.get("items", [])
    if items:
        parts.append("【重要物品】")
        for i in items[-4:]:
            holder = f"（{i['holder']}）" if i.get("holder") else ""
            parts.append(f"  · {i.get('item', '')}{holder}：{i.get('note', '')}")

    # 隐藏数值机制（世界书定义的游戏数值）
    mechanics = slots.get("mechanics", {})
    if mechanics:
        parts.append("【隐藏数值】")
        for k, v in mechanics.items():
            parts.append(f"  {k}：{v}")

    return "\n".join(parts) if parts else ""


async def get_context_messages(session_id: int) -> tuple[str, list[dict]]:
    """返回 (formatted_memory, 最近 WINDOW 条 messages)"""
    db = await get_db()
    async with db.execute(
        "SELECT memory_summary, plot_id FROM sessions WHERE id=?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
    raw = (row["memory_summary"] if row else "") or "{}"
    plot_id = row["plot_id"] if row else None
    try:
        slots = json.loads(raw)
    except Exception:
        slots = {}
    summary = _format_slots(slots)

    # 构建角色 ID → 名字映射，用于给 user 消息加角色前缀
    char_id_to_name: dict[int, str] = {}
    if plot_id:
        async with db.execute(
            "SELECT id, name FROM characters WHERE plot_id=?", (plot_id,)
        ) as cur2:
            for cr in await cur2.fetchall():
                char_id_to_name[cr["id"]] = cr["name"]

    async with db.execute(
        """SELECT m.content, m.role, m.metadata
           FROM messages m
           WHERE m.session_id=? AND m.role NOT IN ('snapshot', 'chat_image', 'init')
           ORDER BY m.id DESC LIMIT ?""",
        (session_id, WINDOW),
    ) as cur:
        rows = await cur.fetchall()

    msgs = []
    for r in reversed(rows):
        role = r["role"]
        content = r["content"]
        if role == "user":
            # 从 metadata 中读取当轮扮演角色，加前缀让 LLM 知道谁在说话
            try:
                meta = json.loads(r["metadata"] or "{}")
                pc_id = meta.get("player_character_id")
                if pc_id and pc_id in char_id_to_name:
                    content = f"【{char_id_to_name[pc_id]}】：{content}"
            except Exception:
                pass
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "assistant", "content": content})
    return summary, msgs


async def count_messages(session_id: int) -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE session_id=? AND role='user'",
        (session_id,),
    ) as cur:
        row = await cur.fetchone()
    return row["cnt"] if row else 0


_EVOLVED_MAX_LEN = 1200          # personality_evolved 滚动长度上限（防提示词膨胀）
_DYNAMIC_LOREBOOK_TITLE = "📜 剧情演变"


def _match_character(name: str, chars: list[dict]) -> dict | None:
    """按角色名或别名匹配 plot 内的角色，匹配不到返回 None。"""
    if not name:
        return None
    name = name.strip()
    for c in chars:
        if (c["name"] or "").strip() == name:
            return c
    for c in chars:
        try:
            aliases = json.loads(c["aliases"] or "[]")
        except Exception:
            aliases = []
        if any((a or "").strip() == name for a in aliases):
            return c
    return None


def _append_evolved(existing: str, change: str, reason: str) -> str:
    """把一条演变追加进 personality_evolved（追加式 + 滚动长度上限）。"""
    change = (change or "").strip()
    if not change:
        return existing
    entry = f"· {change}" + (f"（因：{reason.strip()}）" if reason and reason.strip() else "")
    lines = [l for l in (existing or "").split("\n") if l.strip()]
    if entry in lines:           # 去重，避免重复写同一条
        return existing
    lines.append(entry)
    text = "\n".join(lines)
    # 超长则从最旧的丢起
    while len(text) > _EVOLVED_MAX_LEN and len(lines) > 1:
        lines.pop(0)
        text = "\n".join(lines)
    return text


async def _get_or_create_dynamic_lorebook(db, plot_id: int) -> int:
    """取得（或创建并挂载）该 plot 的「剧情演变」动态世界书，返回 lorebook id。"""
    async with db.execute(
        """SELECT lb.id FROM lorebooks lb
           JOIN plot_lorebooks pl ON pl.lorebook_id = lb.id
           WHERE pl.plot_id=? AND lb.title=?""",
        (plot_id, _DYNAMIC_LOREBOOK_TITLE),
    ) as cur:
        row = await cur.fetchone()
    if row:
        return row["id"]
    async with db.execute(
        "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
        (_DYNAMIC_LOREBOOK_TITLE, "随剧情自动生成的新世界规则"),
    ) as cur:
        lb_id = (await cur.fetchone())[0]
    await db.execute(
        "INSERT OR IGNORE INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
        (plot_id, lb_id),
    )
    return lb_id


def _clean_keywords(raw) -> list[str]:
    """校验关键词：去重、去空白、过滤单字（子串匹配易过度触发）。"""
    if not isinstance(raw, list):
        return []
    seen, out = set(), []
    for k in raw:
        k = (str(k) if k is not None else "").strip()
        if len(k) >= 2 and k not in seen:
            seen.add(k)
            out.append(k)
    return out


async def _apply_evolution(db, session_id: int, plot_id: int, evolution: dict, round_no: int):
    """把 memory_mgr 输出的 evolution 落库：角色性格/背景演变 + 新增世界规则。"""
    if not isinstance(evolution, dict):
        return

    # ── 角色性格/背景演变 ──────────────────────────────────────────
    char_changes = evolution.get("characters") or []
    if isinstance(char_changes, list) and char_changes:
        async with db.execute(
            "SELECT id, name, aliases, personality_evolved FROM characters WHERE plot_id=?",
            (plot_id,),
        ) as cur:
            chars = [dict(r) for r in await cur.fetchall()]
        applied = 0
        for ch in char_changes:
            if not isinstance(ch, dict):
                continue
            target = _match_character(ch.get("name", ""), chars)
            if not target:
                continue
            change, reason = ch.get("change", ""), ch.get("reason", "")
            new_evolved = _append_evolved(target.get("personality_evolved") or "", change, reason)
            if new_evolved == (target.get("personality_evolved") or ""):
                continue  # 无实际变化（空或重复）
            await db.execute(
                "UPDATE characters SET personality_evolved=? WHERE id=?",
                (new_evolved, target["id"]),
            )
            await db.execute(
                """INSERT INTO character_evolution_log (character_id, session_id, round, change, reason)
                   VALUES (?,?,?,?,?)""",
                (target["id"], session_id, round_no, (change or "").strip(), (reason or "").strip()),
            )
            target["personality_evolved"] = new_evolved  # 同步本地，支持同轮多条
            applied += 1
        if applied:
            logger.info("Evolution: %d character(s) evolved  session=%d", applied, session_id)

    # ── 新增世界规则 ──────────────────────────────────────────────
    rules = evolution.get("world_rules") or []
    if isinstance(rules, list) and rules:
        lb_id = None
        added = 0
        # 当前序号（追加到末尾）
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            content = (rule.get("content") or "").strip()
            keywords = _clean_keywords(rule.get("keywords"))
            if not content or not keywords:
                continue
            if lb_id is None:
                lb_id = await _get_or_create_dynamic_lorebook(db, plot_id)
            async with db.execute(
                "SELECT COALESCE(MAX(order_idx), -1) + 1 AS nxt FROM lorebook_entries WHERE lorebook_id=?",
                (lb_id,),
            ) as cur:
                order_idx = (await cur.fetchone())["nxt"]
            await db.execute(
                "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx, round) VALUES (?,?,?,?,?)",
                (lb_id, json.dumps(keywords, ensure_ascii=False), content, order_idx, round_no),
            )
            added += 1
        if added:
            logger.info("Evolution: %d world-rule(s) added  session=%d", added, session_id)

    await db.commit()


async def rollback_to_round(session_id: int, plot_id: int | None, keep_round: int) -> int:
    """撤回消息后，把记忆 / 角色演变 / 世界规则回滚到保留 ≤keep_round 轮的状态。
    ⚠️ 安全原则（防误伤）：只删【被撤回的轮次 round>keep_round】，保留轮次内(≤keep_round)的
       演变/世界规则一律保留。没有可用记忆快照时【不动记忆】，绝不清空。
    回滚后调用方应再触发一次静默 memory_update 让剩余轮次被重放。返回 keep_round。
    """
    db = await get_db()
    # 1) 记忆：有 ≤keep_round 的快照就恢复；没有则【保持不动】，避免清空误伤
    async with db.execute(
        "SELECT memory_summary FROM memory_snapshots WHERE session_id=? AND round<=? ORDER BY round DESC LIMIT 1",
        (session_id, keep_round),
    ) as cur:
        snap = await cur.fetchone()
    if snap:
        await db.execute("UPDATE sessions SET memory_summary=? WHERE id=?", (snap["memory_summary"], session_id))
    # 清掉被撤回轮次的快照
    await db.execute("DELETE FROM memory_snapshots WHERE session_id=? AND round>?", (session_id, keep_round))

    if plot_id is not None:
        # 2) 角色演变：只删【被撤回轮次 round>keep_round】的日志，保留 ≤keep_round；重建 personality_evolved
        async with db.execute("SELECT id FROM characters WHERE plot_id=?", (plot_id,)) as cur:
            char_ids = [r["id"] for r in await cur.fetchall()]
        await db.execute(
            "DELETE FROM character_evolution_log WHERE round>? AND character_id IN (SELECT id FROM characters WHERE plot_id=?)",
            (keep_round, plot_id),
        )
        for cid in char_ids:
            evolved = ""
            async with db.execute(
                "SELECT change, reason FROM character_evolution_log WHERE character_id=? ORDER BY id", (cid,)
            ) as cur:
                for r in await cur.fetchall():
                    evolved = _append_evolved(evolved, r["change"], r["reason"])
            await db.execute("UPDATE characters SET personality_evolved=? WHERE id=?", (evolved, cid))
        # 3) 世界规则：只删动态"剧情演变"书里【被撤回轮次 round>keep_round】的条目
        await db.execute(
            """DELETE FROM lorebook_entries WHERE round>? AND lorebook_id IN (
                   SELECT lb.id FROM lorebooks lb JOIN plot_lorebooks pl ON pl.lorebook_id=lb.id
                   WHERE pl.plot_id=? AND lb.title=?
               )""",
            (keep_round, plot_id, _DYNAMIC_LOREBOOK_TITLE),
        )
    await db.commit()
    logger.info("Rollback  session=%d  keep_round=%d (只删被撤回轮次)", session_id, keep_round)
    return keep_round


async def update_slots(session_id: int):
    """增量更新记忆槽位：读取当前 JSON + 最近20条消息 → LLM → 写回"""
    db = await get_db()

    # 加载会话 + 关联剧情的模式
    async with db.execute(
        "SELECT memory_summary, plot_id FROM sessions WHERE id=?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
    current_raw = (row["memory_summary"] if row else "") or "{}"
    plot_id = row["plot_id"] if row else None
    try:
        current_slots = json.loads(current_raw)
    except Exception:
        current_slots = {}

    # 读取最近消息（含 metadata 以识别玩家角色）
    async with db.execute(
        """SELECT content, role, metadata FROM messages
           WHERE session_id=? AND role IN ('user','assistant')
           ORDER BY id DESC LIMIT 20""",
        (session_id,),
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return

    # 从最近的 user 消息 metadata 中找玩家角色 ID
    player_char_name = None
    for r in rows:
        if r["role"] == "user" and r["metadata"]:
            try:
                meta = json.loads(r["metadata"])
                pc_id = meta.get("player_character_id")
                if pc_id and plot_id:
                    async with db.execute(
                        "SELECT name FROM characters WHERE id=? AND plot_id=?",
                        (pc_id, plot_id),
                    ) as cur2:
                        char_row = await cur2.fetchone()
                    if char_row:
                        player_char_name = char_row["name"]
                        break
            except Exception:
                pass

    # 格式化对话历史（user 消息用玩家角色名标注，更准确）
    def _label(r):
        if r["role"] == "user":
            return player_char_name or "玩家"
        return "叙事者"

    recent_text = "\n".join(
        f"{_label(r)}: {r['content'][:300]}"
        for r in reversed(rows)
    )

    system_prompt = await load("memory_mgr")
    context_hint = ""
    if player_char_name:
        context_hint = f'【当前玩家角色】{player_char_name}（即对话中的"玩家"，由用户扮演）\n\n'

    prompt = (
        f"{context_hint}"
        f"当前记忆槽位：\n{json.dumps(current_slots, ensure_ascii=False, indent=2)}"
        f"\n\n最近对话：\n{recent_text}"
    )

    try:
        result = await chat(
            [{"role": "user", "content": prompt}],
            system=system_prompt,
            max_tokens=3000,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = result.strip()
        # 剥离可能的 markdown 代码块
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        new_slots = json.loads(result)
        # 剥离演变层（不存进记忆槽位，单独落到 characters 表 / 动态世界书）
        evolution = new_slots.pop("evolution", None)
        round_no = await count_messages(session_id)
        new_slots["_updated_at_round"] = round_no
        summary_json = json.dumps(new_slots, ensure_ascii=False)
        await db.execute(
            "UPDATE sessions SET memory_summary=? WHERE id=?",
            (summary_json, session_id),
        )
        # 存一份带 round 的记忆快照（撤回消息时回滚用）；每会话只保留最近 30 份
        await db.execute(
            "INSERT INTO memory_snapshots (session_id, round, memory_summary) VALUES (?,?,?)",
            (session_id, round_no, summary_json),
        )
        await db.execute(
            """DELETE FROM memory_snapshots WHERE session_id=? AND id NOT IN (
                   SELECT id FROM memory_snapshots WHERE session_id=? ORDER BY id DESC LIMIT 30
               )""",
            (session_id, session_id),
        )
        await db.commit()
        logger.info("Memory slots updated  session=%d  round=%d", session_id, round_no)

        # 应用角色性格/背景演变 + 世界规则新增（容错，绝不影响记忆主流程）
        if evolution and plot_id:
            try:
                await _apply_evolution(db, session_id, plot_id, evolution, round_no)
            except Exception as ee:
                logger.error("Evolution apply FAIL  session=%d  error=%s", session_id, ee)
    except Exception as e:
        logger.error("Memory slots FAIL  session=%d  error=%s", session_id, e)