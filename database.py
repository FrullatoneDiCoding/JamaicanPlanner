"""
Gestione del database SQLite per JamaicaPlanner.

Tabelle:
- users: membri del gruppo, stato di approvazione
- presence: presenze segnate sul calendario (utente + data)
"""
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    requested_at TEXT DEFAULT (datetime('now')),
    decided_at  TEXT
);

CREATE TABLE IF NOT EXISTS presence (
    user_id  INTEGER NOT NULL,
    day      TEXT NOT NULL,  -- formato YYYY-MM-DD
    PRIMARY KEY (user_id, day),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- Utenti / approvazioni ----------

def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def request_access(user_id: int, username: Optional[str], first_name: Optional[str]) -> str:
    """Registra (o ritrova) una richiesta di accesso. Ritorna lo status attuale."""
    existing = get_user(user_id)
    if existing:
        return existing["status"]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, status) VALUES (?, ?, ?, 'pending')",
            (user_id, username, first_name),
        )
    return "pending"


def set_status(user_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET status = ?, decided_at = datetime('now') WHERE user_id = ?",
            (status, user_id),
        )


def is_approved(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["status"] == "approved")


def list_approved() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE status = 'approved' ORDER BY first_name"
        ).fetchall()


def list_pending() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE status = 'pending' ORDER BY requested_at"
        ).fetchall()


# ---------- Presenze ----------

def toggle_presence(user_id: int, day: date) -> bool:
    """Inverte la presenza per un utente in un dato giorno.
    Ritorna True se ora è presente, False se è stata rimossa."""
    day_str = day.isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM presence WHERE user_id = ? AND day = ?", (user_id, day_str)
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM presence WHERE user_id = ? AND day = ?", (user_id, day_str)
            )
            return False
        else:
            conn.execute(
                "INSERT INTO presence (user_id, day) VALUES (?, ?)", (user_id, day_str)
            )
            return True


def get_presence_for_month(year: int, month: int) -> dict[str, list[int]]:
    """Ritorna {giorno_iso: [user_id, ...]} per tutte le presenze nel mese."""
    prefix = f"{year:04d}-{month:02d}-"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT day, user_id FROM presence WHERE day LIKE ? ORDER BY day",
            (prefix + "%",),
        ).fetchall()
    result: dict[str, list[int]] = {}
    for row in rows:
        result.setdefault(row["day"], []).append(row["user_id"])
    return result


def get_user_presence_days(user_id: int, year: int, month: int) -> set[str]:
    prefix = f"{year:04d}-{month:02d}-"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT day FROM presence WHERE user_id = ? AND day LIKE ?",
            (user_id, prefix + "%"),
        ).fetchall()
    return {row["day"] for row in rows}


def get_attendees_for_day(day: date) -> list[sqlite3.Row]:
    day_str = day.isoformat()
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name
            FROM presence p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.day = ?
            ORDER BY u.first_name
            """,
            (day_str,),
        ).fetchall()
