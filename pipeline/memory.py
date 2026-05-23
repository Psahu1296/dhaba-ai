import psycopg
from psycopg.rows import dict_row

_conn = None


async def init(database_url: str):
    global _conn
    _conn = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    await _conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_history (
            id      BIGSERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role    TEXT NOT NULL,
            content TEXT NOT NULL,
            ts      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await _conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ph_session ON pipeline_history(session_id, ts)"
    )


async def load(session_id: str, limit: int = 6) -> list[dict]:
    """Return last `limit` messages in chronological order."""
    async with _conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """SELECT role, content FROM pipeline_history
               WHERE session_id = %s ORDER BY ts DESC LIMIT %s""",
            (session_id, limit),
        )
        rows = await cur.fetchall()
    return list(reversed(rows))


async def save(session_id: str, user_msg: str, assistant_msg: str):
    async with _conn.cursor() as cur:
        await cur.executemany(
            "INSERT INTO pipeline_history (session_id, role, content) VALUES (%s, %s, %s)",
            [(session_id, "user", user_msg), (session_id, "assistant", assistant_msg)],
        )
