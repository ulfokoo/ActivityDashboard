"""
One-time migration: adds password_reset_requested and password_reset_allowed
columns to the users table for the admin-approved password reset flow.

This connects directly to the SQLite file instead of importing app.py,
because create_app() seeds a default admin on startup, which queries the
users table (including these new columns) before the migration can run.
"""
import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(users)")
existing_columns = {row[1] for row in cur.fetchall()}

if "password_reset_requested" not in existing_columns:
    cur.execute("ALTER TABLE users ADD COLUMN password_reset_requested BOOLEAN NOT NULL DEFAULT 0")
    print("Added column: password_reset_requested")
else:
    print("Column already exists: password_reset_requested")

if "password_reset_allowed" not in existing_columns:
    cur.execute("ALTER TABLE users ADD COLUMN password_reset_allowed BOOLEAN NOT NULL DEFAULT 0")
    print("Added column: password_reset_allowed")
else:
    print("Column already exists: password_reset_allowed")

conn.commit()
conn.close()
print("Migration complete.")