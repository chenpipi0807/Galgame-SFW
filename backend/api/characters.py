import base64 as _b64
import json as _json
import struct
import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.database import get_db, UPLOADS_DIR
from tasks.worker import enqueue
from core.llm import chat
from core.prompt_loader import load
from core.memory import get_context_messages

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterCreate(BaseModel):
    plot_id: int
    name: str = ''
    description: str = ''
    personality: str = ''
    image_prompt: str = ''
    image_style: str = ''
    reference_image: str = ''
    avatar_url: str = ''
    image_url: str = ''
    first_mes: str = ''
    aliases: str = '[]'


class CharacterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    personality: str | None = None
    image_prompt: str | None = None
    image_style: str | None = None
    reference_image: str | None = None
    avatar_url: str | None = None
    image_url: str | None = None
    first_mes: str | None = None
    aliases: str | None = None


@router.post("")
async def create_character(body: CharacterCreate):
    db = await get_db()
    async with db.execute(
        """INSERT INTO characters (plot_id, name, description, personality, image_prompt, image_style, reference_image, avatar_url, image_url, first_mes, aliases)
           VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
        (body.plot_id, body.name, body.description, body.personality, body.image_prompt, body.image_style,
         body.reference_image, body.avatar_url, body.image_url, body.first_mes, body.aliases),
    ) as cur:
        row = await cur.fetchone()
    await db.commit()
    return {"id": row[0]}


@router.get("")
async def list_characters(plot_id: int | None = None):
    db = await get_db()
    if plot_id:
        async with db.execute(
            "SELECT * FROM characters WHERE plot_id=? ORDER BY id", (plot_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    async with db.execute("SELECT * FROM characters ORDER BY id") as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.put("/{char_id}")
async def update_character(char_id: int, body: CharacterUpdate):
    db = await get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"ok": True}
    sets = ", ".join(f"{k}=?" for k in updates)
    await db.execute(f"UPDATE characters SET {sets} WHERE id=?", (*updates.values(), char_id))
    await db.commit()
    return {"ok": True}


@router.delete("/{char_id}")
async def delete_character(char_id: int):
    db = await get_db()
    await db.execute("DELETE FROM characters WHERE id=?", (char_id,))
    await db.commit()
    return {"ok": True}


class TavernCardBody(BaseModel):
    data: str  # base64 data URI: "data:image/png;base64,..."


def _parse_chara_png(img_bytes: bytes) -> dict | None:
    """从 PNG tEXt chunk 提取 SillyTavern chara 数据，返回解码后的 dict"""
    if img_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    pos = 8
    while pos + 8 <= len(img_bytes):
        length = struct.unpack('>I', img_bytes[pos:pos + 4])[0]
        chunk_type = img_bytes[pos + 4:pos + 8]
        data = img_bytes[pos + 8:pos + 8 + length]
        pos += 8 + length + 4
        if chunk_type == b'tEXt':
            parts = data.split(b'\x00', 1)
            if len(parts) == 2 and parts[0] == b'chara':
                try:
                    decoded = _b64.b64decode(parts[1].decode('latin-1')).decode('utf-8')
                    return _json.loads(decoded)
                except Exception:
                    return None
    return None


# ═══════════════════════════════════════════════
# 酒馆角色卡智能解析辅助函数
# ═══════════════════════════════════════════════

def _serialize_json_char_field(obj, depth: int = 0) -> str:
    """将 JSON 角色描述子对象递归序列化为可读中文文本"""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        parts = []
        for item in obj:
            rendered = _serialize_json_char_field(item, depth)
            if rendered.strip():
                parts.append(rendered)
        return "\n".join(parts)
    if not isinstance(obj, dict):
        return str(obj)

    lines = []
    prefix = "  " * depth
    for k, v in obj.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}【{k}】")
            inner = _serialize_json_char_field(v, depth + 1)
            if inner.strip():
                lines.append(inner)
        elif isinstance(v, list):
            if all(isinstance(x, str) for x in v):
                items = "；".join(str(x) for x in v)
                lines.append(f"{prefix}{k}：{items}")
            else:
                lines.append(f"{prefix}【{k}】")
                for item in v:
                    rendered = _serialize_json_char_field(item, depth + 1)
                    if rendered.strip():
                        lines.append(rendered)
        else:
            val = str(v).strip()
            if val:
                lines.append(f"{prefix}{k}：{val}")
    return "\n".join(lines)


def _parse_description_smart(raw_desc: str) -> dict:
    """
    智能解析角色卡 description 字段，三分支策略：
      A. JSON 结构化 → 提取 appearance / personality / extra
      B. XML 标签分区 → 按 <外表> <性格> 等标签切分
      C. 纯文本 → 原样返回

    返回 {"appearance": str, "personality": str, "extra": str, "format": str}
    """
    raw_desc = raw_desc.strip()
    if not raw_desc:
        return {"appearance": "", "personality": "", "extra": "", "format": "empty"}

    # ── 分支 A：JSON 结构化 ──
    if raw_desc.startswith("{"):
        try:
            obj = _json.loads(raw_desc)
            if isinstance(obj, dict):
                ap_parts, per_parts, ext_parts = [], [], []
                for k, v in obj.items():
                    kl = k.lower()
                    if any(w in kl for w in ("appearance", "外表", "外观", "look", "physical",
                                              "body", "face", "cloth", "hair", "eye", "feature")):
                        ap_parts.append(_serialize_json_char_field(v))
                    elif any(w in kl for w in ("personality", "性格", "persona", "trait",
                                                "strength", "weakness", "value", "hobby",
                                                "like", "dislike")):
                        per_parts.append(_serialize_json_char_field(v))
                    elif kl in ("background_story", "backstory", "背景故事", "background", "history"):
                        ext_parts.append(_serialize_json_char_field(v))
                    elif kl == "relationships":
                        ext_parts.append(f"【人际关系】\n{_serialize_json_char_field(v)}")
                    elif kl in ("name", "age", "race", "gender", "occupation",
                                "residence", "example_dialogue", "race_details"):
                        continue
                    else:
                        ext_parts.append(_serialize_json_char_field(v))

                appearance = "\n\n".join(p for p in ap_parts if p).strip()
                personality = "\n\n".join(p for p in per_parts if p).strip()
                extra = "\n\n".join(p for p in ext_parts if p).strip()

                if appearance or personality:
                    return {"appearance": appearance, "personality": personality,
                            "extra": extra, "format": "json"}
        except (_json.JSONDecodeError, TypeError):
            pass

    # ── 分支 B：XML / Markdown 标签分区 ──
    sections = {"appearance": [], "personality": [], "extra": []}
    tag_map = {
        "外表": "appearance", "外观": "appearance", "appearance": "appearance",
        "性格": "personality", "personality": "personality",
        "场景": "extra", "设定": "extra", "背景": "extra",
        "scenario": "extra", "background": "extra",
        "char": "extra", "角色": "extra", "user": "extra",
    }
    for m in re.finditer(r'<(\w+)[^>]*>\s*(.*?)\s*(?:</\1>|(?=<)|$)', raw_desc, re.I | re.S):
        raw_tag = m.group(1)
        tag = raw_tag.lower()
        content = m.group(2).strip()
        bucket = tag_map.get(tag) or tag_map.get(raw_tag)
        if bucket and content:
            sections[bucket].append(content)

    if any(v for v in sections.values()):
        appearance = "\n\n".join(sections["appearance"]).strip()
        personality = "\n\n".join(sections["personality"]).strip()
        extra = "\n\n".join(sections["extra"]).strip()
        remaining = re.sub(r'<[^>]+>', '', raw_desc).strip()
        if not appearance and remaining:
            appearance = remaining
        return {"appearance": appearance, "personality": personality,
                "extra": extra, "format": "xml"}

    # ── 分支 C：纯文本 ──
    return {"appearance": raw_desc, "personality": "", "extra": "", "format": "plain"}




# ═══════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════

@router.post("/parse-tavern-card")
async def parse_tavern_card(body: TavernCardBody):
    """
    解析 SillyTavern 角色卡 PNG（CharaCard V2/V3）。
    - 返回 raw_json：完整 chara JSON（占位符已替换），供 import-tavern LLM 使用
    - 同时返回规则解析的 description/personality 作兜底字段
    - 不再调用 LLM（LLM 调用移至 /plots/wizard/import-tavern）
    """
    parts = body.data.split(',', 1)
    if len(parts) != 2 or 'base64' not in parts[0]:
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")

    try:
        img_bytes = _b64.b64decode(parts[1])
    except Exception:
        raise HTTPException(status_code=400, detail="base64 解码失败")

    chara = _parse_chara_png(img_bytes)
    if not chara:
        return {"is_tavern_card": False}

    d = chara.get('data') or chara
    name = (d.get('name') or chara.get('name') or '').strip() or '未命名角色'

    def _sub(text: str) -> str:
        for pat in ('{{char}}', '{{Char}}', '{{CHAR}}',
                    '{char}', '{Char}', '{CHAR}',
                    '<char>', '<Char>', '<CHAR>',
                    '<bot>', '<Bot>', '<BOT>',
                    '<assistant>', '<Assistant>'):
            text = text.replace(pat, name)
        for pat in ('{{user}}', '{{User}}', '{{USER}}',
                    '{user}', '{User}', '{USER}',
                    '<user>', '<User>', '<USER>',
                    '<human>', '<Human>', '<HUMAN>'):
            text = text.replace(pat, '你')
        return text

    def _sub_deep(obj):
        if isinstance(obj, str):   return _sub(obj)
        if isinstance(obj, list):  return [_sub_deep(x) for x in obj]
        if isinstance(obj, dict):  return {k: _sub_deep(v) for k, v in obj.items()}
        return obj

    # 深度替换占位符后序列化为 raw_json，供 LLM 处理
    chara_clean = _sub_deep(d)
    raw_json = _json.dumps(chara_clean, ensure_ascii=False)

    # ── 规则解析兜底字段（LLM 失败时使用） ──
    raw_description = (chara_clean.get('description') or '').strip()
    raw_personality = (chara_clean.get('personality') or '').strip()
    first_mes = (chara_clean.get('first_mes') or '').strip()

    # depth_prompt 兜底
    extensions = chara_clean.get('extensions') or {}
    depth_prompt_raw = extensions.get('depth_prompt') or {}
    if isinstance(depth_prompt_raw, dict):
        depth_prompt_text = depth_prompt_raw.get('prompt', '').strip()
    elif isinstance(depth_prompt_raw, str):
        depth_prompt_text = depth_prompt_raw.strip()
    else:
        depth_prompt_text = ''
    if not raw_description and depth_prompt_text:
        raw_description = depth_prompt_text

    # alternate_greetings
    alternate_greetings = [g for g in (chara_clean.get('alternate_greetings') or [])
                           if isinstance(g, str) and g.strip()]
    if not first_mes and alternate_greetings:
        first_mes = alternate_greetings[0]

    # 规则解析 description → appearance/personality（兜底用）
    parsed = _parse_description_smart(raw_description)
    fallback_description = parsed["appearance"] or raw_description
    fallback_personality = parsed["personality"] or raw_personality
    scenario = (chara_clean.get('scenario') or '').strip()
    if scenario and parsed["format"] in ("plain", "empty", "xml"):
        fallback_description = (fallback_description + "\n\n【场景背景】\n" + scenario).strip()
    if parsed["format"] == "plain" and raw_personality:
        fallback_personality = raw_personality

    # 保存图片
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    (UPLOADS_DIR / filename).write_bytes(img_bytes)
    image_url = f"/uploads/{filename}"

    return {
        "is_tavern_card": True,
        "name": name,
        "first_mes": first_mes,
        "alternate_greetings": alternate_greetings,
        "image_url": image_url,
        "raw_json": raw_json,
        # 兜底字段（LLM 失败时前端/import-tavern 使用）
        "description": fallback_description,
        "personality": fallback_personality,
    }


class CharacterAutofillBody(BaseModel):
    plot_id: int
    name: str = ""
    session_id: int | None = None  # 可选：用于获取当前记忆上下文


@router.post("/autofill")
async def autofill_character(body: CharacterAutofillBody):
    """AI 一键补全角色信息：根据故事背景、记忆上下文和角色名，生成外貌/性格/生图提示词/别名"""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="角色名不能为空")

    db = await get_db()

    # ── 1. 加载故事背景 ──
    async with db.execute("SELECT * FROM plots WHERE id=?", (body.plot_id,)) as cur:
        plot = await cur.fetchone()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情不存在")
    plot = dict(plot)

    # ── 2. 加载已有角色 ──
    async with db.execute(
        "SELECT name, description, personality FROM characters WHERE plot_id=? ORDER BY id",
        (body.plot_id,),
    ) as cur:
        existing_chars = [dict(r) for r in await cur.fetchall()]

    # ── 3. 加载当前记忆上下文 ──
    memory_text = ""
    if body.session_id:
        try:
            summary, _ = await get_context_messages(body.session_id)
            if summary:
                memory_text = f"\n【当前剧情状态】\n{summary}"
        except Exception:
            pass

    # ── 4. 叙事模式（全年龄向：固定 classic）──
    mode = "classic"

    # ── 5. 构建 prompt ──
    system = await load("character_autofill", mode)
    if not system:
        system = await load("character_autofill", "classic")

    # 构建角色列表
    chars_text = ""
    if existing_chars:
        chars_text = "\n".join(
            f"- {c['name']}：{c.get('description','')[:60]}（{c.get('personality','')[:40]}）"
            for c in existing_chars[:15]
        )

    user_prompt = f"""请为以下新角色补全设定：

【故事标题】{plot.get('title', '')}
【故事概念】{plot.get('concept', '')}
【开场白】{plot.get('opening', '')[:300]}
【背景设定】{plot.get('backstory', '')[:300]}

【已有角色】
{chars_text or '暂无'}

{memory_text}

【新角色名】{body.name.strip()}

请输出 JSON。"""

    raw = await chat([{"role": "user", "content": user_prompt}], system=system, max_tokens=8192)

    # ── 6. 解析 JSON ──
    return _parse_autofill_json(raw)


class RegenerateAvatarBody(BaseModel):
    image_style: str = ""  # 可覆盖原有风格


def _parse_autofill_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON，容错处理"""
    raw = raw.strip()
    # 去除 markdown 代码块
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    try:
        return _json.loads(raw)
    except Exception:
        # 尝试提取第一个 { } 对象
        m = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if m:
            return _json.loads(m.group())
    return {"description": "", "personality": "", "image_prompt": "", "aliases": []}


@router.post("/{char_id}/regenerate-avatar")
async def regenerate_avatar(char_id: int, body: RegenerateAvatarBody = RegenerateAvatarBody()):
    db = await get_db()
    async with db.execute(
        "SELECT image_prompt, image_style, description, personality, reference_image FROM characters WHERE id=?",
        (char_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 优先用已有 image_prompt，否则用 description（worker 会自动翻译英文）
    prompt = row["image_prompt"] or row["description"] or row["personality"] or ""
    if not prompt:
        raise HTTPException(status_code=400, detail="角色没有任何可用于生图的描述")

    style = body.image_style or row["image_style"] or ""
    ref_imgs = [row["reference_image"]] if row["reference_image"] else []
    task_id = await enqueue(
        "character_img",
        {
            "character_id": char_id,
            "image_prompt": prompt,
            "image_style": style,
            "reference_images": ref_imgs,
        },
    )
    return {"task_id": task_id}