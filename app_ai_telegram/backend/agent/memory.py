import aiosqlite
from backend.config import settings

db_path = settings.DATA_DIR / "memory.db"

async def init_chat_db():
    """Khởi tạo database SQLite cho luồng hội thoại và tin nhắn."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
        )
        """)
        await db.commit()

async def create_thread(thread_id: str, title: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO threads (id, title) VALUES (?, ?)",
            (thread_id, title)
        )
        await db.commit()

async def get_messages(thread_id: str):
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT role, content FROM messages WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in rows]

async def save_message(thread_id: str, role: str, content: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (thread_id, role, content)
        )
        await db.commit()
