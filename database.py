import aiosqlite
import os
from config import DB_PATH, SESSIONS_DIR

async def init_db():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned INTEGER DEFAULT 0,
                last_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                session_file TEXT,
                two_fa_password TEXT,
                tronaccs_item_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                tronaccs_api_key TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                channel_url TEXT NOT NULL,
                title TEXT
            )
        """)
        # Миграция: добавляем is_banned если таблица уже существовала
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.commit()

# ── Аккаунты ──────────────────────────────────────────────

async def add_account(user_id: int, phone: str, session_file: str = None, two_fa: str = None, item_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO accounts (user_id, phone, session_file, two_fa_password, tronaccs_item_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, phone, session_file, two_fa, item_id)
        )
        await db.commit()

async def get_accounts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE user_id=? AND status='active'", (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_account(account_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE id=? AND user_id=?", (account_id, user_id)
        ) as cursor:
            return await cursor.fetchone()

async def delete_account(account_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE accounts SET status='deleted' WHERE id=? AND user_id=?", (account_id, user_id)
        )
        await db.commit()

async def update_session(account_id: int, session_file: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET session_file=? WHERE id=?", (session_file, account_id))
        await db.commit()

async def get_all_accounts(limit: int = 50, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE status='active' ORDER BY added_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            return await cursor.fetchall()

async def get_accounts_by_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE user_id=? AND status='active'", (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_account_admin(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE id=?", (account_id,)
        ) as cursor:
            return await cursor.fetchone()

# ── Пользователи ──────────────────────────────────────────

async def register_user(user_id: int, username: str = None, first_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, first_name, last_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET last_at=CURRENT_TIMESTAMP,
               username=excluded.username, first_name=excluded.first_name""",
            (user_id, username, first_name)
        )
        await db.commit()

async def get_all_users(limit: int = 20, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY last_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cursor:
            return await cursor.fetchall()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE last_at >= datetime('now', '-7 days')"
        ) as c:
            weekly = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE last_at >= datetime('now', '-1 day')"
        ) as c:
            daily = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM accounts WHERE status='active'") as c:
            accs = (await c.fetchone())[0]
    return {"total": total, "weekly": weekly, "daily": daily, "accounts": accs}

# ── API ключ ──────────────────────────────────────────────

async def save_api_key(user_id: int, api_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (user_id, tronaccs_api_key) VALUES (?, ?)",
            (user_id, api_key)
        )
        await db.commit()

async def get_api_key(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT tronaccs_api_key FROM settings WHERE user_id=?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ── Настройки бота (баннер и т.д.) ───────────────────────

async def set_bot_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()

async def get_bot_setting(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key=?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ── Обязательные каналы ───────────────────────────────────

async def add_required_channel(channel_id: str, channel_url: str, title: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO required_channels (channel_id, channel_url, title) VALUES (?, ?, ?)",
            (channel_id, channel_url, title)
        )
        await db.commit()

async def get_required_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM required_channels") as cursor:
            return await cursor.fetchall()

async def delete_required_channel(ch_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM required_channels WHERE id=?", (ch_id,))
        await db.commit()
