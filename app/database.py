import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "kr3.sqlite3"))


def get_db_connection() -> sqlite3.Connection:
    """Return a raw sqlite3 connection. SQLAlchemy is intentionally not used."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create all tables if they do not exist."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def insert_user_plain(username: str, password: str) -> int:
    """Task 8.1 requires storing username/password in SQLite without SQLAlchemy."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def create_todo(title: str, description: str) -> dict[str, Any]:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO todos (title, description, completed)
            VALUES (?, ?, 0)
            """,
            (title, description),
        )
        connection.commit()
        todo_id = int(cursor.lastrowid)
        return get_todo(todo_id)
    finally:
        connection.close()


def get_todo(todo_id: int) -> dict[str, Any] | None:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, title, description, completed FROM todos WHERE id = ?",
            (todo_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "completed": bool(row["completed"]),
        }
    finally:
        connection.close()


def update_todo(todo_id: int, title: str, description: str, completed: bool) -> dict[str, Any] | None:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE todos
            SET title = ?, description = ?, completed = ?
            WHERE id = ?
            """,
            (title, description, int(completed), todo_id),
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None
        return get_todo(todo_id)
    finally:
        connection.close()


def delete_todo(todo_id: int) -> bool:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
