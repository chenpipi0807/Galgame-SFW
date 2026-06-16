import base64
import uuid
import httpx
import asyncio
import logging
import json as _json
from pathlib import Path
from core.providers import get_img_config
from core.llm import get_client

AGNES_IMG_MODEL = "agnes-image-2.1-flash"
IMG_MODEL = AGNES_IMG_MODEL

logger = logging.getLogger("galgame.imggen")

from core.paths import LOGS_DIR as _PROMPT_LOG_DIR, UPLOADS_DIR as _UPLOADS_DIR, ensure_dir
ensure_dir(_PROMPT_LOG_DIR)

def _log_prompt(prompt: str):
    """将生图 prompt 写入专用日志文件，方便排查"""
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"\n{'='*60}\n{ts}\n{'='*60}\n{prompt}\n"
    try:
        with open(_PROMPT_LOG_DIR / "img_prompts.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def _resize_data_uri(data_uri: str, max_side: int = 1024) -> str:
    """将 data URI 图片缩放到最长边 ≤ max_side，保持宽高比。失败则原样返回。"""
    try:
        from PIL import Image
        import io
        header, b64 = data_uri.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        w, h = img.size
        if max(w, h) <= max_side:
            return data_uri  # 已经够小，不处理
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        # RGBA/P 转 RGB 避免 JPEG 保存报错
        fmt = "PNG" if mime == "image/png" else "JPEG"
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format=fmt, quality=85)
        new_b64 = base64.b64encode(out.getvalue()).decode()
        logger.debug("_resize_data_uri  %dx%d → %dx%d", w, h, int(w * scale), int(h * scale))
        return f"data:{mime};base64,{new_b64}"
    except Exception as e:
        logger.warning("_resize_data_uri failed: %s", e)
        return data_uri


async def _ref_to_base64(ref: str) -> str | None:
    """把任意格式的图片引用转为 data URI（base64）。
    - data URI → 原样返回
    - /uploads/ 路径 → 读本地文件
    - http(s):// URL → 下载后转 base64（修复 Agnes 返回 HTTP URL 无法被 Gemini inlineData 使用的问题）
    """
    if not ref:
        return None
    if ref.startswith("data:"):
        return ref
    if ref.startswith("/uploads/"):
        filename = ref[len("/uploads/"):]
        filepath = _UPLOADS_DIR / filename
        if not filepath.exists():
            return None
        ext = filepath.suffix.lstrip(".").lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
        b64 = base64.b64encode(filepath.read_bytes()).decode()
        return f"data:{mime};base64,{b64}"
    if ref.startswith("http"):
        # Agnes 生成的图片是 HTTP URL，Gemini inlineData 需要 data URI，所以下载
        try:
            client = httpx.AsyncClient(timeout=None, trust_env=False)
            resp = await client.get(ref)
            await client.aclose()
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                b64 = base64.b64encode(resp.content).decode()
                return f"data:{ct};base64,{b64}"
        except Exception as e:
            logger.warning("_ref_to_base64 download failed  url=%s  err=%s", ref[:60], e)
        return None
    return None


