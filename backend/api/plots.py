import json
import logging
import random
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from db.database import get_db
from core.llm import chat
from core.prompt_loader import load
from tasks.worker import enqueue

_CHAR_STYLES = ["realistic", "manhwa", "anime", "otome3d", "donghua3d", "donghua2d", "comics", "disney3d", "manga_bw"]

logger = logging.getLogger("galgame.plots")
router = APIRouter(prefix="/api/plots", tags=["plots"])


async def _get_narrative_mode() -> str:
    """叙事模式（全年龄向：固定 classic）"""
    return "classic"


# ─── Pydantic 模型 ────────────────────────────────────────────────────────────

class WizardStep1Body(BaseModel):
    concept: str
    plot_id: int | None = None  # 无则新建

class WizardStep2Body(BaseModel):
    plot_id: int
    vibe: list[str]

class WizardStep3Body(BaseModel):
    plot_id: int

class WizardStep4Body(BaseModel):
    plot_id: int
    opening: str  # 用户选定的 opening

class WizardStep5Body(BaseModel):
    plot_id: int
    backstory: str  # 用户选定的 backstory
    include_player_char: bool = True  # 默认提取玩家角色（系统提示词已指示第一个为主角）

class WizardStep6Body(BaseModel):
    plot_id: int
    characters: list[dict]  # [{name, description, personality, image_prompt}]
    player_char_index: int = 0  # 用户选择扮演的角色下标（0-based）

class WizardTavernBody(BaseModel):
    plot_id: int
    raw_json: str                  # parse-tavern-card 返回的 raw_json
    fallback_name: str = ""        # 兜底：规则解析的主角名
    fallback_description: str = "" # 兜底：规则解析的外貌/背景
    fallback_personality: str = "" # 兜底：规则解析的性格
    fallback_first_mes: str = ""   # 兜底：first_mes 原文

class PlotUpdate(BaseModel):
    title: str | None = None
    concept: str | None = None
    vibe: list[str] | None = None
    opening: str | None = None
    backstory: str | None = None
    style_settings: dict | None = None

class AttachLorebook(BaseModel):
    lorebook_id: int


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────

async def _get_plot_or_404(plot_id: int) -> dict:
    db = await get_db()
    async with db.execute("SELECT * FROM plots WHERE id=?", (plot_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="剧情不存在")
    return dict(row)


def _clean_json(text: str) -> str:
    """清理 LLM 常见输出问题"""
    # 去掉 markdown 代码块
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    # 替换全角标点
    text = (text
        .replace("：", ":")
        .replace("，", ",")
        .replace(""", '"').replace(""", '"')
        .replace("'", "'").replace("'", "'")
    )
    return text.strip()


async def _parse_json_list(text: str) -> list:
    """从 LLM 返回中提取 JSON 数组，容错处理"""
    cleaned = _clean_json(text)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"LLM 未返回有效 JSON 数组，原始输出：{text[:200]}")
    fragment = cleaned[start : end + 1]
    try:
        return json.loads(fragment)
    except json.JSONDecodeError as e:
        # 尝试 json5 风格宽松解析：去掉尾随逗号
        import re
        fragment2 = re.sub(r",\s*([\]}])", r"\1", fragment)
        try:
            return json.loads(fragment2)
        except json.JSONDecodeError:
            raise ValueError(f"JSON 解析失败({e})，片段：{fragment[:300]}")


# ─── 列表 + 单条 ──────────────────────────────────────────────────────────────

@router.get("")
async def list_plots():
    db = await get_db()
    async with db.execute("SELECT * FROM plots ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    result = []
    for row in rows:
        p = dict(row)
        # 附带角色数量
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM characters WHERE plot_id=?", (p["id"],)
        ) as c:
            cnt = await c.fetchone()
        p["character_count"] = cnt["cnt"] if cnt else 0
        result.append(p)
    return result


@router.get("/{plot_id}")
async def get_plot(plot_id: int):
    plot = await _get_plot_or_404(plot_id)
    db = await get_db()
    async with db.execute(
        "SELECT * FROM characters WHERE plot_id=? ORDER BY id", (plot_id,)
    ) as cur:
        chars = [dict(r) for r in await cur.fetchall()]
    plot["characters"] = chars
    return plot


