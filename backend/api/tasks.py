from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_db
from tasks.worker import enqueue

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class RetryBody(BaseModel):
    task_id: str


@router.get("")
async def list_tasks(session_id: int | None = None):
    db = await get_db()
    if session_id:
        async with db.execute(
            "SELECT * FROM tasks WHERE payload LIKE ? ORDER BY created_at DESC",
            (f'%"session_id": {session_id}%',),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{task_id}")
async def get_task(task_id: str):
    db = await get_db()
    async with db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    return dict(row)


@router.post("/retry")
async def retry_task(body: RetryBody):
    db = await get_db()
    async with db.execute("SELECT * FROM tasks WHERE id=?", (body.task_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    await db.execute(
        "UPDATE tasks SET status='pending', error='', updated_at=datetime('now') WHERE id=?",
        (body.task_id,),
    )
    await db.commit()
    return {"ok": True, "task_id": body.task_id}
