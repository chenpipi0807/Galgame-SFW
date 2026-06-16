from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_db
from core.llm import chat
from core.prompt_loader import load
from tasks.worker import enqueue
import json as _json

router = APIRouter(prefix="/api/snapshot", tags=["snapshot"])


class SnapshotBody(BaseModel):
    session_id: int


@router.post("")
async def create_snapshot(body: SnapshotBody):
    db = await get_db()
    async with db.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 取最近 5 条 assistant 消息
    async with db.execute(
        """SELECT content FROM messages
           WHERE session_id=? AND role='assistant'
           ORDER BY id DESC LIMIT 5""",
        (body.session_id,),
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        raise HTTPException(status_code=400, detail="暂无叙事内容可生成场景图")

    context = "\n\n".join(r["content"] for r in reversed(rows))
    # 叙事模式（全年龄向：固定 classic）
    mode = "classic"
    system = await load("snapshot", mode)
    img_prompt = await chat(
        [{"role": "user", "content": f"请根据以下叙事内容生成场景图 prompt：\n\n{context}"}],
        system=system,
        max_tokens=8192,
    )
    img_prompt = img_prompt.strip()

    # 获取本剧情所有角色参考图（含玩家角色，确保主角外貌正确）
    reference_images: list[str] = []
    try:
        async with db.execute(
            "SELECT avatar_url, reference_image FROM characters WHERE plot_id=?",
            (session["plot_id"],),
        ) as cur:
            chars = await cur.fetchall()
        for c in chars:
            ref = c["avatar_url"] or c["reference_image"]
            if ref and ref.startswith(("http", "/uploads", "data:")):
                reference_images.append(ref)
    except Exception:
        pass

    task_id = await enqueue(
        "snapshot",
        {"prompt": img_prompt, "session_id": body.session_id, "reference_images": reference_images},
    )
    return {"task_id": task_id, "prompt": img_prompt}
