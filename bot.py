import sqlite3

conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    user_id INTEGER PRIMARY KEY,
    user_name TEXT,
    status TEXT DEFAULT 'new',
    note TEXT DEFAULT ''
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    sender TEXT,
    text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()


def get_or_create_client(user_id: int, user_name: str):
    cursor.execute("SELECT user_id FROM clients WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO clients (user_id, user_name) VALUES (?, ?)",
            (user_id, user_name)
        )
        conn.commit()


def get_clients():
    cursor.execute(
        "SELECT user_id, user_name, status FROM clients ORDER BY user_name"
    )
    return cursor.fetchall()


def get_client(user_id: int):
    cursor.execute(
        "SELECT user_name, status, note FROM clients WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()


def update_status(user_id: int, status: str):
    cursor.execute(
        "UPDATE clients SET status = ? WHERE user_id = ?",
        (status, user_id)
    )
    conn.commit()


def update_note(user_id: int, note: str):
    cursor.execute(
        "UPDATE clients SET note = ? WHERE user_id = ?",
        (note, user_id)
    )
    conn.commit()


def save_message(user_id: int, sender: str, text: str):
    cursor.execute(
        "INSERT INTO messages (user_id, sender, text) VALUES (?, ?, ?)",
        (user_id, sender, text)
    )
    conn.commit()


def get_history(user_id: int, limit: int = 20):
    cursor.execute(
        """
        SELECT sender, text
        FROM messages
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    return cursor.fetchall()[::-1]
