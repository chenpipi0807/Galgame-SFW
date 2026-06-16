import asyncio
import json
import logging
import uuid

from db.database import get_db
from core.image_gen import generate as img_generate
from core.memory import update_slots as memory_update_slots

logger = logging.getLogger("galgame.worker")


async def enqueue(task_type: str, payload: dict) -> str:
    task_id = str(uuid.uuid4())
    db = await get_db()
    await db.execute(
        "INSERT INTO tasks (id, type, payload, status) VALUES (?,?,?,?)",
        (task_id, task_type, json.dumps(payload, ensure_ascii=False), "pending"),
    )
    await db.commit()
    return task_id


async def _set_task_status(task_id: str, status: str, result_url: str = "", error: str = ""):
    db = await get_db()
    await db.execute(
        "UPDATE tasks SET status=?, result_url=?, error=?, updated_at=datetime('now') WHERE id=?",
        (status, result_url, error, task_id),
    )
    await db.commit()


# 所有实况图（snapshot / chat_image / opening_bg）的强制前缀
# 告知模型严格复刻参考图的画风和角色五官
_SCENE_IMG_PREFIX = (
    "Follow the art style and character appearance from reference images. "
)

_STYLE_PREFIXES: dict[str, str] = {
    "realistic":  "photorealistic portrait, natural lighting, clean composition, ",
    "manhwa":     "Korean manhwa webtoon art style, clean linework, soft gradient shading, delicate pastel tones, ",
    "anime":      "anime illustration style, cel shading, vibrant colors, clean linework, ",
    "otome3d":    "high-end otome game CG style, 3D character render, bishoujo beautiful face, volumetric hair, soft cinematic lighting, ",
    "donghua3d":  "Chinese 3D animation donghua style, 3D character render, xianxia fantasy aesthetics, flowing robes, natural facial features, cinematic lighting, ",
    "donghua2d":  "Chinese 2D animation donghua style, clean line art, Chinese ancient-style robes and hanfu costumes, elegant character design, flat color with soft shading, Chinese fantasy theme, ",
    "comics":     "western comic book style, bold ink outlines, dynamic line art, flat color with strong shading, American superhero comic aesthetic, ",
    "disney3d":   "3D CGI animated movie character, stylized rounded features, large expressive eyes, smooth subsurface skin, vibrant candy colors, ",
    "manga_bw":   "black and white manga illustration, ink linework, screentone shading, monochrome Japanese manga style, ",
}

_TRANSLATE_PROMPT = """Translate the following character appearance description into an English image generation prompt.
Rules:
- Output ONLY the English prompt, no explanations
- Keep all visual details (clothing, hair, eyes, body type, pose, expression, setting)
- Replace explicit sexual terms with tasteful equivalents (e.g. "revealing neckline" instead of graphic terms)
- Do NOT add any quality tags, resolution keywords, or style modifiers (no "masterpiece", "8K", "ultra", "high quality", "detailed", "best quality")
- Keep it under 300 words"""


async def _translate_to_english(prompt: str) -> str:
    """将中文形象描述翻译为英文生图 prompt，同时规避内容审核敏感词"""
    # 已经是英文则跳过
    if all(ord(c) < 128 or c in ' .,!?-_()[]{}' for c in prompt[:50]):
        return prompt
    from core.llm import chat as _chat
    try:
        result = await _chat(
            [{"role": "user", "content": f"{_TRANSLATE_PROMPT}\n\nChinese description:\n{prompt}"}],
            temperature=0.3,
            max_tokens=512,
        )
        return result.strip() or prompt
    except Exception as e:
        logger.warning("Prompt translation failed: %s", e)
        return prompt


def _build_char_prompt(image_prompt: str, image_style: str) -> str:
    prefix = _STYLE_PREFIXES.get(image_style, "")
    return f"{prefix}{image_prompt}, ultra-high definition, exquisite detail, best quality".strip()


_DOWNGRADE_PROMPT = """You are an image generation prompt safety editor.
Rewrite the following prompt to remove any content that may trigger content moderation (nudity, explicit body parts, sexual acts, graphic violence).
Rules:
- Replace explicit terms with tasteful equivalents (e.g. "low neckline" instead of bare chest, "curvaceous figure" instead of explicit body terms)
- Keep all visual appearance details: hair, eyes, face, clothing style, atmosphere, art style tags
- Do NOT add new details or change the character concept
- Output ONLY the rewritten prompt, no explanations"""


async def _downgrade_prompt(prompt: str) -> str:
    """通过 LLM 对生图 prompt 做内容降级，去除可能触发审核的词汇"""
    from core.llm import chat as _chat
    try:
        result = await _chat(
            [{"role": "user", "content": f"{_DOWNGRADE_PROMPT}\n\nOriginal prompt:\n{prompt}"}],
            temperature=0.2,
            max_tokens=512,
        )
        downgraded = result.strip()
        logger.info("Prompt downgraded  original_len=%d  new_len=%d", len(prompt), len(downgraded))
        return downgraded or prompt
    except Exception as e:
        logger.warning("Prompt downgrade failed: %s", e)
        return prompt


