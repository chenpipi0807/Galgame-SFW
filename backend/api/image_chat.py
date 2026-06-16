"""
图像生成辅助接口：
  POST /api/image/from-chat    — 基于当前对话最近 1 轮生成配图（附角色参考图）
  POST /api/image/opening-bg   — 生成会话开场背景图
  POST /api/uploads/image      — 上传本地图片，保存到 data/uploads/ 并返回 URL
"""
import base64
import json as _json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.llm import chat
from core.prompt_loader import load
from db.database import get_db, UPLOADS_DIR
from tasks.worker import enqueue

logger = logging.getLogger("galgame.image_chat")
router = APIRouter(tags=["image_chat"])


# 容错字段提取——与前端 NarrativeBlock.vue 的 repairLine/extractFields 保持同一套规则。
# 仅在 _json.loads 失败时触发，用于救出对白内未转义引号撑破的 character 行。
# ⚠️ 改动此处时请同步前端 NarrativeBlock.vue（两份实现必须一致，否则前端渲染与
#    后端场景角色检测会再次分叉）。
_KEY_RE = re.compile(r'"(type|name|action|dialogue|content|_player)"\s*:')


def _extract_name_from_broken(obj_str: str) -> str | None:
    """从一段损坏的类 JSON 中提取 type=='character' 的 name（找不到返回 None）"""
    keys = list(_KEY_RE.finditer(obj_str))
    if not keys:
        return None
    fields: dict[str, str] = {}
    for i, m in enumerate(keys):
        key = m.group(1)
        val_start = m.end()
        val_end = keys[i + 1].start() if i + 1 < len(keys) else len(obj_str)
        raw = obj_str[val_start:val_end].strip()
        if key == '_player':
            continue
        fq = raw.find('"')
        if fq == -1:
            continue
        rest = raw[fq + 1:]
        cut = -1
        for p in range(len(rest) - 1, -1, -1):
            if rest[p] == '"':
                after = rest[p + 1:].lstrip()
                if after == '' or after[0] in ',}':
                    cut = p
                    break
        val = rest[:cut] if cut != -1 else re.sub(r'[”」』"]+$', '', re.sub(r'[}\],\s]+$', '', rest))
        fields[key] = val.replace('\\"', '"')
    if fields.get('type') == 'character' and fields.get('name'):
        return fields['name']
    return None


def _chars_in_scene(content: str) -> set[str]:
    """从 NDJSON 叙事内容中提取出镜角色名（character 行的 name 字段）"""
    names = set()
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            obj = _json.loads(line)
            if obj.get('type') == 'character' and obj.get('name'):
                names.add(obj['name'])
            continue
        except Exception:
            pass
        # 解析失败且形似 character 行 → 容错提取（与前端修复逻辑对齐）
        if line.startswith('{') and '"type"' in line:
            # 先尝试粘连切分（}{ 拼接），逐片提取
            pieces = re.split(r'(?<=\})\s*,?\s*(?=\{)', line) if re.search(r'\}\s*,?\s*\{', line) else [line]
            for piece in pieces:
                nm = _extract_name_from_broken(piece)
                if nm:
                    names.add(nm)
    return names


# ── 上传图片 ──────────────────────────────────────────────────────────────────

class UploadBody(BaseModel):
    data: str  # base64 data URI: "data:image/png;base64,..."


@router.post("/api/uploads/image")
async def upload_image(body: UploadBody):
    """保存 base64 图片到 data/uploads/，返回可访问的 URL"""
    m = body.data.split(",", 1)
    if len(m) != 2 or "base64" not in m[0]:
        raise HTTPException(status_code=400, detail="无效的 base64 数据")
    header, b64data = m
    ext = "jpg"
    if "png" in header:
        ext = "png"
    elif "webp" in header:
        ext = "webp"
    filename = f"{uuid.uuid4().hex}.{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / filename).write_bytes(base64.b64decode(b64data))
    return {"url": f"/uploads/{filename}"}


# ── 对话配图 ──────────────────────────────────────────────────────────────────

