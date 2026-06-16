import io
import uuid
import base64
import zipfile
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.paths import SYSPROMPT_DIR, README_PATH
from db.database import get_db, DB_PATH, UPLOADS_DIR
from core.prompt_loader import list_prompts, list_modes, load, save, invalidate
from core.env_config import read as env_read, write as env_write

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/readme")
async def get_readme():
    if README_PATH.exists():
        return {"content": README_PATH.read_text("utf-8")}
    raise HTTPException(status_code=404, detail="README.md 不存在")


class ConfigUpdate(BaseModel):
    api_key: str


class PromptUpdate(BaseModel):
    content: str


class AvatarUpload(BaseModel):
    data: str  # base64 data URI 或 "" 清空


class GenderUpdate(BaseModel):
    gender: str  # "female" / "male" / ""


@router.get("/config")
async def get_config():
    cfg = env_read()
    key = cfg.get("AGNES_API_KEY", "")
    masked = key[:8] + "***" + key[-4:] if len(key) > 12 else ("***" if key else "")
    return {"api_key": masked, "has_key": bool(key)}


@router.post("/config")
async def update_config(body: ConfigUpdate):
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    env_write(AGNES_API_KEY=body.api_key.strip())
    return {"ok": True}


class ModeUpdate(BaseModel):
    mode: str  # 仅 "classic"（本项目为全年龄向，不提供其它模式）


@router.get("/mode")
async def get_mode():
    # 全年龄向：固定返回 classic
    return {"mode": "classic", "modes": ["classic"]}


@router.put("/mode")
async def update_mode(body: ModeUpdate):
    # 全年龄向：只允许 classic，拒绝任何其它模式
    if body.mode != "classic":
        raise HTTPException(status_code=400, detail="本项目为全年龄向，mode 仅接受 classic")
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('narrative_mode', 'classic')",
    )
    await db.commit()
    return {"ok": True, "mode": "classic"}


@router.get("/prompts")
async def get_prompts(mode: str = "classic"):
    return {"prompts": list_prompts(mode), "mode": mode, "modes": list_modes()}


@router.get("/prompts/{name}")
async def get_prompt(name: str, mode: str = "classic"):
    path = SYSPROMPT_DIR / mode / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="提示词文件不存在")
    content = await load(name, mode)
    return {"name": name, "content": content}


@router.put("/prompts/{name}")
async def update_prompt(name: str, body: PromptUpdate, mode: str = "classic"):
    allowed = list_prompts(mode)
    if name not in allowed:
        raise HTTPException(status_code=400, detail=f"不允许编辑此文件，可用：{allowed}")
    await save(name, body.content, mode)
    invalidate(name)
    return {"ok": True}


@router.get("/user-avatar")
async def get_user_avatar():
    db = await get_db()
    async with db.execute("SELECT value FROM settings WHERE key='user_avatar'") as cur:
        row = await cur.fetchone()
    url = row["value"] if row else ""
    return {"url": url}


@router.post("/user-avatar")
async def upload_user_avatar(body: AvatarUpload):
    """上传用户头像（base64 data URI）"""
    url = ""
    if body.data:
        m = body.data.split(",", 1)
        if len(m) != 2 or "base64" not in m[0]:
            raise HTTPException(status_code=400, detail="无效的 base64 数据")
        header, b64data = m
        ext = "png" if "png" in header else ("webp" if "webp" in header else "jpg")
        filename = f"user_avatar_{uuid.uuid4().hex[:8]}.{ext}"
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / filename).write_bytes(base64.b64decode(b64data))
        url = f"/uploads/{filename}"

    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('user_avatar', ?)", (url,)
    )
    await db.commit()
    return {"url": url}


@router.get("/user-gender")
async def get_user_gender():
    db = await get_db()
    async with db.execute("SELECT value FROM settings WHERE key='user_gender'") as cur:
        row = await cur.fetchone()
    return {"gender": row["value"] if row else ""}


@router.post("/user-gender")
async def update_user_gender(body: GenderUpdate):
    if body.gender not in ("female", "male", ""):
        raise HTTPException(status_code=400, detail="gender 只接受 female / male / 空字符串")
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('user_gender', ?)",
        (body.gender,),
    )
    await db.commit()
    return {"ok": True}


# ── Provider 管理（通用「连接列表」模型，存本地 DB，见 core/providers.py）────────
from core import providers as _prov


class ProviderCreate(BaseModel):
    kind: str            # "llm" | "image"
    label: str
    api_type: str        # llm: "openai" / image: "openai-image" | "gemini"
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class ProviderUpdate(BaseModel):
    label: str | None = None
    api_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None   # 留空表示不修改 key
    model: str | None = None


class ProviderTestBody(BaseModel):
    api_type: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    id: str = ""        # 提供 id 时，key 留空则取该连接已存值


def _mask(key: str) -> str:
    if not key or len(key) <= 8:
        return "***" if key else ""
    return key[:6] + "***" + key[-4:]