async def _generate_gemini(cfg: dict, prompt: str, reference_images: list[str] | None = None, size: str = "1792x1024") -> str:
    base_url = cfg["base_url"]
    model = cfg["model"]
    key = cfg["key"]

    # 根据 size 推断 aspectRatio：1:1 头像 vs 16:9 场景图
    w_str, h_str = size.split("x") if "x" in size else ("1792", "1024")
    w, h = int(w_str), int(h_str)
    if w == h:
        aspect_ratio = "1:1"
    elif w > h:
        aspect_ratio = "16:9"
    else:
        aspect_ratio = "9:16"

    # 有参考图时，在 prompt 前加"按参考图风格"前缀，确保 Gemini 约束外貌风格一致
    if reference_images:
        ref_prefix = (
            "The provided reference images show the characters' appearances "
            "(hair color/style, eye color, clothing, art style). "
            "Strictly maintain their visual characteristics in the generated image.\n\n"
        )
        final_prompt = ref_prefix + prompt
    else:
        final_prompt = prompt

    parts = [{"text": final_prompt}]
    if reference_images:
        for ref in reference_images:
            data_uri = await _ref_to_base64(ref)
            if not data_uri or not data_uri.startswith("data:"):
                logger.warning("Gemini ref image skipped (not data URI after conversion)  ref=%s…", str(ref)[:40])
                continue
            data_uri = _resize_data_uri(data_uri)
            header, b64 = data_uri.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
            parts.append({"inlineData": {"mimeType": mime, "data": b64}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 1.0,
            "imageConfig": {"imageSize": "512", "aspectRatio": aspect_ratio},
        },
    }

    if "v1beta" in base_url:
        api_url = f"{base_url}/models/{model}:generateContent"
    else:
        api_url = f"{base_url}/v1beta/models/{model}:generateContent"

    n_refs = len(parts) - 1  # parts[0] is text
    logger.info("Gemini ImgGen  model=%s  refs=%d  aspectRatio=%s  prompt=%s",
                model, n_refs, aspect_ratio, final_prompt)
    _log_prompt(final_prompt)

    client = httpx.AsyncClient(timeout=None, trust_env=False)
    try:
        resp = await client.post(
            api_url,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    finally:
        await client.aclose()

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini API 无 candidates: {data}")

    parts_out = candidates[0].get("content", {}).get("parts", [])
    img_b64 = None
    for p in parts_out:
        if "inlineData" in p:
            img_b64 = p["inlineData"].get("data")
            break

    if not img_b64:
        raise RuntimeError(f"Gemini API 无图像数据: {parts_out}")

    filename = f"gemini_{uuid.uuid4().hex[:12]}.png"
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (_UPLOADS_DIR / filename).write_bytes(base64.b64decode(img_b64))
    logger.info("Gemini ImgGen  OK  saved=%s", filename)
    return f"/uploads/{filename}"


async def _aihubmix_parse_response(data: dict) -> str:
    """解析 AiHubMix 图像响应，支持 url / b64_json 两种格式"""
    item = data["data"][0]
    if item.get("url"):
        logger.info("AiHubMix ImgGen  OK  url=%s…", item["url"][:60])
        return item["url"]
    elif item.get("b64_json"):
        filename = f"gptimg_{uuid.uuid4().hex[:12]}.png"
        _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        (_UPLOADS_DIR / filename).write_bytes(base64.b64decode(item["b64_json"]))
        logger.info("AiHubMix ImgGen  OK  saved=%s", filename)
        return f"/uploads/{filename}"
    else:
        raise RuntimeError(f"AiHubMix 无图像数据: {item}")


# 瞬时网络错误：连接被对端重置 / 读取中断 / 连接失败 / 连接超时。
# 这类错误重试通常即可成功，与 HTTP 4xx/5xx 业务错误不同（后者重试无意义，不在此列）。
_TRANSIENT_NET_ERRORS = (
    httpx.ReadError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.WriteError,
)


async def _post_with_retry(client: httpx.AsyncClient, url: str, *, max_attempts: int = 3, **kwargs) -> httpx.Response:
    """对瞬时网络错误自动重试的 POST（聚合平台生图时常瞬断）。
    仅重试 _TRANSIENT_NET_ERRORS；HTTP 状态码错误由调用方的 raise_for_status 处理，不在此重试。
    """
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await client.post(url, **kwargs)
        except _TRANSIENT_NET_ERRORS as e:
            last_err = e
            if attempt < max_attempts:
                backoff = 1.5 * attempt  # 1.5s, 3.0s …
                logger.warning("ImgGen POST 瞬时网络错误 (%s)，第 %d/%d 次重试，%.1fs 后…",
                               type(e).__name__, attempt, max_attempts, backoff)
                await asyncio.sleep(backoff)
    raise last_err  # type: ignore[misc]


async def _generate_aihubmix(cfg: dict, prompt: str, reference_images: list[str] | None = None, size: str = "1792x1024") -> str:
    """AiHubMix gpt-image-2：
    - 无参考图 → /images/generations（文生图）
    - 有参考图 → /images/edits（multipart，参考图用于角色外貌一致性）
    size 由调用方指定，默认 1792x1024（横幅场景图）。
    """
    key = cfg["key"]
    base_url = cfg["base_url"]

    # 有参考图时在 prompt 前加外貌锁定前缀（与 Gemini 保持一致）
    if reference_images:
        ref_prefix = (
            "The provided reference images show the characters' appearances "
            "(hair color/style, eye color, clothing, art style). "
            "Strictly maintain their visual characteristics in the generated scene.\n\n"
        )
        final_prompt = ref_prefix + prompt
    else:
        final_prompt = prompt

    client = httpx.AsyncClient(timeout=120.0, trust_env=False)
    try:
        # ── 有参考图：/images/edits (multipart) ───────────────────────────────
        if reference_images:
            files: list = []
            for ref in reference_images[:4]:   # 最多 4 张参考图
                data_uri = await _ref_to_base64(ref)
                if not data_uri or not data_uri.startswith("data:"):
                    logger.warning("AiHubMix ref skipped  ref=%s…", str(ref)[:40])
                    continue
                # img2img multipart：压到 512px 并转 JPEG 减小 payload，避免服务端因包体过大重置连接
                data_uri = _resize_data_uri(data_uri, max_side=512)
                try:
                    from PIL import Image
                    import io
                    _, b64 = data_uri.split(",", 1)
                    img = Image.open(io.BytesIO(base64.b64decode(b64)))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    out = io.BytesIO()
                    img.save(out, format="JPEG", quality=85)
                    jpeg_bytes = out.getvalue()
                except Exception as _je:
                    logger.warning("AiHubMix JPEG convert failed (%s), using raw bytes", _je)
                    _, b64 = data_uri.split(",", 1)
                    jpeg_bytes = base64.b64decode(b64)
                files.append(("image[]", ("ref.jpg", jpeg_bytes, "image/jpeg")))

            if files:
                form = {
                    "model":      cfg["model"],
                    "prompt":     final_prompt,
                    "size":       size,
                    "quality":    "low",
                    "moderation": "low",
                }
                logger.info("AiHubMix ImgGen  mode=img2img  refs=%d  prompt=%s",
                            len(files), final_prompt)
                _log_prompt(final_prompt)
                resp = await _post_with_retry(
                    client,
                    f"{base_url}/images/edits",
                    headers={"Authorization": f"Bearer {key}"},
                    data=form,
                    files=files,
                )
                resp.raise_for_status()
                return await _aihubmix_parse_response(resp.json())
            # 所有参考图转换失败时降级为文生图
            logger.warning("AiHubMix all refs failed, falling back to txt2img")

        # ── 无参考图（或降级）：/images/generations (json) ────────────────────
        logger.info("AiHubMix ImgGen  mode=txt2img  model=%s  prompt=%s",
                    cfg["model"], final_prompt)
        _log_prompt(final_prompt)
        resp = await _post_with_retry(
            client,
            f"{base_url}/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model":      cfg["model"],
                "prompt":     final_prompt,
                "size":       size,
                "quality":    "low",
                "moderation": "low",
                "n":          1,
            },
        )
        resp.raise_for_status()
        return await _aihubmix_parse_response(resp.json())

    except httpx.HTTPStatusError as e:
        body = e.response.text[:800] if e.response else ""
        logger.error("AiHubMix ImgGen  HTTP %d  body=%s", e.response.status_code, body)
        raise
    except Exception as e:
        logger.error("AiHubMix ImgGen  FAIL  type=%s  err=%r", type(e).__name__, e)
        raise
    finally:
        await client.aclose()