class ChatImageBody(BaseModel):
    session_id: int
    message_id: int  # 触发生图的 assistant 消息 id
    player_character_id: int | None = None  # 当前轮次扮演角色（旧卡兜底）


@router.post("/api/image/from-chat")
async def image_from_chat(body: ChatImageBody):
    """
    取触发消息及其前一条 user 消息（最近 1 轮），
    加上角色参考图 + 用户头像，生成 1 张 POV 配图。
    """
    db = await get_db()

    # 获取当前 assistant 消息
    async with db.execute(
        "SELECT * FROM messages WHERE id=?", (body.message_id,)
    ) as cur:
        msg = await cur.fetchone()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    # 获取前一条 user 消息（1 轮 = user + assistant），同时取 metadata 获取当轮扮演角色
    async with db.execute(
        """SELECT content, metadata FROM messages
           WHERE session_id=? AND id < ? AND role='user'
           ORDER BY id DESC LIMIT 1""",
        (body.session_id, body.message_id),
    ) as cur:
        user_msg = await cur.fetchone()

    # 获取 session → plot_id
    async with db.execute(
        "SELECT plot_id FROM sessions WHERE id=?", (body.session_id,)
    ) as cur:
        session_row = await cur.fetchone()

    # 获取所有角色（含 is_user=1，场景检测需要全量匹配）
    all_chars = []
    player_char_ref = ""
    player_char_name = ""
    if session_row:
        async with db.execute(
            "SELECT name, description, image_prompt, avatar_url, reference_image, is_user FROM characters WHERE plot_id=? ORDER BY id",
            (session_row["plot_id"],),
        ) as cur:
            all_chars = await cur.fetchall()
        # is_user=1 为创建向导时标记的"默认玩家角色"，作为 fallback
        _default_player = next((c for c in all_chars if c["is_user"]), None)
        if _default_player:
            player_char_ref = _default_player["avatar_url"] or _default_player["reference_image"] or ""
            player_char_name = _default_player["name"] or ""

    # chars 仍保留「排除 is_user=1」的 NPC 列表，用于 fallback 和旧格式兜底
    chars = [c for c in all_chars if not c["is_user"]]

    # 检测当前出镜角色 —— 在全部角色里匹配，避免 is_user=1 角色作 NPC 时漏掉
    scene_char_names = _chars_in_scene(msg['content'])
    if scene_char_names:
        active_chars = [c for c in all_chars if c['name'] in scene_char_names]
        if not active_chars:
            active_chars = list(chars)  # fallback：识别失败时用全部 NPC
    else:
        # 旧格式消息（非 NDJSON），降级为全部 NPC
        active_chars = list(chars)

    # ── 确定当轮实际扮演角色（优先级：user_msg metadata > 请求体 body > is_user 标记）──
    action_char_name = player_char_name           # 默认用原始玩家角色
    action_char_ref = player_char_ref             # 默认用原始玩家角色头像

    # 从消息 metadata 读取
    pc_id_from_meta = None
    if user_msg:
        try:
            import json as _j2
            um_meta = _j2.loads(user_msg["metadata"] or "{}")
            pc_id_from_meta = um_meta.get("player_character_id")
        except Exception as _e:
            logger.warning("[实况生图] metadata解析异常: %s", _e)

    # 旧卡兜底：metadata 没有 player_character_id 时使用请求体传入的当前选中角色
    pc_id = pc_id_from_meta or body.player_character_id
    plot_id = session_row["plot_id"] if session_row else None
    if pc_id and plot_id:
        # 必须同时校验 plot_id，防止跨项目角色 ID 碰撞串入错误角色
        async with db.execute(
            "SELECT name, avatar_url, reference_image FROM characters WHERE id=? AND plot_id=?",
            (pc_id, plot_id),
        ) as _c:
            _cr = await _c.fetchone()
        if _cr:
            action_char_name = _cr["name"]
            action_char_ref = _cr["avatar_url"] or _cr["reference_image"] or ""
        else:
            logger.warning("[实况生图] player_character_id=%s 不属于当前 plot=%s，fallback to is_user=1", pc_id, plot_id)

    # 从 active_chars 中排除用户当前扮演的角色（避免同一角色在 AI 和用户两边都出现）
    if action_char_name:
        active_chars = [c for c in active_chars if c["name"] != action_char_name]

    # 获取全局用户设置（头像 + 性别）
    async with db.execute(
        "SELECT key, value FROM settings WHERE key IN ('user_avatar', 'user_gender')"
    ) as cur:
        settings_rows = await cur.fetchall()
    settings = {r["key"]: r["value"] for r in settings_rows}
    # 优先用当轮实际扮演角色头像，其次原始玩家角色，最后全局设置
    user_avatar = action_char_ref or player_char_ref or settings.get("user_avatar", "")
    user_gender = settings.get("user_gender", "")

    # ── 组装角色信息（仅出镜角色）────────────────────────────────────────────
    char_info_parts = []
    chars_with_ref: dict[str, str] = {}  # name → ref_url
    for c in active_chars:
        appearance = (c["image_prompt"] or "")[:150]   # 外貌描述（生成头像时用的 prompt）
        personality = (c["description"] or "")[:80]    # 性格/背景
        ref = c["avatar_url"] or c["reference_image"]   # 优先用最新生成头像，再用原始上传
        has_ref = bool(ref and ref.startswith(("http", "/uploads", "data:")))
        if has_ref:
            chars_with_ref[c["name"]] = ref

        lines = [c["name"]]
        if has_ref:
            # 有参考图时：外貌以参考图为准，不写文字外貌（避免文字描述与参考图冲突）
            lines.append("[参考图已提供，外貌以参考图为准，不要用文字描述外貌]")
        else:
            # 无参考图时：用 image_prompt 文字描述让模型保持外貌一致
            if appearance:
                lines.append(f"外貌：{appearance}")
        if personality:
            lines.append(f"性格：{personality}")
        char_info_parts.append("，".join(lines))

    char_info = "\n".join(char_info_parts) if char_info_parts else "未知角色"

    gender_label = ""
    if user_gender in ("female", "女"):
        gender_label = "USER=FEMALE"
    elif user_gender in ("male", "男"):
        gender_label = "USER=MALE"

    user_has_ref = bool(user_avatar and user_avatar.startswith(("http", "/uploads", "data:")))
    if user_has_ref:
        # 有参考图时：外貌以参考图为准，只提供性别方向
        user_desc = (gender_label if gender_label else "USER=UNSPECIFIED") + " [参考图已提供，外貌以参考图为准，不要用文字描述外貌]"
    else:
        user_desc = gender_label if gender_label else "USER=UNSPECIFIED"

    # 玩家角色说明：告知 LLM 用户当轮在扮演谁，以便把"我"正确映射到角色名
    if action_char_name:
        player_role_note = (
            f"\n\n[重要] 用户正在扮演角色「{action_char_name}」，"
            f"用户消息中的\"我\"即指代「{action_char_name}」，"
            f"生图时需将「{action_char_name}」视为在场角色。"
        )
    else:
        player_role_note = ""

    display_name = action_char_name or player_char_name or "你"
    background_info = (
        f"AI角色:\n{char_info}\n\n"
        f"用户角色(\"{display_name}\"): {user_desc}{player_role_note}"
    )

    dialogue = ""
    if user_msg:
        label = f"【{display_name}(用户扮演)】" if display_name else "[User Action]"
        dialogue += f"{label} - 60% visual weight: {user_msg['content']}\n\n"
    dialogue += f"[AI Narrative - 40% atmosphere] {msg['content']}"

    llm_user_msg = (
        f"=== Character & User Info ===\n{background_info}\n\n"
        f"=== Dialogue ===\n{dialogue}"
    )

    # ── 调用 LLM 生成图像 prompt ──────────────────────────────────────────
    # 叙事模式（全年龄向：固定 classic）
    mode = "classic"
    system = await load("snapshot", mode)
    img_prompt = await chat(
        [{"role": "user", "content": llm_user_msg}],
        system=system,
        max_tokens=8192,
    )
    img_prompt = img_prompt.strip()

    # LLM 返回空（被内容过滤等原因）时使用兜底 prompt
    if not img_prompt:
        import logging as _log
        _log.getLogger("galgame.image_chat").warning(
            "snapshot LLM returned empty, using fallback  session=%d  msg=%d",
            body.session_id, body.message_id,
        )
        char_names = [c["name"] for c in active_chars]
        name_str = "、".join(char_names) if char_names else "人物"
        img_prompt = (
            f"{name_str}，温柔对视，情感氛围浓郁，插画风格，横幅16:9构图"
        )

    # ── 组装参考图：prompt 提到角色名则带入参考图 ─────────────────────────
    # url → 角色名 反向映射，用于日志展示
    ref_url_to_name: dict[str, str] = {v: k for k, v in chars_with_ref.items()}
    if user_has_ref and user_avatar:
        ref_url_to_name[user_avatar] = action_char_name or player_char_name or "玩家"

    reference_images: list[str] = []
    for name, ref_url in chars_with_ref.items():
        if name in img_prompt:
            reference_images.append(ref_url)
    # prompt 为兜底时角色名不在其中，直接带所有有参考图的角色
    if not reference_images and chars_with_ref:
        reference_images = list(chars_with_ref.values())
    # 玩家角色在场判定：用户发了消息（"我"在场） → 带入玩家参考图
    # 不再要求"先有 NPC 图"，玩家是独立的在场判断
    if user_has_ref and user_msg:
        reference_images.append(user_avatar)

    ref_names = [ref_url_to_name.get(r, "?") for r in reference_images]
    logger.info("[实况生图] 最终参考图(%d张): %s", len(reference_images), ref_names)

    task_id = await enqueue(
        "chat_image",
        {
            "prompt": img_prompt,
            "session_id": body.session_id,
            "message_id": body.message_id,
            "reference_images": reference_images,
        },
    )
    return {"task_id": task_id, "prompt": img_prompt}


