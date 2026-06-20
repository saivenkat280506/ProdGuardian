import hashlib
import json
import sqlite3
from pathlib import Path

CACHE_DIR = Path.home() / ".prodguardian_cache"
CACHE_DIR.mkdir(exist_ok=True)
DB_PATH = CACHE_DIR / "cache.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ast_cache (
            file_hash TEXT PRIMARY KEY,
            file_path TEXT,
            issues TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    return conn


def get_cached_ast(file_path: Path):
    file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
    conn = get_db()
    cur = conn.execute(
        "SELECT issues FROM ast_cache WHERE file_hash = ?", (file_hash,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def store_ast(file_path: Path, data: dict):
    file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO ast_cache (file_hash, file_path, issues) VALUES (?, ?, ?)",
        (file_hash, str(file_path), json.dumps(data)),
    )
    conn.commit()
    conn.close()
