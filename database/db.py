import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash


# ------------------------------------------------------------------ #
# Connection                                                          #
# ------------------------------------------------------------------ #

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


def get_db():
    """Return a connection with row access by name and foreign keys enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

def init_db():
    """Create both tables if they are missing. Safe to call repeatedly."""
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------ #
# Seed data                                                           #
# ------------------------------------------------------------------ #

DEMO_EXPENSES = (
    ("Food", 450.00, "Lunch with team"),
    ("Food", 1280.00, "Groceries"),
    ("Transport", 320.00, "Metro card recharge"),
    ("Bills", 2450.00, "Electricity bill"),
    ("Health", 899.00, "Pharmacy"),
    ("Entertainment", 649.00, "Movie tickets"),
    ("Shopping", 3199.00, "Running shoes"),
    ("Other", 500.00, "Gift for a friend"),
)


def seed_db():
    """Insert demo data once — does nothing if users already has rows."""
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    today = date.today()
    for index, (category, amount, description) in enumerate(DEMO_EXPENSES):
        # Days 2, 4, 6 … of the current month, never dated past today.
        day = min(2 * (index + 1), today.day)
        spent_on = date(today.year, today.month, day).isoformat()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, spent_on, description),
        )

    conn.commit()
    conn.close()
