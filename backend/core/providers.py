"""
Provider（API 连接）配置 —— 统一的「连接列表」模型，存于本地 DB（settings.providers_config）。
取代旧的「每厂商一组 .env 变量」写法，用户可自由增删/命名/启用任意三方代理，无需改代码。

连接类型（api_type）：
- LLM：只有 "openai"（/chat/completions），覆盖 Agnes / DeepSeek / 任意 OpenAI 兼容代理。
- 生图："openai-image"（/images/generations(+edits)，覆盖 AiHubMix/gpt-image/多数代理）、
        "gemini"（generateContent）、"agnes-image"（Agnes 专属 extra_body 流派，仅内置）。

Agnes 两条为内置(builtin)：key/base 由代码常量注入、不可删，保证零配置开箱即用。
首次启动若 DB 无配置，则从旧 .env 迁移一次。
"""
import json
import uuid

from core.env_config import read as env_read
from db.database import get_db

# ── Agnes 内置常量（永久免费无限，开箱即用）──────────────────────
AGNES_API_KEY   = "sk-SH5wdZMtUCTQzC0Lbcx8KBHURXcQjMlT2dODm9Nxou7QsMwH"
AGNES_LLM_BASE  = "https://apihub.agnes-ai.com/v1"
AGNES_LLM_MODEL = "agnes-2.0-flash"
AGNES_IMG_BASE  = "https://apihub.agnes-ai.com/v1"
AGNES_IMG_MODEL = "agnes-image-2.1-flash"

_SETTINGS_KEY = "providers_config"
_CACHE: dict | None = None


# ── 内置连接模板 ────────────────────────────────────────────────
def _agnes_llm() -> dict:
    return {"id": "agnes-llm", "kind": "llm", "label": "Agnes 叙事", "api_type": "openai",
            "base_url": "", "api_key": "", "model": AGNES_LLM_MODEL, "builtin": True}


def _agnes_img() -> dict:
    return {"id": "agnes-img", "kind": "image", "label": "Agnes 生图", "api_type": "agnes-image",
            "base_url": "", "api_key": "", "model": AGNES_IMG_MODEL, "builtin": True}


def _default_config() -> dict:
    """首次启动：从旧 .env 迁移，构建初始配置（Agnes 内置 + 三张常见示例）。"""
    env = env_read()
    deepseek = {
        "id": uuid.uuid4().hex[:12], "kind": "llm", "label": "DeepSeek", "api_type": "openai",
        "base_url": env.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
        "api_key": env.get("DEEPSEEK_API_KEY", ""),
        "model": env.get("DEEPSEEK_MODEL") or "deepseek-v4-flash", "builtin": False,
    }
    aihubmix = {
        "id": uuid.uuid4().hex[:12], "kind": "image", "label": "AiHubMix · gpt-image", "api_type": "openai-image",
        "base_url": env.get("AIHUBMIX_BASE_URL") or "https://aihubmix.com/v1",
        "api_key": env.get("AIHUBMIX_API_KEY", ""),
        "model": "gpt-image-2", "builtin": False,
    }
    gemini = {
        "id": uuid.uuid4().hex[:12], "kind": "image", "label": "Gemini 图像", "api_type": "gemini",
        "base_url": env.get("GEMINI_BASE_URL", ""),
        "api_key": env.get("GEMINI_API_KEY", ""),
        "model": env.get("GEMINI_MODEL") or "gemini-3.1-flash-image-preview", "builtin": False,
    }
    providers = [_agnes_llm(), _agnes_img(), deepseek, aihubmix, gemini]

    # active 指针沿用旧 LLM_PROVIDER / IMG_PROVIDER（仅当对应连接确有 key 才指过去）
    active_llm = "agnes-llm"
    if env.get("LLM_PROVIDER") == "deepseek" and deepseek["api_key"]:
        active_llm = deepseek["id"]
    active_image = "agnes-img"
    ip = env.get("IMG_PROVIDER")
    if ip == "gpt-image-2" and aihubmix["api_key"]:
        active_image = aihubmix["id"]
    elif ip == "gemini" and gemini["api_key"]:
        active_image = gemini["id"]

    return {"providers": providers, "active_llm": active_llm, "active_image": active_image}


def _ensure_builtins(cfg: dict) -> dict:
    """保证 Agnes 两条内置始终存在、active 指针有效（防误删/脏数据）。"""
    cfg.setdefault("providers", [])
    ids = {p.get("id") for p in cfg["providers"]}
    if "agnes-llm" not in ids:
        cfg["providers"].insert(0, _agnes_llm())
    if "agnes-img" not in ids:
        cfg["providers"].insert(1, _agnes_img())
    if not cfg.get("active_llm"):
        cfg["active_llm"] = "agnes-llm"
    if not cfg.get("active_image"):
        cfg["active_image"] = "agnes-img"
    return cfg


# ── DB 读写 + 缓存 ──────────────────────────────────────────────
async def _persist(cfg: dict):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (_SETTINGS_KEY, json.dumps(cfg, ensure_ascii=False)),
    )
    await db.commit()