@router.put("/{plot_id}")
async def update_plot(plot_id: int, body: PlotUpdate):
    await _get_plot_or_404(plot_id)
    db = await get_db()
    updates = body.model_dump(exclude_none=True)
    if "vibe" in updates:
        updates["vibe"] = json.dumps(updates["vibe"], ensure_ascii=False)
    if "style_settings" in updates:
        updates["style_settings"] = json.dumps(updates["style_settings"], ensure_ascii=False)
    if not updates:
        return {"ok": True}
    sets = ", ".join(f"{k}=?" for k in updates)
    await db.execute(f"UPDATE plots SET {sets} WHERE id=?", (*updates.values(), plot_id))
    await db.commit()
    return {"ok": True}


@router.put("/{plot_id}/publish")
async def publish_plot(plot_id: int):
    await _get_plot_or_404(plot_id)
    db = await get_db()
    await db.execute("UPDATE plots SET status='published' WHERE id=?", (plot_id,))
    await db.commit()
    return {"ok": True}


@router.delete("/{plot_id}")
async def delete_plot(plot_id: int):
    db = await get_db()
    await db.execute("DELETE FROM plots WHERE id=?", (plot_id,))
    await db.commit()
    return {"ok": True}


# ─── Lorebook 挂载 ────────────────────────────────────────────────────────────