async def generate(
    prompt: str,
    size: str = "1024x1024",
    reference_images: list[str] | None = None,
) -> str:
    cfg = get_img_config()
    api_type = cfg.get("api_type", "agnes-image")

    # 按连接类型限制参考图数量
    if reference_images:
        if api_type == "agnes-image":
            reference_images = reference_images[:3]
        elif api_type == "gemini":
            reference_images = reference_images[:9]
        elif api_type == "openai-image":
            reference_images = reference_images[:16]

    if api_type == "gemini":
        return await _generate_gemini(cfg, prompt, reference_images, size=size)

    if api_type == "openai-image":
        return await _generate_aihubmix(cfg, prompt, reference_images, size=size)

    # Agnes（agnes-image：extra_body.image 流派）
    key = cfg["key"]
    payload: dict = {"model": cfg["model"], "prompt": prompt, "size": size}
    if reference_images:
        converted = []
        for r in reference_images:
            data_uri = await _ref_to_base64(r)
            if data_uri:
                converted.append(data_uri)
        if converted:
            payload["extra_body"] = {"image": converted, "response_format": "url"}
            payload["tags"] = ["img2img"]

    mode = "img2img" if reference_images else "txt2img"
    n_refs = len(payload.get("extra_body", {}).get("image", []))
    logger.info("Agnes ImgGen  mode=%s  refs=%d  size=%s  prompt=%s",
                mode, n_refs, size, prompt)
    _log_prompt(prompt)
    try:
        resp = await get_client().post(
            f"{cfg['base_url']}/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=None,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data["data"][0]["url"]
        logger.info("Agnes ImgGen  OK  url=%s…", url[:60])
        return url
    except httpx.HTTPStatusError as e:
        body = e.response.text[:800] if e.response else ""
        logger.error("Agnes ImgGen  HTTP %d  body=%s", e.response.status_code, body)
        raise
    except Exception as e:
        logger.error("Agnes ImgGen  FAIL  type=%s  err=%r", type(e).__name__, e)
        raise