async def load_config() -> dict:
    """启动时调用：从 DB 读配置；无则从 .env 迁移并落库。填充内存缓存。"""
    global _CACHE
    db = await get_db()
    async with db.execute("SELECT value FROM settings WHERE key=?", (_SETTINGS_KEY,)) as cur:
        row = await cur.fetchone()
    if row and row["value"]:
        try:
            cfg = _ensure_builtins(json.loads(row["value"]))
        except Exception:
            cfg = _default_config()
            await _persist(cfg)
    else:
        cfg = _default_config()
        await _persist(cfg)
    _CACHE = cfg
    return cfg


async def save_config(cfg: dict):
    global _CACHE
    cfg = _ensure_builtins(cfg)
    await _persist(cfg)
    _CACHE = cfg


def _get() -> dict:
    """同步取缓存；未加载时回退到纯内置 Agnes（保证 sync getter 永远可用）。"""
    if _CACHE is None:
        return {"providers": [_agnes_llm(), _agnes_img()],
                "active_llm": "agnes-llm", "active_image": "agnes-img"}
    return _CACHE


def _find(cfg: dict, pid: str | None) -> dict | None:
    return next((p for p in cfg["providers"] if p.get("id") == pid), None)


def _resolve(p: dict) -> dict:
    """把一条 provider 记录解析为运行时 cfg（Agnes 内置注入硬编码常量）。
    `provider` 字段为兼容旧日志保留（=label/api_type）。"""
    if p["id"] == "agnes-llm":
        return {"api_type": "openai", "provider": "agnes", "key": AGNES_API_KEY,
                "base_url": AGNES_LLM_BASE, "model": p.get("model") or AGNES_LLM_MODEL}
    if p["id"] == "agnes-img":
        return {"api_type": "agnes-image", "provider": "agnes", "key": AGNES_API_KEY,
                "base_url": AGNES_IMG_BASE, "model": p.get("model") or AGNES_IMG_MODEL}
    return {"api_type": p.get("api_type", "openai"), "provider": p.get("label") or p.get("api_type", ""),
            "key": p.get("api_key", ""), "base_url": (p.get("base_url") or "").rstrip("/"),
            "model": p.get("model", "")}


# ── 运行时 getter（被 llm.py / image_gen.py 同步调用）────────────
def get_llm_config() -> dict:
    cfg = _get()
    p = _find(cfg, cfg.get("active_llm"))
    if not p or p.get("kind") != "llm":
        p = _agnes_llm()
    return _resolve(p)


def get_img_config() -> dict:
    cfg = _get()
    p = _find(cfg, cfg.get("active_image"))
    if not p or p.get("kind") != "image":
        p = _agnes_img()
    return _resolve(p)


# ── CRUD（管理后台调用）─────────────────────────────────────────
def list_providers() -> dict:
    return _get()


def find_provider(pid: str) -> dict | None:
    return _find(_get(), pid)


def resolved_config(pid: str) -> dict | None:
    """按 id 返回运行时配置 {api_type,key,base_url,model}（内置 Agnes 注入常量）。
    供连通性测试复用，避免内置连接 base_url 为空时误用默认地址。"""
    p = _find(_get(), pid)
    return _resolve(p) if p else None


async def add_provider(kind: str, label: str, api_type: str,
                       base_url: str, api_key: str, model: str) -> str:
    cfg = _get()
    pid = uuid.uuid4().hex[:12]
    cfg["providers"].append({
        "id": pid, "kind": kind, "label": label, "api_type": api_type,
        "base_url": base_url, "api_key": api_key, "model": model, "builtin": False,
    })
    await save_config(cfg)
    return pid


async def update_provider(pid: str, label: str | None = None, api_type: str | None = None,
                          base_url: str | None = None, api_key: str | None = None,
                          model: str | None = None) -> bool:
    cfg = _get()
    p = _find(cfg, pid)
    if not p:
        return False
    if label is not None:
        p["label"] = label
    if api_type is not None:
        p["api_type"] = api_type
    if base_url is not None:
        p["base_url"] = base_url
    if model is not None:
        p["model"] = model
    if api_key:  # 留空则保留原 key
        p["api_key"] = api_key
    await save_config(cfg)
    return True


async def delete_provider(pid: str) -> bool:
    cfg = _get()
    p = _find(cfg, pid)
    if not p:
        return False
    if p.get("builtin"):
        raise ValueError("内置连接不可删除")
    cfg["providers"] = [x for x in cfg["providers"] if x.get("id") != pid]
    if cfg.get("active_llm") == pid:
        cfg["active_llm"] = "agnes-llm"
    if cfg.get("active_image") == pid:
        cfg["active_image"] = "agnes-img"
    await save_config(cfg)
    return True


async def set_active(pid: str) -> bool:
    cfg = _get()
    p = _find(cfg, pid)
    if not p:
        return False
    if p.get("kind") == "llm":
        cfg["active_llm"] = pid
    else:
        cfg["active_image"] = pid
    await save_config(cfg)
    return True
