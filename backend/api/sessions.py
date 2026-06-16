import asyncio
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_db
from tasks.worker import enqueue

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSession(BaseModel):
    plot_id: int
    title: str = "新会话"


@router.get("")
async def list_sessions(plot_id: int | None = None):
    db = await get_db()
    if plot_id:
        async with db.execute(
            "SELECT * FROM sessions WHERE plot_id=? ORDER BY created_at DESC", (plot_id,)
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute("SELECT * FROM sessions ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("")
async def create_session(body: CreateSession):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM plots WHERE id=?", (body.plot_id,)
    ) as cur:
        plot = await cur.fetchone()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情不存在")

    async with db.execute(
        "INSERT INTO sessions (plot_id, title) VALUES (?,?) RETURNING id",
        (body.plot_id, body.title),
    ) as cur:
        row = await cur.fetchone()
    session_id = row[0]
    await db.commit()

    # 注入 Opening + Backstory 作为展示用消息（role="init"，不进 LLM 上下文，避免污染格式示例）
    opening = plot["opening"] or ""
    backstory = plot["backstory"] or ""
    if opening or backstory:
        init_content = ""
        if backstory:
            init_content += f"【故事背景】\n{backstory}\n\n"
        if opening:
            init_content += f"【故事开场】\n{opening}"
        await db.execute(
            "INSERT INTO messages (session_id, content, role) VALUES (?,?,?)",
            (session_id, init_content.strip(), "init"),
        )
        await db.commit()

    # 异步触发开场背景图生成（不阻塞响应）
    async def _trigger_bg():
        try:
            from api.image_chat import opening_bg
            from pydantic import BaseModel as BM
            class _B(BM):
                session_id: int
            await opening_bg(_B(session_id=session_id))
        except Exception:
            pass
    asyncio.create_task(_trigger_bg())

    return {"session_id": session_id, "plot_id": body.plot_id}


@router.get("/{session_id}")
async def get_session(session_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session = dict(session)

    async with db.execute(
        "SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)
    ) as cur:
        messages = [dict(r) for r in await cur.fetchall()]
    session["messages"] = messages
    return session


@router.get("/{session_id}/memory")
async def get_session_memory(session_id: int):
    """返回会话的记忆槽位 JSON + 轮次进度"""
    db = await get_db()
    async with db.execute("SELECT memory_summary FROM sessions WHERE id=?", (session_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    raw = row["memory_summary"] or "{}"
    try:
        slots = json.loads(raw)
    except Exception:
        slots = {}
    from core.memory import count_messages, SLOT_UPDATE_INTERVAL
    current_round = await count_messages(session_id)
    updated_at_round = slots.pop("_updated_at_round", 0)
    return {
        "session_id": session_id,
        "slots": slots,
        "current_round": current_round,
        "updated_at_round": updated_at_round,
        "interval": SLOT_UPDATE_INTERVAL,
    }


@router.delete("/{session_id}/messages/from/{message_id}")
async def trim_messages_from(session_id: int, message_id: int, rollback: bool = False):
    """删除 message_id 及其之后的所有消息。
    rollback=True（用户主动撤回）时，连带把记忆/角色演变/世界规则回滚到撤回点之前，
    再静默触发一次记忆更新重放剩余轮次（精确回滚、用户无感知）。
    rollback=False（重生成）时只删消息，不动记忆——重生成在同一轮次框架内，无需回滚。
    """
    db = await get_db()

    keep_round = 0
    plot_id = None
    if rollback:
        # 撤回后保留的轮次数 = message_id 之前的 user 消息数
        async with db.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id=? AND role='user' AND id<?",
            (session_id, message_id),
        ) as cur:
            keep_round = (await cur.fetchone())["n"]
        async with db.execute("SELECT plot_id FROM sessions WHERE id=?", (session_id,)) as cur:
            srow = await cur.fetchone()
        plot_id = srow["plot_id"] if srow else None

    await db.execute(
        "DELETE FROM messages WHERE session_id=? AND id>=?",
        (session_id, message_id),
    )
    await db.commit()

    if rollback:
        from core.memory import rollback_to_round, count_messages
        from tasks.worker import enqueue as _enqueue
        await rollback_to_round(session_id, plot_id, keep_round)
        # 仍有对话则静默补算，让 restore_round+1..keep_round 被重放
        if await count_messages(session_id) > 0:
            await _enqueue("memory_update", {"session_id": session_id})

    return {"ok": True}


@router.delete("/{session_id}/messages/clear")
async def clear_messages(session_id: int):
    """清空对话消息并重置记忆槽位（保留 init 开场白和 system 系统通知）。
    同时重置随剧情累积的演变层：角色性格/背景演变、演变日志、自动生成的「剧情演变」世界书——
    清空即视为全新开始，演变不应残留。
    """
    db = await get_db()
    async with db.execute("SELECT plot_id FROM sessions WHERE id=?", (session_id,)) as cur:
        srow = await cur.fetchone()
    plot_id = srow["plot_id"] if srow else None

    await db.execute(
        "DELETE FROM messages WHERE session_id=? AND role NOT IN ('init', 'system')",
        (session_id,),
    )
    # 同步重置记忆槽位，避免旧状态（角色死亡/数值残留）与全新对话产生悖论
    await db.execute(
        "UPDATE sessions SET memory_summary='{}' WHERE id=?",
        (session_id,),
    )
    if plot_id is not None:
        # 重置角色演变层 + 清空演变日志
        await db.execute(
            "UPDATE characters SET personality_evolved='' WHERE plot_id=?",
            (plot_id,),
        )
        await db.execute(
            """DELETE FROM character_evolution_log
               WHERE character_id IN (SELECT id FROM characters WHERE plot_id=?)""",
            (plot_id,),
        )
        # 删除自动生成的「剧情演变」动态世界书（条目随 lorebook 级联删除）
        await db.execute(
            """DELETE FROM lorebooks WHERE title='📜 剧情演变' AND id IN (
                   SELECT lorebook_id FROM plot_lorebooks WHERE plot_id=?
               )""",
            (plot_id,),
        )
    await db.commit()
    return {"ok": True}


@router.delete("/{session_id}/messages/{message_id}")
async def delete_message(session_id: int, message_id: int):
    """删除单条消息"""
    db = await get_db()
    await db.execute(
        "DELETE FROM messages WHERE session_id=? AND id=?",
        (session_id, message_id),
    )
    await db.commit()
    return {"ok": True}


class PatchSession(BaseModel):
    bg_image_url: str | None = None


@router.patch("/{session_id}")
async def patch_session(session_id: int, body: PatchSession):
    db = await get_db()
    if body.bg_image_url is not None:
        await db.execute(
            "UPDATE sessions SET bg_image_url=? WHERE id=?",
            (body.bg_image_url, session_id),
        )
        await db.commit()
    return {"ok": True}


@router.post("/{session_id}/memory/checkpoint")
async def trigger_memory_checkpoint(session_id: int):
    """手动触发一次记忆槽位更新（存档）—— 仅当前轮次高于上次更新轮次时写入"""
    import logging as _logging
    from core.memory import update_slots, count_messages
    from tasks.worker import enqueue as _enqueue

    db = await get_db()
    async with db.execute("SELECT memory_summary FROM sessions WHERE id=?", (session_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")

    raw = row["memory_summary"] or "{}"
    try:
        slots = json.loads(raw)
    except Exception:
        slots = {}

    current_round = await count_messages(session_id)
    updated_at_round = slots.get("_updated_at_round", 0)

    if current_round <= updated_at_round:
        raise HTTPException(status_code=400, detail=f"无新对话内容（当前 {current_round} 轮 ≤ 已存档 {updated_at_round} 轮），无需存档")

    _log = _logging.getLogger("galgame.memory")
    _log.info("Manual checkpoint  session=%d  round=%d  last_round=%d", session_id, current_round, updated_at_round)
    task_id = await _enqueue("memory_update", {"session_id": session_id})
    return {"task_id": task_id, "message": f"记忆存档已入队（当前 {current_round} 轮，上次存档 {updated_at_round} 轮）"}


@router.delete("/{session_id}")
async def delete_session(session_id: int):
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    await db.commit()
    return {"ok": True}