import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "instance", "database.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Add the two new columns if they don't already exist
existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(service_areas)")]

if "created_by_id" not in existing_cols:
    cur.execute("ALTER TABLE service_areas ADD COLUMN created_by_id INTEGER")
    print("Added created_by_id column.")
else:
    print("created_by_id already exists.")

if "created_by_role" not in existing_cols:
    cur.execute("ALTER TABLE service_areas ADD COLUMN created_by_role VARCHAR(20)")
    print("Added created_by_role column.")
else:
    print("created_by_role already exists.")

conn.commit()
conn.close()
print("Done.")