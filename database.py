import aiosqlite
import os
from config import DB_PATH, SESSIONS_DIR

async def init_db():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
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

async def add_account(phone: str, session_file: str = None, two_fa: str = None, item_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO accounts (phone, session_file, two_fa_password, tronaccs_item_id) VALUES (?, ?, ?, ?)",
            (phone, session_file, two_fa, item_id)
        )
        await db.commit()

async def get_accounts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts WHERE status='active'") as cursor:
            return await cursor.fetchall()

async def get_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)) as cursor:
            return await cursor.fetchone()

async def delete_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET status='deleted' WHERE id=?", (account_id,))
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
        async with db.execute("SELECT tronaccs_api_key FROM settings WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
