import asyncio
import logging
import time
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from contextlib import asynccontextmanager

from core.paths import LOGS_DIR, FRONTEND_DIST, ensure_dir
from db.database import init_db, close_db, UPLOADS_DIR
from tasks.worker import process_pending
from api.plots import router as plots_router
from api.sessions import router as sessions_router
from api.chat import router as chat_router
from api.lorebook import router as lorebook_router
from api.admin import router as admin_router
from api.tasks import router as tasks_router
from api.snapshot import router as snapshot_router
from api.characters import router as characters_router
from api.image_chat import router as image_chat_router
from api.galgame_card import router as galgame_card_router

_LOG_DIR = ensure_dir(LOGS_DIR)

_file_handler = RotatingFileHandler(
    _LOG_DIR / "galgame.log",
    maxBytes=10 * 1024 * 1024,   # 10 MB per file
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(name)-24s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# 把文件 handler 挂到 galgame.* 和 uvicorn.* 两棵子树
for _name in ("galgame", "uvicorn", "uvicorn.access", "uvicorn.error"):
    _lg = logging.getLogger(_name)
    _lg.addHandler(_file_handler)
    _lg.setLevel(logging.DEBUG)

logger = logging.getLogger("galgame")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from core import providers
    await providers.load_config()   # 加载/迁移 provider 连接配置到内存缓存
    task = asyncio.create_task(process_pending())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_db()


app = FastAPI(title="GalGame API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        logger.error("%-6s %-45s  ERROR  %.0fms  %s",
                     request.method, request.url.path, elapsed, exc)
        raise
    elapsed = (time.time() - start) * 1000
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(level, "%-6s %-45s  %d  %.0fms",
               request.method, request.url.path, response.status_code, elapsed)
    return response

app.include_router(plots_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(lorebook_router)
app.include_router(admin_router)
app.include_router(tasks_router)
app.include_router(snapshot_router)
app.include_router(characters_router)
app.include_router(image_chat_router)
app.include_router(galgame_card_router)

# 静态文件：用户上传的图片
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── 前端 SPA：FastAPI 同源直出已构建的 Vue 应用（打包后无 Vite dev server）──────
# 仅当构建产物存在时挂载（开发态若未 build 则跳过，仍用 Vite dev server）。
if FRONTEND_DIST.exists():
    # /assets/* 等带后缀的静态资源由 StaticFiles 提供
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    _SPA_INDEX = FRONTEND_DIST / "index.html"

    @app.get("/")
    async def _spa_root():
        return FileResponse(str(_SPA_INDEX))

    # SPA 回退：非 /api、非 /uploads 的路径都返回 index.html，
    # 让 vue-router(history 模式)的深链/刷新(/read/:id、/admin 等)不 404。
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # /api、/uploads 下的未知路径不应伪装成页面，返回真实 404 便于排查
        if full_path.startswith("api/") or full_path.startswith("uploads/"):
            return Response(status_code=404)
        # 真实存在的静态文件（如 favicon、gen_failed.png）直接返回
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_SPA_INDEX))
