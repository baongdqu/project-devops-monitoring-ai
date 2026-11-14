import aiosqlite
try:
    from backend.config import settings
except ImportError:
    from app_ai_telegram.backend.config import settings

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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            message_id TEXT,
            eval_type TEXT,
            score REAL,
            feedback_text TEXT,
            flags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        cursor = await db.execute(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (thread_id, role, content)
        )
        await db.commit()
        return cursor.lastrowid


async def save_evaluation(thread_id: str, message_id: str, eval_type: str, score: float, feedback_text: str = "", flags: str = ""):
    """Lưu kết quả đánh giá (Human Feedback hoặc Automated LLM Evals) vào cơ sở dữ liệu."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO evaluations (thread_id, message_id, eval_type, score, feedback_text, flags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (thread_id, str(message_id), eval_type, score, feedback_text, flags)
        )
        await db.commit()


async def get_eval_summary():
    """Lấy tổng hợp chỉ số đánh giá (Evaluation Summary) phục vụ Observability."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("""
            SELECT 
                COUNT(*) as total_evals,
                AVG(score) as avg_score,
                SUM(CASE WHEN score >= 4.0 OR feedback_text = 'good' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN score < 3.0 OR feedback_text = 'bad' THEN 1 ELSE 0 END) as negative_count
            FROM evaluations
        """) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "total_evals": row[0] or 0,
                    "avg_score": round(row[1] or 0.0, 2),
                    "positive_count": row[2] or 0,
                    "negative_count": row[3] or 0
                }
            return {"total_evals": 0, "avg_score": 0.0, "positive_count": 0, "negative_count": 0}
