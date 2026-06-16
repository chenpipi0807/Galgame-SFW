# GalGame 桌面 EXE 打包计划

> 目标：打包成单个 Windows `.exe`，别人双击运行、首次填入自己的 API Key 即可游玩。
> 技术路线：PyInstaller 冻结后端 + FastAPI 直出已构建前端 + pywebview 原生窗口外壳 + GitHub Actions 自动构建。
>
> 本文件是工作清单，逐项执行、勾选。

---

## ⚠️ 三大最高风险（先知道，避免白干）

1. **路径冻结失效（#1 风险）**：所有路径都用 `Path(__file__).parent...` 推导，PyInstaller 冻结后 `__file__` 指向临时解压目录 `_MEIPASS`，导致：数据库/上传/日志/.env 写进临时目录、退出即丢；sysprompt/README 等只读资源读不到。**必须先做阶段 A。**
2. **真实 Key 泄露**：项目根 `.env` 里有你的真实 key（Agnes/DeepSeek/Gemini/AIHubMix）。**绝不能把 `.env` 打进 exe**，否则每个用户都拿到你的 key。→ 这些 key 建议尽快轮换。
3. **Key 被复制进数据库**：[database.py:156-165](backend/db/database.py#L156) 把 key 写进了 `galgame.db` 的 settings 表，而 `/admin/export` 会导出整个 db → 二次泄露。需移除。

---

## 阶段 A — 路径改造（资源 vs 用户数据，最高优先级）

- [ ] **A1. 新建 `backend/core/paths.py`** —— 统一路径解析单一真相源
  - `RESOURCE_ROOT`：只读资源根。frozen 时 = `Path(sys._MEIPASS)`，否则 = 项目根
  - `USERDATA_ROOT`：可写数据根。frozen 时 = `Path(sys.executable).parent`（exe 同级），否则 = 项目根
  - 用 `getattr(sys, 'frozen', False)` 判定
  - 导出 `ensure_dir()` 辅助
  - *为何*：全仓零处 frozen 处理；集中化可消除现有重复定义（UPLOADS_DIR 两处、SYSPROMPT_DIR 两处）和目录深度不一致

- [ ] **A2. `.env` 路径 → 可写目录**
  - [env_config.py:8](backend/core/env_config.py#L8) `ENV_PATH` → `USERDATA_ROOT / '.env'`
  - [database.py:160](backend/db/database.py#L160) 的 `load_dotenv(...)` 同步指向同一路径
  - *为何*：首屏填 key 的唯一持久化点；冻结后 set_key 写临时目录会丢

- [ ] **A3. SQLite 路径 → 可写目录**
  - [database.py:5](backend/db/database.py#L5) `DB_PATH` → `USERDATA_ROOT / 'data' / 'galgame.db'`
  - WAL/SHM 随之落同一目录；保留 `.parent.mkdir`

- [ ] **A4. uploads 路径 → 可写目录 + 去重**
  - [database.py:122](backend/db/database.py#L122) `UPLOADS_DIR` → `USERDATA_ROOT/'data'/'uploads'`
  - 删 [image_gen.py:30](backend/core/image_gen.py#L30) 重复定义，改为 import 同一个
  - *为何*：两处不一致会导致生图写入处与 `/uploads` 挂载处不符 → 图片 404

- [ ] **A5. 日志目录 → 可写目录 + 统一**
  - [main.py:25](backend/main.py#L25) `_LOG_DIR`（注意当前用 `.parent.parent`）和 [image_gen.py:16](backend/core/image_gen.py#L16) `_PROMPT_LOG_DIR`（用 `.parent.parent.parent`，当前其实指向不同目录）统一为 `USERDATA_ROOT/'data'/'logs'`
  - *为何*：`RotatingFileHandler` 在 import 期就打开文件，目录只读会导致启动前崩溃

- [ ] **A6. 只读资源路径 → `RESOURCE_ROOT`**
  - [prompt_loader.py:4](backend/core/prompt_loader.py#L4) `SYSPROMPT_DIR` → `RESOURCE_ROOT/'backend'/'sysprompt'`
  - 删 [admin.py:16](backend/api/admin.py#L16) 重复 SYSPROMPT_DIR，改 import
  - [admin.py:17](backend/api/admin.py#L17) `README_PATH` → `RESOURCE_ROOT/'README.md'`
  - *为何*：`list_modes()` 靠遍历真实目录树发现模式，必须以真实目录形式打包

- [ ] **A7. 处理 prompt 编辑器与只读资源冲突**
  - prompt_loader.save / admin PUT /prompts 会写回 SYSPROMPT_DIR（冻结后只读）
  - **方案（先做省事版）**：冻结时禁用编辑（save 抛 503 + 前端隐藏入口）
  - 进阶版：写到 `USERDATA_ROOT/'sysprompt'` 覆盖副本，load 时先查用户副本再回落

---

## 阶段 B — 前后端合并（FastAPI 直出前端）

- [ ] **B1. main.py 挂载前端构建产物 + SPA 回退**
  - 在所有 `/api` 路由 include 之后、`/uploads` 挂载之后：
  - `FRONTEND_DIST = RESOURCE_ROOT/'frontend'/'dist'`
  - `app.mount('/', StaticFiles(directory=str(FRONTEND_DIST), html=True), name='spa')`
  - 加 catch-all `@app.get('/{full_path:path}')` 返回 `FileResponse(index.html)`（注册在所有 API 路由之后）
  - *为何*：后端当前只挂 `/uploads`，无前端服务；SPA 用 `createWebHistory`，深链 `/read/:id`、`/admin` 硬刷新会 404

- [x] **B2. 前端无需改动（已验证）**
  - ✅ 所有 fetch 已是相对 `/api`、`/uploads`（plotStore.js `const API=(p)=>\`/api${p}\``）
  - ✅ 无硬编码 host/port（仅 vite proxy 的 dev 目标，打包后失效）
  - ✅ dist 用根绝对资源路径 `/assets/...`，正好配合根挂载
  - ✅ 后端返回的图片 URL 也是相对 `/uploads/...`

- [ ] **B3.（可选）离线字体**
  - dist/index.html 从 Google Fonts CDN 加载字体，离线静默回退系统字体
  - 完全离线需自托管 Noto 字体；否则接受回退（非阻断）

---

## 阶段 C — 桌面外壳（pywebview + 进程内 uvicorn）

- [ ] **C1. 新建冻结入口 `desktop.py`（仓库根，PyInstaller 入口）**
  - 把 backend 目录加入 `sys.path`（frozen 时 = `RESOURCE_ROOT/'backend'`）
  - `from main import app`
  - 后台线程 `uvicorn.run(app, host='127.0.0.1', port=17832)` —— **直接传 app 对象，不要用 'main:app' 字符串**
  - 主线程等端口就绪 → `webview.create_window('GalGame', 'http://127.0.0.1:17832')` + `webview.start()`
  - *为何*：main.py 无 `__main__` 块、无 uvicorn.run；冻结后 sys.executable 是 exe 本体，CLI 不可用

- [ ] **C2. start.py 降级为仅 dev 用**（生产改用 desktop.py，无需删除）

- [ ] **C3. 绑定 127.0.0.1 + 收紧 CORS**
  - desktop.py 用 host `127.0.0.1`（非 0.0.0.0）
  - 可选收紧 [main.py:70-75](backend/main.py#L70) 的 `allow_origins=['*']`

- [ ] **C4. 依赖补充**
  - `backend/requirements.txt` 加 `pywebview`（Win 走 Edge WebView2，多数 Win10/11 内置）
  - 新建 `requirements-build.txt` 加 `pyinstaller`

---

## 阶段 D — 首次运行填 Key

- [ ] **D1. 首启检测无 key → 引导到配置页**
  - 前端启动调 `GET /api/admin/providers`，若所有 `*_has_key` 全 false → 跳 `/admin`（或新建 `/setup`）
  - *为何*：无 key 时应用能开但生成全部静默失败；现有 AdminView「API 配置」tab 已能读写全部 key，可直接复用

- [ ] **D2. 首启无 .env 也能写入**
  - desktop.py 启动时若 `USERDATA_ROOT/.env` 不存在，从打包的 `.env.example`（仅占位符）拷一份种子
  - env_config.write() 的 set_key 在文件不存在时会自动创建（前提 ENV_PATH 可写，A2 已修）

- [ ] **D3. 移除 key 复制进 DB 的逻辑（泄密面）**
  - 删 [database.py:156-165](backend/db/database.py#L156) `_seed_defaults` 里 load_dotenv + 写 `settings.api_key` 的部分
  - 检查 [database.py:144-153](backend/db/database.py#L144) `_PROVIDER_DEFAULTS` 镜像 provider 配置的行
  - *为何*：key 被写进 db 且 /admin/export 会导出 db → 泄露

---

## 阶段 E — PyInstaller 配置

- [ ] **E1. 编写 `galgame.spec`**
  - entry = `desktop.py`
  - `datas`：`('backend/sysprompt','backend/sysprompt')`、`('README.md','.')`、`('frontend/dist','frontend/dist')`、`('.env.example','.')`
  - **绝不包含 `.env`**
- [ ] **E2. hidden imports / collect**（冻结常漏的依赖）
  - `--collect-all Crypto`（pycryptodome C 扩展，否则 GG 卡加解密崩）
  - `--collect-all uvicorn` + h11/httptools/websockets/anyio（uvicorn 动态导入子模块）
  - `--collect-submodules PIL`（Pillow 图像插件动态加载）
  - `--collect-data certifi`（httpx 出站 TLS 的 CA bundle，否则所有 HTTPS API 调用失败）
- [ ] **E3. 本地试打包验证**（关键回归项）
  - 跑一次冻结 exe，验证：填 key 能持久化、生图能写入并显示、GG 卡导入导出、prompt 读取、深链刷新

---

## 阶段 F — GitHub Actions 自动构建

- [ ] **F1. 新建 `.github/workflows/build-exe.yml`**
  - `runs-on: windows-latest`
  - 步骤：checkout → setup-python → setup-node → `cd frontend && npm ci && npm run build` → `pip install -r requirements.txt -r requirements-build.txt` → `pyinstaller galgame.spec`
  - 产物：上传为 artifact，或 push tag 时挂到 Release
- [ ] **F2. 触发方式**：push tag（如 `v*`）触发，或手动 `workflow_dispatch`
- [ ] **F3. 验证私库额度**：私有仓库 Actions 免费额度足够（Windows runner 约 1000 等效分钟/月，单次构建 5-10 分钟）

---

## 执行顺序与工作量

**严格按 A → B → C → D → E → F 顺序**（A 是其余一切的地基）。

| 阶段 | 工作量 | 说明 |
|---|---|---|
| A 路径改造 | 大 | 地基，最易翻车，必须最先做并本地验证 |
| B 前后端合并 | 小 | 前端无需改，仅后端加挂载 |
| C 桌面外壳 | 中 | 新建 desktop.py + 进程内启动 |
| D 填 key onboarding | 中 | 复用现有 admin 配置页 |
| E PyInstaller | 中 | spec + 依赖 hook，需多轮试打 |
| F Actions | 小 | 一个 yml |

> 经验值：有经验者 2-3 天出第一版可分发 exe，主要时间在 A 和 E 的反复验证。
