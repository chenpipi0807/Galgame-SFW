"""
Galgame 卡 导出 / 导入 API
将剧情、角色、世界背景、聊天历史、记忆摘要等文本数据
嵌入 PNG 图片的 tEXt chunk 中，实现"一张图即一个故事存档"。

数据经过 AES-256-GCM 加密，只有持有相同密钥的 GalGame 才能读写。
"""
import base64
import json
import io
import struct
import zlib
import re
import os

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from db.database import get_db, UPLOADS_DIR
from core.paths import BASE_CARD_PATH

router = APIRouter(prefix="/api/galgame-card", tags=["galgame-card"])

# ── 加密 ────────────────────────────────────────────────────────
# ⚠️ 加密密钥种子（盐值 + 口令）：这两个值参与 AES 密钥派生，绝对不能修改。
#    一旦改动，所有历史导出的 GG 卡都将无法解密。其字面含 “Zeta” 仅为历史遗留的
#    密钥材料，不是展示名称，保持原值以兼容旧卡。
_APP_SALT = b"ZetaPlay_GalgameCard_2026_SALT"
_APP_PASSPHRASE = os.getenv("GALCARD_SECRET", "zeta-galcard-default-secret").encode()
_KEY_ITERATIONS = 100_000

# AES-256-GCM 加密标记：新卡写入 GALGAME1:，读取时同时兼容旧卡的 ZETA1:
_ENCRYPTION_MARKER = b"GALGAME1:"        # 新版写入标记
_LEGACY_ENCRYPTION_MARKERS = (b"ZETA1:",)  # 旧版读取兼容

def _derive_key() -> bytes:
    """从应用密钥派生 AES-256 密钥（32 字节）"""
    return PBKDF2(_APP_PASSPHRASE, _APP_SALT, dkLen=32, count=_KEY_ITERATIONS, hmac_hash_module=SHA256)


def _encrypt_data(plaintext: bytes) -> bytes:
    """AES-256-GCM 加密，返回 nonce(12) + tag(16) + ciphertext"""
    key = _derive_key()
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return nonce + tag + ciphertext


