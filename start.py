"""
python start.py   — 同时启动后端（uvicorn）和前端（vite）
Ctrl+C 退出，两个进程一起关
"""
import subprocess
import sys
import os
import signal
import time
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

procs = []

def stop(*_):
    for p in procs:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

print("启动后端 (port 17832)...")
backend_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "17832"],
    cwd=BACKEND,
)
procs.append(backend_proc)

print("启动前端 (port 15927)...")
npm = "npm.cmd" if sys.platform == "win32" else "npm"
frontend_proc = subprocess.Popen(
    [npm, "run", "dev"],
    cwd=FRONTEND,
)
procs.append(frontend_proc)

print("\n✓ 运行中 → http://localhost:15927")
print("Ctrl+C 退出\n")

# 等待任意一个进程退出
while True:
    for p in procs:
        if p.poll() is not None:
            print(f"进程意外退出（code {p.returncode}），关闭所有...")
            stop()
    time.sleep(1)
