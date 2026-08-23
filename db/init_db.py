"""Initialize Vellora database and Final Project state tables."""
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "vellora_therapeutics.db"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"

STATE_SQL = """
CREATE TABLE IF NOT EXISTS state_runs (
    run_id TEXT PRIMARY KEY,
    graph_name TEXT NOT NULL,
    status TEXT NOT NULL,
    current_state TEXT NOT NULL,
    state_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    run_id TEXT,
    state_data TEXT NOT NULL,
    current_state TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES state_runs(run_id)
);
CREATE TABLE IF NOT EXISTS hitl_tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT,
    checkpoint_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL,
    state_data TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT,
    decision TEXT,
    FOREIGN KEY(run_id) REFERENCES state_runs(run_id)
);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    run_id TEXT,
    checkpoint_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    error TEXT NOT NULL,
    state_data TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT,
    resolution TEXT,
    FOREIGN KEY(run_id) REFERENCES state_runs(run_id)
);
CREATE TABLE IF NOT EXISTS rag_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    target TEXT NOT NULL,
    created_at TEXT NOT NULL,
    details TEXT
);
"""

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        schema = SCHEMA.read_text(encoding="utf-8")
        conn.executescript(schema)
    except Exception:
        # State tables remain usable even if an older DB was created from another schema.
        pass
    conn.executescript(STATE_SQL)
    conn.commit()
    return DB_PATH

if __name__ == "__main__":
    print(f"Initialized: {init_db()}")
