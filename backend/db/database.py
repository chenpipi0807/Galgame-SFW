import aiosqlite
from core.paths import DB_PATH, UPLOADS_DIR

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        raise RuntimeError("数据库未初始化")
    return _db


async def init_db():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _create_tables()
    await _migrate()
    await _seed_defaults()
    await _db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


async def _create_tables():
    await _db.executescript("""
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL DEFAULT '',
    concept        TEXT NOT NULL DEFAULT '',
    vibe           TEXT NOT NULL DEFAULT '[]',
    opening        TEXT NOT NULL DEFAULT '',
    backstory      TEXT NOT NULL DEFAULT '',
    style_settings TEXT NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'draft',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS characters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id      INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    personality  TEXT NOT NULL DEFAULT '',
    image_prompt TEXT NOT NULL DEFAULT '',
    image_url    TEXT NOT NULL DEFAULT '',
    avatar_url   TEXT NOT NULL DEFAULT '',
    is_user      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lorebooks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lorebook_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    keywords    TEXT NOT NULL DEFAULT '[]',
    content     TEXT NOT NULL DEFAULT '',
    order_idx   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS plot_lorebooks (
    plot_id     INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    PRIMARY KEY (plot_id, lorebook_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id        INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    title          TEXT NOT NULL DEFAULT '新会话',
    current_scene  TEXT NOT NULL DEFAULT '',
    memory_summary TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    content      TEXT NOT NULL DEFAULT '',
    role         TEXT NOT NULL DEFAULT 'assistant',
    timestamp    TEXT NOT NULL DEFAULT (datetime('now')),
    metadata     TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}',
    status     TEXT NOT NULL DEFAULT 'pending',
    result_url TEXT NOT NULL DEFAULT '',
    error      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS character_evolution_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    session_id   INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    round        INTEGER NOT NULL DEFAULT 0,
    change       TEXT NOT NULL DEFAULT '',
    reason       TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 记忆快照：每次记忆更新存一份（带 round），撤回消息时回滚到对应轮次的快照
CREATE TABLE IF NOT EXISTS memory_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round          INTEGER NOT NULL DEFAULT 0,
    memory_summary TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
""")


async def _migrate():
    """给旧表增加新列（幂等）"""
    migrations = [
        "ALTER TABLE sessions ADD COLUMN bg_image_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE characters ADD COLUMN reference_image TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE characters ADD COLUMN image_style TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE characters ADD COLUMN first_mes TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE characters ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]'",
        # 角色性格/背景的累积演变层（随剧情发展由记忆系统写入，不覆盖原始 personality）
        "ALTER TABLE characters ADD COLUMN personality_evolved TEXT NOT NULL DEFAULT ''",
        # lorebook 条目所属轮次（仅动态"剧情演变"条目使用，>0；普通条目为 0，撤回不删）
        "ALTER TABLE lorebook_entries ADD COLUMN round INTEGER NOT NULL DEFAULT 0",
        # 清空旧式自由文本摘要，改用 JSON 槽位格式
        "UPDATE sessions SET memory_summary='{}' WHERE memory_summary NOT LIKE '{%'",
    ]
    for sql in migrations:
        try:
            await _db.execute(sql)
        except Exception:
            pass  # 列已存在时忽略
    await _db.commit()


async def _seed_defaults():
    """初始化默认设置。
    说明：provider「连接」配置（含自填的第三方 Key）存于 settings.providers_config，
       由 core/providers.py 管理。Agnes 内置 Key 仅硬编码在代码、不入库。
       ⚠️ /admin/export 会导出整库 —— 若用户填了自己的三方 Key，导出文件会含该 Key，
          分享前需自行注意（GG 卡分享不含 Key，是安全的）。
    """
    await _db.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('user_avatar', '')"
    )
    await _db.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('user_gender', '')"
    )
    await _db.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('narrative_mode', 'classic')"
    )
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)