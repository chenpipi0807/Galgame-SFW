import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_db

router = APIRouter(prefix="/api/lorebooks", tags=["lorebooks"])


class LorbookCreate(BaseModel):
    title: str
    description: str = ""
    entries: list[dict] = []


class LorbookUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    entries: list[dict] | None = None


@router.get("")
async def list_lorebooks():
    db = await get_db()
    async with db.execute("SELECT * FROM lorebooks ORDER BY created_at DESC") as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    return rows


@router.post("")
async def create_lorebook(body: LorbookCreate):
    db = await get_db()
    async with db.execute(
        "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
        (body.title, body.description),
    ) as cur:
        row = await cur.fetchone()
    lb_id = row[0]
    await db.commit()
    for i, entry in enumerate(body.entries):
        await db.execute(
            "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
            (
                lb_id,
                json.dumps(entry.get("keywords", []), ensure_ascii=False),
                entry.get("content", ""),
                i,
            ),
        )
    await db.commit()
    return {"id": lb_id}


@router.get("/{lb_id}")
async def get_lorebook(lb_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM lorebooks WHERE id=?", (lb_id,)) as cur:
        lb = await cur.fetchone()
    if not lb:
        raise HTTPException(status_code=404, detail="Lorebook 不存在")
    lb = dict(lb)
    async with db.execute(
        "SELECT * FROM lorebook_entries WHERE lorebook_id=? ORDER BY order_idx", (lb_id,)
    ) as cur:
        entries = []
        for r in await cur.fetchall():
            e = dict(r)
            e["keywords"] = json.loads(e["keywords"])
            entries.append(e)
    lb["entries"] = entries
    return lb


@router.put("/{lb_id}")
async def update_lorebook(lb_id: int, body: LorbookUpdate):
    db = await get_db()
    async with db.execute("SELECT id FROM lorebooks WHERE id=?", (lb_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Lorebook 不存在")

    if body.title is not None or body.description is not None:
        updates = {}
        if body.title is not None:
            updates["title"] = body.title
        if body.description is not None:
            updates["description"] = body.description
        sets = ", ".join(f"{k}=?" for k in updates)
        await db.execute(f"UPDATE lorebooks SET {sets} WHERE id=?", (*updates.values(), lb_id))

    if body.entries is not None:
        await db.execute("DELETE FROM lorebook_entries WHERE lorebook_id=?", (lb_id,))
        for i, entry in enumerate(body.entries):
            await db.execute(
                "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
                (
                    lb_id,
                    json.dumps(entry.get("keywords", []), ensure_ascii=False),
                    entry.get("content", ""),
                    i,
                ),
            )

    await db.commit()
    return {"ok": True}


@router.delete("/{lb_id}")
async def delete_lorebook(lb_id: int):
    db = await get_db()
    await db.execute("DELETE FROM lorebooks WHERE id=?", (lb_id,))
    await db.commit()
    return {"ok": True}
