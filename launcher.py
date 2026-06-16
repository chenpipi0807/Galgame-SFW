"""
GalGame 启动器 —— 打包成 exe 后的入口。

职责：
  1. 把内置 backend 目录加入 sys.path（冻结态从 _MEIPASS，开发态从项目根）
  2. 首次运行：若 exe 同级没有 .env，则从内置 .env.example 拷一份（仅占位符，安全）
  3. 进程内启动 uvicorn（同源直出前端 + API），仅监听 127.0.0.1
  4. 等端口就绪后用默认浏览器打开，无需用户做任何配置

开发态也可直接 `python launcher.py` 单进程运行（需先 `cd frontend && npm run build` 产出 dist）。
"""
import sys
import os
import shutil
import threading
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 17832

_FROZEN = getattr(sys, "frozen", False)
_RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
_USERDATA_ROOT = Path(sys.executable).resolve().parent if _FROZEN else Path(__file__).resolve().parent

# 让 `from main import app` 与 `from db.database ...` 等顶层包导入可用
_BACKEND_DIR = _RESOURCE_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))


def _seed_env_if_missing():
    """首次运行：exe 同级无 .env 时，从内置 .env.example 拷一份占位符模板。
    用户随后在「管理后台 → API 配置」填入自己的 Key 即写回此 .env。
    """
    env_path = _USERDATA_ROOT / ".env"
    if env_path.exists():
        return
    example = _RESOURCE_ROOT / ".env.example"
    try:
        if example.exists():
            shutil.copyfile(example, env_path)
            print(f"[launcher] 已创建 .env 模板: {env_path}（请在应用内填写 API Key）")
        else:
            env_path.touch()
    except Exception as e:
        print(f"[launcher] 创建 .env 失败（可手动在应用内配置）: {e}")


def _open_browser_when_ready():
    """轮询健康检查，就绪后打开浏览器。"""
    import urllib.request
    url = f"http://{HOST}:{PORT}/"
    health = f"http://{HOST}:{PORT}/api/health"
    for _ in range(60):  # 最多等 ~30s
        try:
            with urllib.request.urlopen(health, timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    try:
        webbrowser.open(url)
        print(f"[launcher] 已在浏览器打开 {url}")
    except Exception:
        print(f"[launcher] 请手动在浏览器打开 {url}")


def main():
    _seed_env_if_missing()

    # 延迟导入，确保 sys.path 与 .env 已就绪
    import uvicorn
    from main import app  # backend/main.py

    print(f"[launcher] GalGame 启动中 → http://{HOST}:{PORT}")
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    # 直接传 app 对象（不要用 "main:app" 字符串，冻结态字符串导入会失败）
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
