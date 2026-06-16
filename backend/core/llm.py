import httpx
import json
import logging
from typing import AsyncIterator
from core.providers import get_llm_config

# 兼容旧代码的常量
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_MODEL = "agnes-2.0-flash"
BASE_URL = AGNES_BASE_URL
LLM_MODEL = AGNES_MODEL

logger = logging.getLogger("galgame.llm")

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=300.0, trust_env=False)
    return _client


async def get_api_key() -> str:
    """兼容旧调用"""
    return get_llm_config()["key"]


async def chat(
    messages: list[dict],
    system: str | None = None,
    temperature: float = 0.9,
    max_tokens: int = 8192,
    response_format: dict | None = None,
) -> str:
    cfg = get_llm_config()
    payload_messages = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    logger.info("LLM chat  provider=%s  msgs=%d  max_tokens=%d", cfg["provider"], len(payload_messages), max_tokens)
    body: dict = {
        "model": cfg["model"],
        "messages": payload_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    try:
        resp = await get_client().post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        msg = choice.get("message", {})
        result = (msg.get("content") or "").strip()
        finish_reason = choice.get("finish_reason", "unknown")

        # 输出被 token 限制截断时，翻倍重试（无论 content 是否为空）
        if finish_reason == "length" and max_tokens < 65536:
            logger.warning("LLM chat  finish=length (truncated), retrying with max_tokens=%d",
                           max_tokens * 2)
            return await chat(messages, system, temperature, max_tokens * 2, response_format)

        if not result:
            reason = (msg.get("reasoning_content") or "")[:200]
            logger.warning("LLM chat  EMPTY content  finish_reason=%s  reason_preview=%s  provider=%s",
                           finish_reason, reason, cfg["provider"])
        else:
            logger.info("LLM chat  OK  len=%d", len(result))

        # 酒馆模型：剥离 <think>...</think> 思考内容
        model = cfg.get("model", "")
        if "tavern" in model.lower() and result:
            import re
            result = re.sub(r'</?think>', '', result)
        return result
    except Exception as e:
        logger.error("LLM chat  FAIL  %s", e)
        raise


async def stream(
    messages: list[dict],
    system: str | None = None,
    temperature: float = 0.9,
    max_tokens: int = 8192,
) -> AsyncIterator[str]:
    cfg = get_llm_config()
    payload_messages = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    model = cfg.get("model", "")
    _is_tavern = "tavern" in model.lower()
    _think_buf = ""       # 累积 think 标签内容以跳过
    _in_think = False

    async with get_client().stream(
        "POST",
        f"{cfg['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        },
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if raw == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
                delta = chunk["choices"][0]["delta"]
                content = delta.get("content", "")
                # 跳过 reasoning_content（思考过程）
                if not content:
                    continue

                if _is_tavern:
                    _think_buf += content
                    # 检测并剥离 <think>...</think> 标签
                    while True:
                        if not _in_think:
                            start = _think_buf.find("&lt;think&gt;")
                            if start == -1: start = _think_buf.find("<think>")
                            if start == -1:
                                # 没有 think，全部输出
                                if _think_buf:
                                    yield _think_buf
                                _think_buf = ""
                                break
                            # 输出 think 之前的内容
                            if start > 0:
                                yield _think_buf[:start]
                            _think_buf = _think_buf[start:]
                            _in_think = True
                        else:
                            end = _think_buf.find("&lt;/think&gt;")
                            if end == -1: end = _think_buf.find("</think>")
                            if end == -1:
                                # think 还没结束，清空缓冲区等待更多
                                _think_buf = ""
                                break
                            _think_buf = _think_buf[end + len("</think>"):].lstrip()
                            _in_think = False
                else:
                    yield content

            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    # 流结束后清空残余（非 think 内容）
    if _think_buf and not _in_think:
        yield _think_buf