@router.get("/{plot_id}/lorebooks")
async def get_plot_lorebooks(plot_id: int):
    db = await get_db()
    async with db.execute(
        """SELECT l.* FROM lorebooks l
           JOIN plot_lorebooks pl ON pl.lorebook_id = l.id
           WHERE pl.plot_id=?""",
        (plot_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.post("/{plot_id}/lorebooks")
async def attach_lorebook(plot_id: int, body: AttachLorebook):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
        (plot_id, body.lorebook_id),
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{plot_id}/lorebooks/{lorebook_id}")
async def detach_lorebook(plot_id: int, lorebook_id: int):
    db = await get_db()
    await db.execute(
        "DELETE FROM plot_lorebooks WHERE plot_id=? AND lorebook_id=?",
        (plot_id, lorebook_id),
    )
    await db.commit()
    return {"ok": True}


def _extract_entries_from_json(obj: dict) -> tuple[list[dict], str]:
    """从任意 JSON 中提取 lorebook 条目，返回 (entries_raw, name)。

    支持的格式：
    1. SillyTavern 世界书: {"entries": {"0": {"key":[], "content":"..."}}}
    2. 角色卡/预设: {"main_prompt": "...", "nsfw_prompt": "...", ...} — 每个字符串值作为一个条目
    3. 任意 JSON: 递归提取所有字符串值作为条目
    """
    entries: list[dict] = []
    name = obj.get("name", "") or obj.get("title", "") or "导入规则"

    # ── 格式1: SillyTavern 世界书 ──
    ents = obj.get("entries")
    if ents:
        if isinstance(ents, dict):
            for v in ents.values():
                if isinstance(v, dict) and (v.get("content") or v.get("key")):
                    entries.append(v)
        elif isinstance(ents, list):
            entries = [e for e in ents if isinstance(e, dict) and (e.get("content") or e.get("key"))]
        if entries:
            return entries, name

    # ── 格式2: 顶层字符串值作为条目（角色卡/jailbreak预设） ──
    _text_keys = ["main_prompt", "nsfw_prompt", "jailbreak_prompt",
                  "impersonation_prompt", "nsfw_avoidance_prompt", "description"]
    for k in _text_keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            entries.append({"key": [k], "content": v.strip()})

    # ── 格式3: 遍历顶层所有字符串键值 ──
    if not entries:
        for k, v in obj.items():
            if k in ("name", "title", "entries", "chat_completion_source", "openai_model",
                     "claude_model", "temperature", "frequency_penalty", "presence_penalty",
                     "top_p", "top_k", "openai_max_context", "openai_max_tokens",
                     "stream_openai", "api_url_scale", "reverse_proxy", "legacy_streaming",
                     "max_context_unlocked", "nsfw_toggle", "enhance_definitions",
                     "wrap_in_quotes", "send_if_empty", "nsfw_first", "jailbreak_system",
                     "bias_preset_selected", "wi_format"):
                continue
            if isinstance(v, str) and v.strip() and len(v.strip()) > 20:
                entries.append({"key": [k], "content": v.strip()})

    # ── 格式4: 兜底——整个 JSON 作为一条规则 ──
    if not entries:
        entries.append({
            "key": [name],
            "content": json.dumps(obj, ensure_ascii=False, indent=2),
        })

    return entries, name


class ImportLorebookBody(BaseModel):
    name: str = ""
    data: dict | None = None
    file_content: str | None = None


@router.post("/{plot_id}/lorebooks/import")
async def import_lorebook(plot_id: int, body: ImportLorebookBody):
    """通用 JSON 导入——自动识别 SillyTavern 世界书/角色卡预设/任意JSON"""
    db = await get_db()

    entries_raw: list[dict] = []
    name = body.name or "世界书"
    obj: dict | None = None

    # 来源1：直接传入的 dict
    if body.data:
        obj = body.data
    # 来源2：上传的文件内容
    elif body.file_content:
        try:
            raw = body.file_content
            if not raw.strip().startswith("{"):
                import base64 as _b64
                raw = _b64.b64decode(raw).decode("utf-8")
            obj = json.loads(raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {e}")

    if obj:
        entries_raw, auto_name = _extract_entries_from_json(obj)
        name = body.name or auto_name or "世界书"

    if not entries_raw:
        raise HTTPException(status_code=400, detail="未找到有效的条目数据")

    # 创建 lorebook
    async with db.execute(
        "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
        (name, f"从导入创建，共 {len(entries_raw)} 条规则"),
    ) as cur:
        row = await cur.fetchone()
    lb_id = row[0]

    # 创建条目
    for i, entry in enumerate(entries_raw):
        keywords = list(entry.get("key") or entry.get("keywords") or [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        # 合并 keysecondary（次要关键词）
        secondary = entry.get("keysecondary") or []
        if isinstance(secondary, list):
            keywords.extend([k for k in secondary if isinstance(k, str) and k.strip()])
        # 如果完全没有关键词，用 comment 兜底
        if not keywords and entry.get("comment"):
            keywords = [entry["comment"].strip()[:20]]
        content = entry.get("content", "")
        await db.execute(
            "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
            (lb_id, json.dumps(keywords, ensure_ascii=False), content, i),
        )

    # 挂载到剧情
    await db.execute(
        "INSERT OR IGNORE INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
        (plot_id, lb_id),
    )
    await db.commit()

    return {"id": lb_id, "name": name, "entries_count": len(entries_raw)}


@router.get("/{plot_id}/lorebooks/search")
async def search_plot_lorebooks(plot_id: int, q: str = ""):
    """模糊搜索当前剧情的所有世界书条目（关键词 + 内容）"""
    if not q.strip():
        return []
    db = await get_db()
    keyword = f"%{q.strip()}%"
    async with db.execute(
        """SELECT le.id, le.keywords, le.content, le.order_idx,
                  lb.id as lorebook_id, lb.title as lorebook_title
           FROM lorebook_entries le
           JOIN lorebooks lb ON lb.id = le.lorebook_id
           JOIN plot_lorebooks pl ON pl.lorebook_id = lb.id
           WHERE pl.plot_id = ?
             AND (le.keywords LIKE ? OR le.content LIKE ?)
           ORDER BY lb.title, le.order_idx""",
        (plot_id, keyword, keyword),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    for row in rows:
        try:
            row["keywords"] = json.loads(row["keywords"])
        except Exception:
            row["keywords"] = []
    return rows


# ─── 6步向导 ──────────────────────────────────────────────────────────────────

@router.post("/wizard/1")
async def wizard_step1(body: WizardStep1Body):
    """Concept → LLM 提炼标题，创建 plot 草稿"""
    system = await load("plot_creator", await _get_narrative_mode())
    title_raw = await chat(
        [{"role": "user", "content": f"用户的故事概念：{body.concept}\n\n请用一句话（10-20字）提炼出一个吸引人的故事标题，直接返回标题文字，不要加引号或额外说明。"}],
        system=system,
        max_tokens=8192,
    )
    title = title_raw.strip().strip('"').strip("《》")

    db = await get_db()
    if body.plot_id:
        await db.execute(
            "UPDATE plots SET title=?, concept=? WHERE id=?",
            (title, body.concept, body.plot_id),
        )
        await db.commit()
        return {"plot_id": body.plot_id, "title": title}
    else:
        async with db.execute(
            "INSERT INTO plots (title, concept) VALUES (?,?) RETURNING id",
            (title, body.concept),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return {"plot_id": row[0], "title": title}


@router.post("/wizard/2")
async def wizard_step2(body: WizardStep2Body):
    """保存 Vibe 标签"""
    db = await get_db()
    await db.execute(
        "UPDATE plots SET vibe=? WHERE id=?",
        (json.dumps(body.vibe, ensure_ascii=False), body.plot_id),
    )
    await db.commit()
    return {"ok": True, "plot_id": body.plot_id}


@router.post("/wizard/3")
async def wizard_step3(body: WizardStep3Body):
    """生成 3 个 Opening 选项"""
    plot = await _get_plot_or_404(body.plot_id)
    system = await load("plot_creator", await _get_narrative_mode())
    vibe = json.loads(plot["vibe"] or "[]")
    prompt = (
        f"故事标题：{plot['title']}\n"
        f"故事概念：{plot['concept']}\n"
        f"情感氛围标签：{', '.join(vibe)}\n\n"
        "请生成3个不同风格的故事开场（Opening），每个100-150字，包含场景设定和情绪氛围。\n"
        "【重要】第一个选项必须完全遵从上面的故事概念，不可偏离或改写。"
        "如果概念已经很详细，选项一仅做文字润色；如果概念简短，选项一仅做合理补充。"
        "第二、三个选项可以在概念基础上适度发挥。\n"
        '必须以JSON数组格式返回，格式：[{"title":"简短标题","content":"开场内容"}, ...]'
    )
    raw = await chat([{"role": "user", "content": prompt}], system=system, max_tokens=8192)
    options = await _parse_json_list(raw)
    return {"options": options, "plot_id": body.plot_id}


@router.post("/wizard/4")
async def wizard_step4(body: WizardStep4Body):
    """保存选定 Opening，生成 3 个 Backstory 选项"""
    plot = await _get_plot_or_404(body.plot_id)
    db = await get_db()
    await db.execute("UPDATE plots SET opening=? WHERE id=?", (body.opening, body.plot_id))
    await db.commit()

    system = await load("plot_creator", await _get_narrative_mode())
    vibe = json.loads(plot["vibe"] or "[]")
    prompt = (
        f"故事标题：{plot['title']}\n"
        f"故事概念：{plot['concept']}\n"
        f"开场：{body.opening}\n"
        f"情感氛围：{', '.join(vibe)}\n\n"
        "请为这个故事生成3个不同方向的背景设定（Backstory），每个120-200字，描述世界观、角色关系背景和核心张力。\n"
        "【重要】第一个选项必须完全遵从上面给出的故事概念和开场，不可偏离或改写。"
        "如果概念和开场已经很详细，选项一仅做文字润色和上下文衔接；如果简短，选项一仅做合理补充。"
        "第二、三个选项可以在已有基础上适度发挥。\n"
        '必须以JSON数组格式返回，格式：[{"title":"简短标题","content":"背景内容"}, ...]'
    )
    raw = await chat([{"role": "user", "content": prompt}], system=system, max_tokens=8192)
    options = await _parse_json_list(raw)
    return {"options": options, "plot_id": body.plot_id}


@router.post("/wizard/5")
async def wizard_step5(body: WizardStep5Body):
    """保存选定 Backstory，自动提取角色"""
    plot = await _get_plot_or_404(body.plot_id)
    db = await get_db()
    await db.execute("UPDATE plots SET backstory=? WHERE id=?", (body.backstory, body.plot_id))
    await db.commit()

    system = await load("character_gen", await _get_narrative_mode())
    if body.include_player_char:
        char_instruction = (
            "请从以上故事内容中提取所有主要角色，包括故事中'你'（用户/读者）所扮演的角色。\n"
            "对于'你'所扮演的角色，请根据描述推断其姓名（若有）、身份和特征，并在该角色 JSON 中加上 \"is_user\": true 字段。\n"
            "如果找不到明确的玩家角色描述，可不输出 is_user 角色。"
        )
    else:
        char_instruction = "请从以上故事内容中提取所有主要角色（不包含用户扮演的角色）。"

    prompt = (
        f"故事标题：{plot['title']}\n"
        f"故事概念：{plot['concept']}\n"
        f"开场：{plot['opening']}\n"
        f"背景：{body.backstory}\n\n"
        f"{char_instruction}\n"
        "严格按照系统提示中的角色卡片格式输出，直接返回 JSON 数组，不加任何说明。"
    )
    raw = await chat([{"role": "user", "content": prompt}], system=system, max_tokens=32768)
    try:
        characters = await _parse_json_list(raw)
    except ValueError:
        logger.warning("wizard/5 character extraction failed (LLM refusal or bad JSON): %s", raw[:120])
        characters = []
    return {"characters": characters, "plot_id": body.plot_id}


@router.post("/wizard/import-tavern")
async def wizard_import_tavern(body: WizardTavernBody):
    """酒馆卡一步导入：LLM 从 raw chara JSON 提取全量角色 + opening + backstory。
    LLM 失败时降级到规则解析的兜底字段。"""
    db = await get_db()

    prompt = (
        "以下是一张 SillyTavern 角色卡的完整原始 JSON 数据：\n\n"
        f"{body.raw_json[:12000]}\n\n"
        "请从中提取：\n"
        "1. 所有出场角色（description、first_mes、scenario、system_prompt 等字段中出现的\n"
        "   每一个有名字或可辨识的角色，严禁遗漏任何人物，哪怕只被提到一次。\n"
        "   用户会自行删除不需要的，但遗漏的角色无法恢复。\n"
        "   每个角色输出：\n"
        "   - name：姓名\n"
        "   - description：外貌与背景（100字左右，纯自然语言描述，禁止用 *星号*、[括号]、{{变量}} 等RP格式标记）\n"
        "   - personality：性格特征（50字，纯自然语言）\n"
        "   - image_prompt：中文生图描述（80-150字）。\n"
        "     从年龄感/体型/发型发色/面部特征/着装气质逐一描述，只写外貌，不写场景背景。\n"
        "     【重要】避免露骨或明确的性描写词汇，用隐晦含蓄的方式描述吸引力，确保图像可以生成。\n"
        '   - is_user：用户/玩家扮演的角色（通常是"你"）设为 true，其余为 false\n'
        "2. opening：从 first_mes 字段提取，但必须转换为自然叙事散文风格。\n"
        "   【关键】绝对禁止保留 *星号动作标记*、[系统指令]、{{变量占位符}}、RP格式符号。\n"
        "   将原文中的动作描述（通常用*包围）融合进叙事文本，写成流畅的自然段落。\n"
        "3. backstory：从 description/scenario/system_prompt 等字段中提炼世界背景，\n"
        "   用自然散文风格写成，禁止保留任何元指令、格式标记、系统提示词片段。\n"
        "   只保留世界观、人物关系、背景设定等实质性内容，丢弃一切写作指导、风格指令。\n\n"
        "只输出 JSON，不加任何说明：\n"
        '{"characters":[{"name":"...","description":"...","personality":"...","image_prompt":"...","is_user":false}],'
        '"opening":"...","backstory":"..."}'
    )

    result = None
    try:
        raw = await chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=32768,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s != -1 and e != -1:
            obj = json.loads(cleaned[s:e + 1])
            if isinstance(obj.get("characters"), list):
                result = obj
    except Exception as e_llm:
        logger.warning("import-tavern LLM failed: %s", e_llm)

    # 兜底：LLM 失败时用规则解析字段构造最小结果
    if not result:
        logger.info("import-tavern fallback to rule-parsed fields")
        result = {
            "characters": [{
                "name": body.fallback_name,
                "description": body.fallback_description,
                "personality": body.fallback_personality,
                "is_user": False,
            }] if body.fallback_name else [],
            "opening": body.fallback_first_mes,
            "backstory": body.fallback_description,
        }

    opening = result.get("opening") or body.fallback_first_mes or ""
    backstory = result.get("backstory") or body.fallback_description or ""

    await db.execute(
        "UPDATE plots SET opening=?, backstory=? WHERE id=?",
        (opening, backstory, body.plot_id),
    )
    await db.commit()

    return {
        "characters": result.get("characters", []),
        "opening": opening,
        "backstory": backstory,
        "plot_id": body.plot_id,
    }


@router.post("/wizard/6")
async def wizard_step6(body: WizardStep6Body):
    """保存角色，触发头像生成任务。所有角色统一处理，player_char_index 对应的角色标记 is_user=1。"""
    db = await get_db()
    # 删除该故事的全部旧角色（重新提交，用户角色也在其中）
    await db.execute("DELETE FROM characters WHERE plot_id=?", (body.plot_id,))
    await db.commit()

    task_ids = []
    player_idx = max(0, min(body.player_char_index, len(body.characters) - 1))

    for idx, char in enumerate(body.characters):
        is_player = 1 if idx == player_idx else 0
        aliases_val = char.get("aliases") or []
        if isinstance(aliases_val, list):
            aliases_val = json.dumps(aliases_val, ensure_ascii=False)
        elif not isinstance(aliases_val, str):
            aliases_val = "[]"
        async with db.execute(
            """INSERT INTO characters (plot_id, name, description, personality, image_prompt, image_style, reference_image, first_mes, is_user, aliases)
               VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (
                body.plot_id,
                char.get("name", ""),
                char.get("description", ""),
                char.get("personality", ""),
                char.get("image_prompt", ""),
                char.get("image_style", ""),
                char.get("reference_image", ""),
                char.get("first_mes", ""),
                is_player,
                aliases_val,
            ),
        ) as cur:
            row = await cur.fetchone()
        char_id = row[0]
        await db.commit()

        ref_img = char.get("reference_image", "")
        if ref_img:
            await db.execute(
                "UPDATE characters SET avatar_url=?, image_url=? WHERE id=?",
                (ref_img, ref_img, char_id),
            )
            await db.commit()
            task_ids.append({"character_id": char_id, "task_id": None, "avatar_url": ref_img, "is_user": bool(is_player)})
        else:
            # 构建生图 prompt：优先 image_prompt，否则拼接外貌+性格作为保底
            img_prompt = char.get("image_prompt", "").strip()
            if not img_prompt:
                parts = [p for p in [char.get("description", ""), char.get("personality", "")] if p and p.strip()]
                img_prompt = "。".join(parts).strip()

            # 风格：未选则随机
            img_style = char.get("image_style", "").strip() or random.choice(_CHAR_STYLES)

            if img_prompt:
                task_id = await enqueue(
                    "character_img",
                    {
                        "character_id": char_id,
                        "image_prompt": img_prompt,
                        "image_style": img_style,
                        "reference_images": [],
                    },
                )
                task_ids.append({"character_id": char_id, "task_id": task_id, "is_user": bool(is_player)})
            else:
                # 完全没有任何描述，显示在列表里但不生成
                task_ids.append({"character_id": char_id, "task_id": None, "avatar_url": "", "is_user": bool(is_player)})

    # ── LLM 从概念/背景中提取世界规则（用户输入的世界书、隐藏机制、关键地点等） ──
    try:
        plot = await _get_plot_or_404(body.plot_id)
        concept_text = plot['concept'] or ''
        backstory_text = plot['backstory'] or ''

        if concept_text or backstory_text:
            lore_prompt = (
                "请从以下故事设定中提取所有世界规则条目，包括但不限于：\n"
                "- 关键地点（建筑、区域、场景）及其设定\n"
                "- 隐藏游戏机制（数值系统、好感度、触发条件）\n"
                "- 阵营/势力关系与矛盾\n"
                "- 关键物品及其象征意义\n"
                "- 事件触发条件与后果\n"
                "- 人物关系网络\n\n"
                "每条规则用简短中文描述（30-120字），并配有触发关键词。\n"
                "输出为 JSON 数组：\n"
                '[{"keywords":["关键词1","关键词2"],"content":"规则描述..."}, ...]\n\n'
                f"故事概念：\n{concept_text}\n\n"
                f"背景设定：\n{backstory_text}\n\n"
                "只输出 JSON 数组，不加任何说明。"
            )
            lore_raw = await chat(
                [{"role": "user", "content": lore_prompt}],
                system="你是世界设定整理师，擅长从长篇故事设定中提取结构化世界规则。仔细阅读用户提供的全部文本，提取每一条设定为独立条目。不要遗漏任何关键词触发的规则。",
                max_tokens=32768,
            )
            llm_lore_entries = await _parse_json_list(lore_raw)
            if llm_lore_entries:
                # 创建 lorebook
                async with db.execute(
                    "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
                    ("📖 世界书", f"LLM 从概念中自动提取，共 {len(llm_lore_entries)} 条规则"),
                ) as cur_lb:
                    lb_row = await cur_lb.fetchone()
                lb_id = lb_row[0]
                await db.commit()
                # 逐条插入 lorebook_entries
                for i, entry in enumerate(llm_lore_entries):
                    kw = entry.get("keywords") or entry.get("key") or []
                    if isinstance(kw, str):
                        kw = [k.strip() for k in kw.split(",") if k.strip()]
                    await db.execute(
                        "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
                        (lb_id, json.dumps(kw, ensure_ascii=False), entry.get("content", ""), i),
                    )
                await db.commit()
                # 挂载到剧情
                await db.execute(
                    "INSERT INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
                    (body.plot_id, lb_id),
                )
                await db.commit()
                logger.info("LLM lorebook extracted  entries=%d  plot=%d", len(llm_lore_entries), body.plot_id)
    except Exception as e:
        logger.warning("LLM lorebook extraction failed: %s", e)

    # ── 自动生成系统线索世界书（从角色秘密字段，静默注入） ──
    auto_lore_entries = []
    for char in body.characters:
        name = char.get("name", "")
        faction = char.get("faction", "")
        secret = char.get("secret_objective", "")
        items = char.get("starting_items") or []
        location = char.get("starting_location", "")

        if secret or items or location:
            keywords = [name]
            if location: keywords.append(location)
            for item in items:
                keywords.append(item[:10])

            parts = []
            if faction: parts.append(f"阵营：{faction}")
            if secret: parts.append(f"秘密任务：{secret}")
            if items: parts.append(f"初始物品：{'、'.join(items)}")
            if location: parts.append(f"初始位置：{location}")

            if parts:
                auto_lore_entries.append({
                    "keywords": keywords,
                    "content": "【角色线索】" + "；".join(parts) + "。\n（此线索仅供叙事参考，不应被角色直接知晓，除非被相关行动揭示。）"
                })

    if auto_lore_entries:
        # 创建 lorebook
        async with db.execute(
            "INSERT INTO lorebooks (title, description) VALUES (?,?) RETURNING id",
            ("🎯 系统线索", f"从角色秘密字段自动生成，共 {len(auto_lore_entries)} 条线索"),
        ) as cur_lb:
            lb_row = await cur_lb.fetchone()
        lb_id = lb_row[0]
        await db.commit()
        # 逐条插入 lorebook_entries
        for i, entry in enumerate(auto_lore_entries):
            await db.execute(
                "INSERT INTO lorebook_entries (lorebook_id, keywords, content, order_idx) VALUES (?,?,?,?)",
                (lb_id, json.dumps(entry["keywords"], ensure_ascii=False), entry["content"], i),
            )
        await db.commit()
        # 挂载到剧情
        await db.execute(
            "INSERT INTO plot_lorebooks (plot_id, lorebook_id) VALUES (?,?)",
            (body.plot_id, lb_id),
        )
        await db.commit()

    await db.execute("UPDATE plots SET status='ready' WHERE id=?", (body.plot_id,))
    await db.commit()
    return {"ok": True, "task_ids": task_ids, "plot_id": body.plot_id}