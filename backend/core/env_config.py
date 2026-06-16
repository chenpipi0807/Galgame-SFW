"""
统一从 .env 文件读写 provider 配置。
不依赖数据库，避免 key 存两处。
"""
from dotenv import dotenv_values, set_key
from core.paths import ENV_PATH

_DEFAULTS = {
    "AGNES_API_KEY":    "",
    "LLM_PROVIDER":     "agnes",
    "DEEPSEEK_API_KEY": "",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "DEEPSEEK_MODEL":   "deepseek-v4-flash",
    "IMG_PROVIDER":     "agnes",
    "GEMINI_API_KEY":   "",
    "GEMINI_BASE_URL":  "",
    "GEMINI_MODEL":     "gemini-3.1-flash-image-preview",
    "AIHUBMIX_API_KEY":  "",
    "AIHUBMIX_BASE_URL": "https://aihubmix.com/v1",
}


def read() -> dict:
    """读取 .env，返回所有 provider 相关配置（缺失则用默认值）"""
    vals = dotenv_values(str(ENV_PATH))
    return {k: vals.get(k, v) for k, v in _DEFAULTS.items()}


def write(**kwargs):
    """将 key=value 写入 .env（仅接受 _DEFAULTS 中定义的 key）"""
    for k, v in kwargs.items():
        if k not in _DEFAULTS:
            continue
        if v is None:
            continue
        set_key(str(ENV_PATH), k, str(v))


def get_llm_config() -> dict:
    cfg = read()
    provider = cfg["LLM_PROVIDER"]
    if provider == "deepseek":
        return {
            "provider": "deepseek",
            "key":      cfg["DEEPSEEK_API_KEY"],
            "base_url": (cfg["DEEPSEEK_BASE_URL"] or "https://api.deepseek.com").rstrip("/"),
            "model":    cfg["DEEPSEEK_MODEL"] or "deepseek-v4-flash",
        }
    return {
        "provider": "agnes",
        "key":      cfg["AGNES_API_KEY"],
        "base_url": "https://apihub.agnes-ai.com/v1",
        "model":    "agnes-2.0-flash",
    }


def get_img_config() -> dict:
    cfg = read()
    provider = cfg["IMG_PROVIDER"]
    if provider == "gemini":
        return {
            "provider": "gemini",
            "key":      cfg["GEMINI_API_KEY"],
            "base_url": (cfg["GEMINI_BASE_URL"] or "").rstrip("/"),
            "model":    cfg["GEMINI_MODEL"] or "gemini-3.1-flash-image-preview",
        }
    if provider == "gpt-image-2":
        return {
            "provider": "gpt-image-2",
            "key":      cfg["AIHUBMIX_API_KEY"],
            "base_url": (cfg["AIHUBMIX_BASE_URL"] or "https://aihubmix.com/v1").rstrip("/"),
            "model":    "gpt-image-2",
        }
    return {
        "provider": "agnes",
        "key":      cfg["AGNES_API_KEY"],
        "base_url": "https://apihub.agnes-ai.com/v1",
        "model":    "agnes-image-2.1-flash",
    }
