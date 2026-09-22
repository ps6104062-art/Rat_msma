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
        await db.commit()

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

async def get_all_users(limit: int = 50, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY last_at DESC LIMIT ? OFFSET ?", (limit, offset)
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
    """Получить аккаунт без проверки user_id (для админа)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE id=?", (account_id,)
        ) as cursor:
            return await cursor.fetchone()