def _public_provider(p: dict) -> dict:
    """对外返回：key 掩码 + has_key（内置 Agnes 视为始终有 key）。"""
    has_key = bool(p.get("builtin") or p.get("api_key"))
    return {
        "id": p.get("id"),
        "kind": p.get("kind"),
        "label": p.get("label", ""),
        "api_type": p.get("api_type", ""),
        "base_url": p.get("base_url", ""),
        "model": p.get("model", ""),
        "builtin": bool(p.get("builtin")),
        "key": "内置" if p.get("builtin") else _mask(p.get("api_key", "")),
        "has_key": has_key,
    }


@router.get("/providers")
async def get_providers():
    cfg = _prov.list_providers()
    return {
        "providers": [_public_provider(p) for p in cfg.get("providers", [])],
        "active_llm": cfg.get("active_llm"),
        "active_image": cfg.get("active_image"),
    }


@router.post("/providers")
async def create_provider(body: ProviderCreate):
    if body.kind not in ("llm", "image"):
        raise HTTPException(status_code=400, detail="kind 只接受 llm / image")
    if not body.label.strip():
        raise HTTPException(status_code=400, detail="名字不能为空")
    valid = {"llm": ("openai",), "image": ("openai-image", "gemini")}
    if body.api_type not in valid[body.kind]:
        raise HTTPException(status_code=400, detail=f"{body.kind} 不支持类型 {body.api_type}")
    pid = await _prov.add_provider(
        kind=body.kind, label=body.label.strip(), api_type=body.api_type,
        base_url=body.base_url.strip(), api_key=body.api_key.strip(), model=body.model.strip(),
    )
    return {"ok": True, "id": pid}


@router.put("/providers/{pid}")
async def edit_provider(pid: str, body: ProviderUpdate):
    ok = await _prov.update_provider(
        pid,
        label=body.label.strip() if body.label is not None else None,
        api_type=body.api_type,
        base_url=body.base_url.strip() if body.base_url is not None else None,
        api_key=body.api_key.strip() if body.api_key else None,
        model=body.model.strip() if body.model is not None else None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="连接不存在")
    return {"ok": True}


@router.delete("/providers/{pid}")
async def remove_provider(pid: str):
    try:
        ok = await _prov.delete_provider(pid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="连接不存在")
    return {"ok": True}


@router.put("/providers/{pid}/activate")
async def activate_provider(pid: str):
    ok = await _prov.set_active(pid)
    if not ok:
        raise HTTPException(status_code=404, detail="连接不存在")
    return {"ok": True}


@router.post("/providers/test")
async def test_provider(body: ProviderTestBody):
    """按 api_type 做连通性测试；带 id 且 key 留空时取该连接已存的 key。"""
    key = body.api_key.strip()
    base = body.base_url.strip().rstrip("/")
    model = body.model.strip()
    if body.id and not key:
        # 用 id 解析为运行时配置（内置 Agnes 会注入正确的 base/key/model，避免误用默认地址）
        rc = _prov.resolved_config(body.id)
        if rc:
            key = key or rc.get("key", "")
            base = base or (rc.get("base_url", "")).rstrip("/")
            model = model or rc.get("model", "")

    try:
        client = httpx.AsyncClient(timeout=15.0, trust_env=False)
        try:
            if body.api_type == "openai":
                if not key:
                    return {"ok": False, "msg": "未填写 API Key"}
                base = base or "https://api.deepseek.com"
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model or "gpt-4o-mini",
                          "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                )
                resp.raise_for_status()
                return {"ok": True, "msg": f"连接正常（{resp.status_code}）"}

            if body.api_type == "openai-image":
                if not key:
                    return {"ok": False, "msg": "未填写 API Key"}
                base = base or "https://aihubmix.com/v1"
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
                if resp.status_code in (200, 401):
                    ok = resp.status_code == 200
                    return {"ok": ok, "msg": f"{'连接正常' if ok else 'Key 无效'}（{resp.status_code}）"}
                resp.raise_for_status()
                return {"ok": True, "msg": f"连接正常（{resp.status_code}）"}

            if body.api_type == "gemini":
                if not key:
                    return {"ok": False, "msg": "未填写 API Key"}
                if not base:
                    return {"ok": False, "msg": "未填写 Base URL"}
                m = model or "gemini-3.1-flash-image-preview"
                url = (f"{base}/models/{m}:generateContent" if "v1beta" in base
                       else f"{base}/v1beta/models/{m}:generateContent")
                resp = await client.post(
                    url, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json={"contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
                          "generationConfig": {"maxOutputTokens": 5}},
                )
                if resp.status_code == 400:
                    return {"ok": True, "msg": "API 可达（key 有效）"}
                resp.raise_for_status()
                return {"ok": True, "msg": f"连接正常（{resp.status_code}）"}

            if body.api_type == "agnes-image":
                return {"ok": True, "msg": "Agnes 内置连接"}

            raise HTTPException(status_code=400, detail=f"未知 api_type: {body.api_type}")
        finally:
            await client.aclose()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "msg": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ── 数据导出 ───────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_data():
    """打包 SQLite 数据库导出为 ZIP"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if DB_PATH.exists():
            zf.write(str(DB_PATH), "galgame.db")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=galgame-export.zip"},
    )