# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（macOS 版）—— 产出单文件可执行 GalGame。

与 galgame.spec（Windows）唯一区别：不设置 .ico 图标（macOS 用 .icns，
未签名分发场景下省略图标更省事），其余资源/依赖收集完全一致。

构建（在 macOS / Apple Silicon 上）：
    pip install -r requirements-build.txt
    cd frontend && npm ci && npm run build && cd ..
    pyinstaller galgame-mac.spec

产物：dist/GalGame（onefile）。运行时数据写在可执行文件同级目录。
⚠️ 绝不打包根目录的 .env（含真实 Key）；只打包 .env.example 占位模板。
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

datas = [
    ("backend/sysprompt", "backend/sysprompt"),
    ("backend/assets",    "backend/assets"),
    ("frontend/dist",     "frontend/dist"),
    ("README.md",         "."),
    (".env.example",      "."),
]
binaries = []
hiddenimports = []

hiddenimports += [
    "aiosqlite",
    "aiofiles",
    "dotenv",
]

hiddenimports += [
    "main",
    "core.paths", "core.env_config", "core.prompt_loader",
    "core.llm", "core.image_gen", "core.memory", "core.lorebook_inj",
    "db.database",
    "tasks.worker",
    "api.plots", "api.sessions", "api.chat", "api.lorebook", "api.admin",
    "api.tasks", "api.snapshot", "api.characters", "api.image_chat", "api.galgame_card",
]

for pkg in ("Crypto", "uvicorn", "anyio"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

hiddenimports += collect_submodules("PIL")

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

datas += collect_data_files("certifi")
hiddenimports += ["certifi"]

a = Analysis(
    ["launcher.py"],
    pathex=["backend"],
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
    upx=False,                # macOS 上 UPX 常导致二进制无法运行，关闭
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
