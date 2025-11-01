import sqlite3
import os
from datetime import datetime
from .utils import sha256sum

DB_PATH = "logs/alerts.db"

def init_db():
    os.makedirs("logs", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ip_alerts (
            id INTEGER PRIMARY KEY,
            ip TEXT NOT NULL,
            hits INTEGER,
            paths TEXT,
            example_entry TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fs_events (
            id INTEGER PRIMARY KEY,
            event_type TEXT,
            path TEXT,
            user TEXT,
            size INTEGER,
            mtime REAL,
            checksum TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications_sent (
            id INTEGER PRIMARY KEY,
            target TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_ip_alert(ip, hits, paths, example_entry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO ip_alerts (ip, hits, paths, example_entry) VALUES (?, ?, ?, ?)",
        (ip, hits, ",".join(paths), example_entry)
    )
    conn.commit()
    conn.close()

def log_fs_event(event_type, path, size, mtime, checksum):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO fs_events (event_type, path, size, mtime, checksum) VALUES (?, ?, ?, ?, ?)",
        (event_type, path, size, mtime, checksum)
    )
    conn.commit()
    conn.close()

def log_notification(target, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notifications_sent (target, message) VALUES (?, ?)",
        (target, message)
    )
    conn.commit()
    conn.close()

def get_baseline():
    """Ambil snapshot terakhir dari semua path dan mtime/checksum."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT path, event_type, mtime, checksum FROM fs_events WHERE id IN (SELECT MAX(id) FROM fs_events GROUP BY path)")
    rows = c.fetchall()
    conn.close()
    baseline = {}
    for row in rows:
        path, etype, mtime, checksum = row
        baseline[path] = {"mtime": mtime, "checksum": checksum, "is_dir": etype == "dir_created"}
    return baseline

def save_baseline_snapshot(root_dir):
    """Simpan snapshot awal semua file & folder ke DB (sekali saja)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root_dir)
        if rel_dir == ".":
            rel_dir = ""
        # Simpan folder
        mtime = os.path.getmtime(dirpath)
        c.execute(
            "INSERT INTO fs_events (event_type, path, size, mtime, checksum) VALUES (?, ?, ?, ?, ?)",
            ("dir_created", rel_dir or ".", 0, mtime, None)
        )
        for f in filenames:
            filepath = os.path.join(dirpath, f)
            rel_path = os.path.relpath(filepath, root_dir)
            try:
                stat = os.stat(filepath)
                checksum = sha256sum(filepath)
                c.execute(
                    "INSERT INTO fs_events (event_type, path, size, mtime, checksum) VALUES (?, ?, ?, ?, ?)",
                    ("created", rel_path, stat.st_size, stat.st_mtime, checksum)
                )
            except (OSError, IOError):
                continue
    conn.commit()
    conn.close()