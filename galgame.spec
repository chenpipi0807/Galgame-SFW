# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 —— 产出单文件 GalGame.exe。

构建：
    pip install -r requirements-build.txt
    cd frontend && npm ci && npm run build && cd ..
    pyinstaller galgame.spec

产物：dist/GalGame.exe（onefile）。运行时数据写在 exe 同级目录。
⚠️ 绝不打包根目录的 .env（含真实 Key）；只打包 .env.example 占位模板。
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# 只读资源：解压到 _MEIPASS 后，backend/core/paths.py 以 RESOURCE_ROOT 读取
datas = [
    ("backend/sysprompt", "backend/sysprompt"),   # classic 提示词 .md（全年龄向）
    ("backend/assets",    "backend/assets"),       # GG 卡默认卡面 BASE.png
    ("frontend/dist",     "frontend/dist"),        # 已构建前端
    ("README.md",         "."),                    # 应用内帮助页读取
    (".env.example",      "."),                    # 首启拷贝为 .env 的占位模板
]
binaries = []
hiddenimports = []

# 后端纯 python 依赖（确保进入依赖图）
hiddenimports += [
    "aiosqlite",
    "aiofiles",
    "dotenv",
]

# 后端自身模块（launcher 通过 `from main import app` 间接导入，显式列出最稳妥）
hiddenimports += [
    "main",
    "core.paths", "core.env_config", "core.prompt_loader",
    "core.llm", "core.image_gen", "core.memory", "core.lorebook_inj",
    "db.database",
    "tasks.worker",
    "api.plots", "api.sessions", "api.chat", "api.lorebook", "api.admin",
    "api.tasks", "api.snapshot", "api.characters", "api.image_chat", "api.galgame_card",
]

# 易被漏收的依赖：完整收集
for pkg in ("Crypto", "uvicorn", "anyio"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# Pillow 图像插件动态加载
hiddenimports += collect_submodules("PIL")

# uvicorn[standard] 动态按名导入的协议/循环实现
hiddenimports += [
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "h11",
    "httptools",
    "websockets",
    "websockets.legacy",
]

# httpx 出站 TLS 的 CA 证书
datas += collect_data_files("certifi")
hiddenimports += ["certifi"]

a = Analysis(
    ["launcher.py"],
    pathex=["backend"],          # 让 from main import app / from db.database 顶层包导入可解析
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GalGame",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,            # 保留控制台便于查看启动日志/排错；稳定后可改 False
    disable_windowed_traceback=False,
    icon="frontend/public/favicon.ico",   # exe 文件图标（与浏览器标签一致的紫色 G）
)
