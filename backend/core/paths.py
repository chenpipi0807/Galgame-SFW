"""
统一路径解析 —— 区分「只读资源」与「可写用户数据」，兼容开发态与 PyInstaller 冻结态。

两类根目录：
- RESOURCE_ROOT：只读资源（sysprompt/*.md、README.md、frontend/dist）。
    冻结态 = PyInstaller 解压目录 sys._MEIPASS；开发态 = 项目根。
- USERDATA_ROOT：可写数据（galgame.db、data/uploads、data/logs、.env）。
    冻结态 = exe 所在目录（绿色便携版，用户拖到哪都能用）；开发态 = 项目根。

⚠️ 全项目所有路径都应从这里取，不要再写 Path(__file__).parent.parent...，
   否则冻结后会指向临时解压目录导致读写错位。
"""
import sys
from pathlib import Path

# 本文件位于 backend/core/paths.py，向上三级 = 项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_FROZEN = getattr(sys, "frozen", False)


def _resource_root() -> Path:
    """只读资源根：冻结态用 _MEIPASS，开发态用项目根。"""
    if _FROZEN:
        # PyInstaller 把 --add-data 的内容解压到 sys._MEIPASS
        return Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
    return _PROJECT_ROOT


def _userdata_root() -> Path:
    """可写数据根：冻结态用 exe 同级目录，开发态用项目根。"""
    if _FROZEN:
        return Path(sys.executable).resolve().parent
    return _PROJECT_ROOT


RESOURCE_ROOT = _resource_root()
USERDATA_ROOT = _userdata_root()


def ensure_dir(p: Path) -> Path:
    """确保目录存在并返回它（父目录一并创建）。"""
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── 常用派生路径（单一真相源）────────────────────────────────────────────────
# 可写数据
DATA_DIR    = USERDATA_ROOT / "data"
DB_PATH     = DATA_DIR / "galgame.db"
UPLOADS_DIR = DATA_DIR / "uploads"
LOGS_DIR    = DATA_DIR / "logs"
ENV_PATH    = USERDATA_ROOT / ".env"

# 只读资源
SYSPROMPT_DIR = RESOURCE_ROOT / "backend" / "sysprompt"
FRONTEND_DIST = RESOURCE_ROOT / "frontend" / "dist"
README_PATH   = RESOURCE_ROOT / "README.md"
ENV_EXAMPLE   = RESOURCE_ROOT / ".env.example"
BASE_CARD_PATH = RESOURCE_ROOT / "backend" / "assets" / "BASE.png"  # GG 卡默认卡面（无生成图时兜底）