def _decrypt_data(encrypted: bytes) -> bytes:
    """AES-256-GCM 解密，输入 nonce(12) + tag(16) + ciphertext"""
    key = _derive_key()
    nonce = encrypted[:12]
    tag = encrypted[12:28]
    ciphertext = encrypted[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


# ── PNG chunk 读写 ──────────────────────────────────────────────
_CARD_KEY = b"galgame_card"            # 新版写入的 tEXt chunk 键
_LEGACY_CARD_KEYS = (b"zeta_card",)    # 旧版读取兼容
_CARD_VERSION = "1.0"


def _make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """构造一个 PNG chunk（length + type + data + crc32）"""
    chunk = struct.pack(">I", len(data)) + chunk_type + data
    chunk += struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return chunk


def _read_png_text_chunks(img_bytes: bytes) -> dict[bytes, str]:
    """读取 PNG 中所有 tEXt / zTXt / iTXt chunk，返回 {key: value}"""
    result: dict[bytes, str] = {}
    if img_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return result
    pos = 8
    while pos + 8 <= len(img_bytes):
        length = struct.unpack('>I', img_bytes[pos:pos + 4])[0]
        chunk_type = img_bytes[pos + 4:pos + 8]
        data = img_bytes[pos + 8:pos + 8 + length]
        pos += 8 + length + 4
        if chunk_type == b'tEXt':
            parts = data.split(b'\x00', 1)
            if len(parts) == 2:
                result[parts[0]] = parts[1].decode("latin-1")
        elif chunk_type == b'zTXt':
            parts = data.split(b'\x00', 2)
            if len(parts) >= 3:
                try:
                    decompressed = zlib.decompress(parts[2]).decode("latin-1")
                    result[parts[0]] = decompressed
                except Exception:
                    pass
        elif chunk_type == b'iTXt':
            # iTXt 格式比较复杂，尝试简化提取
            try:
                null1 = data.find(b'\x00')
                if null1 < 0:
                    continue
                key = data[:null1]
                rest = data[null1 + 1:]
                null2 = rest.find(b'\x00')  # compression flag
                if null2 < 0:
                    continue
                comp_flag = rest[null2 - 1:null2]
                rest2 = rest[null2 + 1:]
                null3 = rest2.find(b'\x00')  # compression method
                if null3 < 0:
                    continue
                rest3 = rest2[null3 + 1:]
                null4 = rest3.find(b'\x00')  # language tag
                if null4 < 0:
                    continue
                rest4 = rest3[null4 + 1:]
                null5 = rest4.find(b'\x00')  # translated keyword
                if null5 < 0:
                    continue
                payload = rest4[null5 + 1:]
                if comp_flag == b'\x01':
                    payload = zlib.decompress(payload)
                result[key] = payload.decode("utf-8")
            except Exception:
                pass
    return result


def _embed_json_in_png(img_bytes: bytes, data: dict) -> bytes:
    """加密 JSON 数据后 base64 编码嵌入 PNG 的 tEXt chunk，返回新的 PNG bytes"""
    json_str = json.dumps(data, ensure_ascii=False)
    # AES-256-GCM 加密 → base64 → 加标记前缀
    encrypted = _encrypt_data(json_str.encode("utf-8"))
    b64_data = _ENCRYPTION_MARKER + base64.b64encode(encrypted)
    # 先移除已有的 zeta_card chunk
    img_bytes = _strip_card_chunk(img_bytes)

    # 找到 IEND chunk 的位置，在其之前插入我们的 chunk
    iend_pos = img_bytes.rfind(b'IEND')
    if iend_pos < 0:
        raise ValueError("不是有效的 PNG 文件")

    # iend_pos 指向 'I' (chunk type 的第一个字节), 往前 4 字节是 length
    iend_start = iend_pos - 4

    card_chunk = _make_png_chunk(b'tEXt', _CARD_KEY + b'\x00' + b64_data)

    return img_bytes[:iend_start] + card_chunk + img_bytes[iend_start:]


def _strip_card_chunk(img_bytes: bytes) -> bytes:
    """从 PNG 中移除卡片 chunk（新旧键都清除，避免重复导出残留旧块）"""
    if img_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return img_bytes
    card_keys = (_CARD_KEY, *_LEGACY_CARD_KEYS)
    result = bytearray(img_bytes[:8])
    pos = 8
    while pos + 8 <= len(img_bytes):
        length = struct.unpack('>I', img_bytes[pos:pos + 4])[0]
        chunk_type = img_bytes[pos + 4:pos + 8]
        data = img_bytes[pos + 8:pos + 8 + length]
        chunk_end = pos + 8 + length + 4
        is_card = chunk_type == b'tEXt' and any(data.startswith(k + b'\x00') for k in card_keys)
        if not is_card:
            result.extend(img_bytes[pos:chunk_end])
        pos = chunk_end
    return bytes(result)


# ── 图片读取 / 编码 ─────────────────────────────────────────────

async def _load_image_bytes(url: str) -> bytes | None:
    """把图片 URL（data: / /uploads/… / http(s)://）读成原始 bytes。"""
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith("data:"):
        try:
            _, b64_part = url.split(",", 1)
            return base64.b64decode(b64_part)
        except Exception:
            return None
    if url.startswith("/uploads/"):
        filepath = UPLOADS_DIR / url[len("/uploads/"):]
        return filepath.read_bytes() if filepath.exists() else None
    if url.startswith("http"):
        import httpx
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(url)
            return resp.content if resp.status_code == 200 else None
    return None


async def _image_to_data_uri(url: str, max_size: int = 512) -> str | None:
    """读取图片并压缩为不超过 max_size 的 JPEG data URI（用于把角色图嵌入卡，控制体积）。"""
    raw = await _load_image_bytes(url)
    if not raw:
        return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB")
        im.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _data_uri_to_upload(data_uri: str) -> str | None:
    """把 data: URI 落盘到 uploads，返回 /uploads/… 路径（导入时还原角色图）。"""
    import uuid as _uuid
    if not data_uri or not data_uri.startswith("data:"):
        return None
    try:
        header, b64_part = data_uri.split(",", 1)
        raw = base64.b64decode(b64_part)
        ext = "jpg" if "jpeg" in header or "jpg" in header else "png"
        fname = f"galcard_char_{_uuid.uuid4().hex[:12]}.{ext}"
        (UPLOADS_DIR / fname).write_bytes(raw)
        return f"/uploads/{fname}"
    except Exception:
        return None


# ── 世界书分类 ──────────────────────────────────────────────────
_DYNAMIC_LOREBOOK_TITLE = "📜 剧情演变"   # 规则演进（动态生成）

def _lore_category(title: str) -> str:
    """按书名标题把世界书归类：original=原设定 / rules=规则演进 / mounted=挂载世界书。"""
    t = (title or "").strip()
    if t == _DYNAMIC_LOREBOOK_TITLE or t.startswith("📜"):
        return "rules"
    if t.startswith("📖") or t.startswith("🎯"):
        return "original"
    return "mounted"


# ── 导出 ────────────────────────────────────────────────────────

class ExportBody(BaseModel):
    session_id: int
    # 卡面来源："base" 用内置 BASE.png；否则为图片 URL（/uploads/… 或 data:）
    card_face: str = "base"
    # 角色卡部分
    include_char_text: bool = True        # 角色卡设计（文本字段）
    include_char_images: bool = True      # 角色卡图片（头像/立绘，压缩内嵌）
    include_char_evolution: bool = True   # 角色性格演变层
    # 聊天轮次上限（按对话回合 turn 计；None=全部）
    round_limit: int | None = None
    # 记忆
    include_memory: bool = True
    # 世界书分类
    include_lore_original: bool = True    # 原设定（📖/🎯）
    include_lore_rules: bool = True       # 规则演进（📜剧情演变）
    include_lore_mounted: bool = True     # 挂载世界书（其他）


@router.post("/export")
async def export_card(body: ExportBody):
    """把会话的全部文本数据嵌入快照图，返回 PNG 下载"""
    db = await get_db()

    # 1. 会话
    async with db.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session = dict(session)

    # 2. 剧情
    async with db.execute("SELECT * FROM plots WHERE id=?", (session["plot_id"],)) as cur:
        plot = await cur.fetchone()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情不存在")
    plot = dict(plot)

    # 3. 角色
    char_id_to_name: dict[int, str] = {}
    async with db.execute(
        "SELECT * FROM characters WHERE plot_id=? ORDER BY id", (session["plot_id"],)
    ) as cur:
        char_rows = [dict(r) for r in await cur.fetchall()]

    characters = []
    for c in char_rows:
        char_id_to_name[c["id"]] = c.get("name", "")
        item: dict = {
            "name": c.get("name", ""),
            "is_user": c.get("is_user", 0),
        }
        if body.include_char_text:
            item.update({
                "description": c.get("description", ""),
                "personality": c.get("personality", ""),
                "first_mes": c.get("first_mes", ""),
                "image_prompt": c.get("image_prompt", ""),
            })
        if body.include_char_evolution:
            item["personality_evolved"] = c.get("personality_evolved", "")
        if body.include_char_images:
            # 头像 + 立绘压缩内嵌（缺一不可，能拿到哪个用哪个）
            avatar = await _image_to_data_uri(c.get("avatar_url", ""), 512)
            image = await _image_to_data_uri(c.get("image_url", ""), 768)
            if avatar:
                item["avatar_b64"] = avatar
            if image:
                item["image_b64"] = image
        characters.append(item)

    # 4. 聊天历史 —— 按对话回合 turn 截断（round_limit=None 则全部）
    #    turn 计数与前端 displayItems 一致：每条 user 消息 +1，user/assistant 共享该 turn
    async with db.execute(
        "SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id",
        (body.session_id,),
    ) as cur:
        rows = await cur.fetchall()

    messages = []
    turn = 0
    for r in rows:
        role = r["role"]
        if role == "user":
            turn += 1
        # 跳过图片类消息（snapshot / chat_image），其 content 是本地 URL 无法跨机使用
        if role in ("snapshot", "chat_image"):
            continue
        # 超出选定回合上限的对话不导出
        if body.round_limit is not None and turn > body.round_limit:
            continue
        meta_str = r["metadata"]
        # 将 player_character_id（本机 DB 行 ID）转为角色名，供跨设备导入时重建映射
        if meta_str and meta_str != "{}":
            try:
                meta = json.loads(meta_str)
                old_pc_id = meta.get("player_character_id")
                if old_pc_id is not None and isinstance(old_pc_id, int):
                    char_name = char_id_to_name.get(old_pc_id)
                    if char_name:
                        meta["_player_char_name"] = char_name
                        meta_str = json.dumps(meta, ensure_ascii=False)
            except Exception:
                pass
        messages.append({
            "role": role,
            "content": r["content"],
            "metadata": meta_str,
        })

    # 5. 世界书条目（按用户选择的分类过滤）
    wanted = set()
    if body.include_lore_original:
        wanted.add("original")
    if body.include_lore_rules:
        wanted.add("rules")
    if body.include_lore_mounted:
        wanted.add("mounted")
    async with db.execute(
        """SELECT lb.title AS lb_title, le.keywords, le.content
           FROM lorebook_entries le
           JOIN lorebooks lb ON lb.id = le.lorebook_id
           JOIN plot_lorebooks pl ON pl.lorebook_id = lb.id
           WHERE pl.plot_id=?""",
        (session["plot_id"],),
    ) as cur:
        lorebook = []
        for r in await cur.fetchall():
            row = dict(r)
            if _lore_category(row.pop("lb_title", "")) in wanted:
                lorebook.append(row)

    # 组装卡片数据
    card_data = {
        "v": _CARD_VERSION,
        "plot": {
            "title": plot.get("title", ""),
            "concept": plot.get("concept", ""),
            "vibe": plot.get("vibe", "[]"),
            "opening": plot.get("opening", ""),
            "backstory": plot.get("backstory", ""),
            "style_settings": plot.get("style_settings", "{}"),
        },
        "characters": characters,
        "messages": messages,
        "memory_summary": session.get("memory_summary", "{}") if body.include_memory else "{}",
        "lorebook": lorebook,
        "session_title": session.get("title", ""),
    }

    # 读取卡面图：card_face="base" 用内置 BASE.png，否则按 URL 读取
    if body.card_face.strip().lower() == "base":
        img_bytes = BASE_CARD_PATH.read_bytes() if BASE_CARD_PATH.exists() else None
    else:
        img_bytes = await _load_image_bytes(body.card_face)

    if not img_bytes:
        raise HTTPException(status_code=400, detail="无法读取卡面图片")

    # 卡面须为 PNG（tEXt chunk 依赖 PNG 结构）；非 PNG（如 JPEG 快照）先转码
    if img_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        except Exception:
            raise HTTPException(status_code=400, detail="卡面图片格式不支持")

    # 嵌入数据
    try:
        out_bytes = _embed_json_in_png(img_bytes, card_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入卡片数据失败: {e}")

    # 返回下载
    from urllib.parse import quote
    filename = f"{plot.get('title', 'galgame')}_galgamecard.png"
    encoded = quote(filename)
    return Response(
        content=out_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/base-face")
async def base_face():
    """返回内置默认卡面 BASE.png，供导出弹窗预览/兜底选用。"""
    if not BASE_CARD_PATH.exists():
        raise HTTPException(status_code=404, detail="默认卡面缺失")
    return Response(content=BASE_CARD_PATH.read_bytes(), media_type="image/png")


# ── 导入 ────────────────────────────────────────────────────────

class ImportBody(BaseModel):
    data: str  # base64 data URI: "data:image/png;base64,..."


@router.post("/import")
async def import_card(body: ImportBody):
    """从 Galgame 卡 PNG 中读取数据，创建剧情+角色+会话+消息，返回新会话 ID"""
    # 解码图片
    if "," in body.data:
        _, b64_part = body.data.split(",", 1)
    else:
        b64_part = body.data
    img_bytes = base64.b64decode(b64_part)

    # 读取卡片 chunk（新键 galgame_card，兼容旧键 zeta_card）
    text_chunks = _read_png_text_chunks(img_bytes)
    card_raw = text_chunks.get(_CARD_KEY)
    if not card_raw:
        for _k in _LEGACY_CARD_KEYS:
            card_raw = text_chunks.get(_k)
            if card_raw:
                break
    if not card_raw:
        raise HTTPException(status_code=400, detail="该图片不是有效的 Galgame 卡（未找到卡片数据）")

    try:
        raw_bytes = card_raw.encode("latin-1") if isinstance(card_raw, str) else card_raw
        # 加密格式：新版 GALGAME1: 与旧版 ZETA1: 都接受
        _marker = next(
            (m for m in (_ENCRYPTION_MARKER, *_LEGACY_ENCRYPTION_MARKERS) if raw_bytes.startswith(m)),
            None,
        )
        if _marker:
            # ✅ AES-256-GCM 加密格式
            encrypted_b64 = raw_bytes[len(_marker):]
            encrypted = base64.b64decode(encrypted_b64)
            decrypted = _decrypt_data(encrypted)
            card = json.loads(decrypted.decode("utf-8"))
        else:
            # 回退：base64 编码格式（旧版，未加密）
            card = json.loads(base64.b64decode(raw_bytes).decode("utf-8"))
    except Exception:
        # 最终回退：直接 JSON（最早版本）
        try:
            card = json.loads(card_raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="卡片数据损坏或密钥不匹配（无法解密）")

    if card.get("v") != _CARD_VERSION:
        raise HTTPException(status_code=400, detail=f"不支持的卡片版本: {card.get('v')}")

    db = await get_db()

    # 1. 创建剧情
    p = card.get("plot", {})
    async with db.execute(
        """INSERT INTO plots (title, concept, vibe, opening, backstory, style_settings, status)
           VALUES (?,?,?,?,?,?,?) RETURNING id""",
        (
            p.get("title", "导入的故事"),
            p.get("concept", ""),
            p.get("vibe", "[]"),
            p.get("opening", ""),
            p.get("backstory", ""),
            p.get("style_settings", "{}"),
            "published",
        ),
    ) as cur:
        row = await cur.fetchone()
    plot_id = row[0]

    # 2. 创建角色
    char_name_to_id: dict[str, int] = {}
    for c in card.get("characters", []):
        # 还原内嵌的角色图（导出时压缩为 data URI）→ 落盘为 /uploads/… 路径
        avatar_url = _data_uri_to_upload(c.get("avatar_b64", "")) or ""
        image_url = _data_uri_to_upload(c.get("image_b64", "")) or avatar_url
        async with db.execute(
            """INSERT INTO characters (plot_id, name, description, personality, personality_evolved, first_mes, is_user, image_prompt, avatar_url, image_url)
               VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (
                plot_id,
                c.get("name", ""),
                c.get("description", ""),
                c.get("personality", ""),
                c.get("personality_evolved", ""),  # 演变层随卡迁移
                c.get("first_mes", ""),
                c.get("is_user", 0),
                c.get("image_prompt", ""),
                avatar_url,
                image_url,
            ),
        ) as cur:
            row = await cur.fetchone()
        char_name_to_id[c.get("name", "")] = row[0]

    # 3. 创建会话
    async with db.execute(
        """INSERT INTO sessions (plot_id, title, current_scene, memory_summary)
           VALUES (?,?,?,?) RETURNING id""",
        (
            plot_id,
            card.get("session_title", "导入的会话"),
            "",
            card.get("memory_summary", "{}"),
        ),
    ) as cur:
        row = await cur.fetchone()
    session_id = row[0]

    # 4. 导入消息历史
    for m in card.get("messages", []):
        role = m.get("role", "assistant")
        content = m.get("content", "")
        metadata = m.get("metadata", "{}")

        # 解析 metadata 中的 player_character_id，映射到新角色 ID
        if metadata and metadata != "{}":
            try:
                meta = json.loads(metadata)
                char_name = meta.pop("_player_char_name", None)
                if char_name:
                    new_id = char_name_to_id.get(char_name)
                    if new_id:
                        meta["player_character_id"] = new_id
                    metadata = json.dumps(meta, ensure_ascii=False)
            except Exception:
                pass

        await db.execute(
            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
            (session_id, content, role, metadata),
        )

    # 5. 导入世界书（Lorebook）
    lore_entries = card.get("lorebook") or []
    if lore_entries:
        async with db.execute(
            "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
            ("📖 导入的世界书", f"从 GG 卡恢复，共 {len(lore_entries)} 条规则"),
        ) as cur_lb:
            lb_row = await cur_lb.fetchone()
        lb_id = lb_row[0]
        for i, entry in enumerate(lore_entries):
            kw = entry.get("keywords") or []
            if isinstance(kw, str):
                try:
                    kw = json.loads(kw)
                except Exception:
                    kw = [k.strip() for k in kw.split(",") if k.strip()]
            content = entry.get("content", "")
            await db.execute(
                "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
                (lb_id, json.dumps(kw, ensure_ascii=False) if isinstance(kw, list) else str(kw), content, i),
            )
        await db.execute(
            "INSERT INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
            (plot_id, lb_id),
        )
        await db.commit()

    # 6. 把卡片图保存为会话背景图
    import uuid as _uuid
    bg_filename = f"galcard_{_uuid.uuid4().hex[:12]}.png"
    bg_path = UPLOADS_DIR / bg_filename
    bg_path.write_bytes(img_bytes)
    bg_url = f"/uploads/{bg_filename}"

    await db.execute(
        "UPDATE sessions SET bg_image_url=? WHERE id=?",
        (bg_url, session_id),
    )

    await db.commit()

    return {
        "plot_id": plot_id,
        "session_id": session_id,
        "bg_image_url": bg_url,
    }
