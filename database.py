"""
طبقة قاعدة البيانات - بوت المكتبة
كل قسم ومادة إلهم رقم فريد (id) بغض النظر عن الاسم الظاهر (display_name).
هيك بنقدر نكرر نفس الاسم بأكتر من مكان بدون أي مشكلة.
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "library.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                content TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


# ---------- categories ----------

def add_category(name, parent_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, parent_id) VALUES (?, ?)",
            (name, parent_id),
        )
        conn.commit()
        return cur.lastrowid


def get_categories(parent_id=None):
    with get_conn() as conn:
        if parent_id is None:
            return conn.execute(
                "SELECT * FROM categories WHERE parent_id IS NULL ORDER BY id"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM categories WHERE parent_id = ? ORDER BY id", (parent_id,)
        ).fetchall()


def get_category(category_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()


def get_all_categories():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM categories ORDER BY id").fetchall()


def delete_category(category_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()


# ---------- subjects (buttons) ----------

def add_subject(display_name, category_id, content=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO subjects (display_name, category_id, content) VALUES (?, ?, ?)",
            (display_name, category_id, content),
        )
        conn.commit()
        return cur.lastrowid


def get_subjects(category_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subjects WHERE category_id = ? ORDER BY id", (category_id,)
        ).fetchall()


def get_subject(subject_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()


def update_subject_name(subject_id, new_name):
    with get_conn() as conn:
        conn.execute(
            "UPDATE subjects SET display_name = ? WHERE id = ?", (new_name, subject_id)
        )
        conn.commit()


def update_subject_content(subject_id, new_content):
    with get_conn() as conn:
        conn.execute(
            "UPDATE subjects SET content = ? WHERE id = ?", (new_content, subject_id)
        )
        conn.commit()


def delete_subject(subject_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()