async def _generate_with_downgrade(prompt: str, size: str, reference_images: list[str] | None):
    """生图统一入口：失败（多为内容审核拒绝）→ LLM 降级 prompt 后重试一次。
    经典模式下提示词本就 SFW，此为第二道安全网，确保取巧聊出的露骨场景也能降级出图。"""
    try:
        return await img_generate(prompt, size=size, reference_images=reference_images or None)
    except Exception as first_err:
        logger.warning("ImgGen first attempt failed (%r), downgrading prompt and retrying…", first_err)
        downgraded = await _downgrade_prompt(prompt)
        url = await img_generate(downgraded, size=size, reference_images=reference_images or None)
        logger.info("ImgGen retry with downgraded prompt succeeded")
        return url


async def _process_character_img(task_id: str, payload: dict):
    image_prompt = payload.get("image_prompt", "")
    image_style = payload.get("image_style", "")
    character_id = payload.get("character_id")
    reference_images: list[str] = payload.get("reference_images") or []

    if not image_prompt or not character_id:
        await _set_task_status(task_id, "failed", error="缺少 image_prompt 或 character_id")
        return

    # 翻译为英文（AiHubMix/GPT-image 需要英文 prompt，同时规避内容审核）
    image_prompt = await _translate_to_english(image_prompt)
    final_prompt = _build_char_prompt(image_prompt, image_style)

    url = await _generate_with_downgrade(final_prompt, "1024x1024", reference_images)

    db = await get_db()
    await db.execute(
        "UPDATE characters SET avatar_url=?, image_url=? WHERE id=?",
        (url, url, character_id),
    )
    await db.commit()
    await _set_task_status(task_id, "completed", result_url=url)


async def _process_snapshot(task_id: str, payload: dict):
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id")
    reference_images: list[str] = payload.get("reference_images") or []
    if not prompt:
        await _set_task_status(task_id, "failed", error="缺少 prompt")
        return
    url = await _generate_with_downgrade(_SCENE_IMG_PREFIX + prompt, "1280x720", reference_images)
    if session_id:
        db = await get_db()
        await db.execute(
            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
            (session_id, url, "snapshot", json.dumps({"task_id": task_id})),
        )
        await db.commit()
    await _set_task_status(task_id, "completed", result_url=url)


async def _process_chat_image(task_id: str, payload: dict):
    """基于单轮对话内容生图（附带角色参考图）"""
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id")
    message_id = payload.get("message_id")
    reference_images: list[str] = payload.get("reference_images") or []

    if not prompt:
        await _set_task_status(task_id, "failed", error="缺少 prompt")
        return

    url = await _generate_with_downgrade(_SCENE_IMG_PREFIX + prompt, "1280x720", reference_images)

    if session_id:
        db = await get_db()
        await db.execute(
            "INSERT INTO messages (session_id, content, role, metadata) VALUES (?,?,?,?)",
            (
                session_id,
                url,
                "chat_image",
                json.dumps({"task_id": task_id, "ref_message_id": message_id}),
            ),
        )
        await db.commit()

    await _set_task_status(task_id, "completed", result_url=url)


async def _process_opening_bg(task_id: str, payload: dict):
    """生成会话开场背景图"""
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id")
    reference_images: list[str] = payload.get("reference_images") or []
    if not prompt:
        await _set_task_status(task_id, "failed", error="缺少 prompt")
        return
    url = await _generate_with_downgrade(_SCENE_IMG_PREFIX + prompt, "1280x720", reference_images)
    if session_id:
        db = await get_db()
        await db.execute(
            "UPDATE sessions SET bg_image_url=? WHERE id=?", (url, session_id)
        )
        await db.commit()
    await _set_task_status(task_id, "completed", result_url=url)


async def _process_memory_update(task_id: str, payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        await _set_task_status(task_id, "failed", error="缺少 session_id")
        return
    await memory_update_slots(session_id)
    await _set_task_status(task_id, "completed")


async def process_one(task_id: str, task_type: str, payload: dict):
    logger.info("Task START  %s  type=%s", task_id[:8], task_type)
    await _set_task_status(task_id, "running")
    try:
        if task_type == "character_img":
            await _process_character_img(task_id, payload)
        elif task_type == "snapshot":
            await _process_snapshot(task_id, payload)
        elif task_type == "chat_image":
            await _process_chat_image(task_id, payload)
        elif task_type == "opening_bg":
            await _process_opening_bg(task_id, payload)
        elif task_type == "memory_update":
            await _process_memory_update(task_id, payload)
        else:
            await _set_task_status(task_id, "failed", error=f"未知任务类型: {task_type}")
        logger.info("Task DONE   %s  type=%s", task_id[:8], task_type)
    except Exception as e:
        err_msg = repr(e) if not str(e) else str(e)
        logger.error("Task FAIL   %s  type=%s  error=%r", task_id[:8], task_type, e)
        await _set_task_status(task_id, "failed", error=err_msg)


async def process_pending():
    """定时轮询 pending 任务（每 3 秒）"""
    while True:
        try:
            db = await get_db()
            async with db.execute(
                "SELECT id, type, payload FROM tasks WHERE status='pending' ORDER BY created_at LIMIT 5"
            ) as cur:
                rows = await cur.fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                asyncio.create_task(process_one(row["id"], row["type"], payload))
        except Exception:
            pass
        await asyncio.sleep(3)