# ── 开场背景图 ────────────────────────────────────────────────────────────────

class OpeningBgBody(BaseModel):
    session_id: int


@router.post("/api/image/opening-bg")
async def opening_bg(body: OpeningBgBody):
    """基于剧情开场和角色设定生成会话背景图"""
    db = await get_db()
    async with db.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async with db.execute("SELECT * FROM plots WHERE id=?", (session["plot_id"],)) as cur:
        plot = await cur.fetchone()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情不存在")

    async with db.execute(
        "SELECT name, description, avatar_url, reference_image FROM characters WHERE plot_id=? AND is_user=0",
        (session["plot_id"],),
    ) as cur:
        chars = await cur.fetchall()

    # 角色描述文本（供 LLM 生成 prompt 时参考）
    char_desc_parts = []
    for c in chars:
        desc = (c["description"] or "")[:80]
        char_desc_parts.append(f"{c['name']}（{desc}）" if desc else c["name"])
    char_desc = "、".join(char_desc_parts)

    # 角色参考图（用于 img2img）
    reference_images: list[str] = []
    for c in chars:
        ref = c["avatar_url"] or c["reference_image"]   # 优先用最新生成头像，再用原始上传
        if ref and ref.startswith(("http", "/uploads", "data:")):
            reference_images.append(ref)

    context = (
        f"故事标题：{plot['title']}\n"
        f"主要角色：{char_desc}\n"
        f"开场：{plot['opening'][:300] if plot['opening'] else ''}\n"
        f"背景：{plot['backstory'][:300] if plot['backstory'] else ''}"
    )

    # 叙事模式（全年龄向：固定 classic）
    mode2 = "classic"
    system = await load("snapshot", mode2)
    img_prompt = await chat(
        [{"role": "user", "content": (
            "请为以下故事生成一张横幅开场背景插图的描述，"
            "以场景氛围为主，角色作为次要元素自然融入画面。\n\n" + context
        )}],
        system=system,
        max_tokens=8192,
    )
    img_prompt = img_prompt.strip()

    task_id = await enqueue(
        "opening_bg",
        {
            "prompt": img_prompt,
            "session_id": body.session_id,
            "reference_images": reference_images,
        },
    )
    return {"task_id": task_id}