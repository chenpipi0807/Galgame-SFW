import sys
import aiofiles
from pathlib import Path
from core.paths import SYSPROMPT_DIR

DEFAULT_MODE = "classic"

_cache: dict[str, str] = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL = 10

def _resolve_path(name: str, mode: str = DEFAULT_MODE) -> Path:
    return SYSPROMPT_DIR / mode / f"{name}.md"  # 秒，确保前端改动 10 秒内生效


async def load(name: str, mode: str = DEFAULT_MODE) -> str:
    """加载 sysprompt/{mode}/{name}.md，10秒缓存过期自动重读"""
    import time
    cache_key = f"{mode}:{name}"
    now = time.time()
    if cache_key in _cache and (now - _cache_ts.get(cache_key, 0)) < _CACHE_TTL:
        return _cache[cache_key]

    path = _resolve_path(name, mode)
    if not path.exists():
        if mode != "classic":
            fallback = _resolve_path(name, "classic")
            if fallback.exists():
                path = fallback
            else:
                return ""
        else:
            return ""

    async with aiofiles.open(path, encoding="utf-8") as f:
        content = await f.read()
    _cache[cache_key] = content
    _cache_ts[cache_key] = now
    return content


async def save(name: str, content: str, mode: str = DEFAULT_MODE) -> None:
    """保存并清空该条目缓存。
    ⚠️ 打包(冻结)态下提示词是只读 bundle 资源，不支持在线编辑。
    """
    if getattr(sys, "frozen", False):
        raise RuntimeError("打包版不支持在线编辑提示词（提示词为内置只读资源）")
    path = _resolve_path(name, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
    k = f"{mode}:{name}"
    _cache.pop(k, None)
    _cache_ts.pop(k, None)


def list_prompts(mode: str = DEFAULT_MODE) -> list[str]:
    """列出指定模式下的所有提示词文件名（不含扩展名）"""
    mode_dir = SYSPROMPT_DIR / mode
    if not mode_dir.exists():
        return []
    return [p.stem for p in mode_dir.glob("*.md")]


def list_modes() -> list[str]:
    """列出所有可用模式"""
    if not SYSPROMPT_DIR.exists():
        return ["classic"]
    modes = []
    for d in SYSPROMPT_DIR.iterdir():
        if d.is_dir() and (d / "narrator.md").exists():
            modes.append(d.name)
    return sorted(modes) if modes else ["classic"]


def invalidate(name: str | None = None, mode: str | None = None):
    """清空缓存"""
    if name and mode:
        k = f"{mode}:{name}"
        _cache.pop(k, None)
        _cache_ts.pop(k, None)
    elif name:
        keys = [k for k in _cache if k.endswith(f":{name}")]
        for k in keys:
            _cache.pop(k, None)
            _cache_ts.pop(k, None)
    else:
        _cache.clear()
        _cache_ts.clear()