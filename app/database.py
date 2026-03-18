import sqlite3
import os
import uuid
from datetime import datetime

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./latex_renderer.db")

# Ensure parent directory exists
os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    try:
        conn = get_db()
    except Exception as e:
        print(f"ERROR: Cannot open database at {DATABASE_PATH}: {e}")
        print(f"  Directory exists: {os.path.isdir(os.path.dirname(DATABASE_PATH) or '.')}")
        print(f"  Writable: {os.access(os.path.dirname(DATABASE_PATH) or '.', os.W_OK)}")
        raise
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT 'Untitled Project',
            source TEXT NOT NULL DEFAULT '',
            main_file TEXT NOT NULL DEFAULT 'main.tex',
            last_pdf_base64 TEXT,
            last_synctex_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS project_files (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            is_binary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(project_id, filename)
        );

        CREATE TABLE IF NOT EXISTS share_links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            access_level TEXT NOT NULL CHECK(access_level IN ('readonly', 'contributor')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # Migration: add main_file column if missing (existing databases)
    try:
        conn.execute("SELECT main_file FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE projects ADD COLUMN main_file TEXT NOT NULL DEFAULT 'main.tex'")
        conn.commit()

    # Migration: add cached render columns if missing (existing databases)
    try:
        conn.execute("SELECT last_pdf_base64 FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE projects ADD COLUMN last_pdf_base64 TEXT")
        conn.execute("ALTER TABLE projects ADD COLUMN last_synctex_json TEXT")
        conn.commit()

    # Migration: add is_binary column if missing (existing databases)
    try:
        conn.execute("SELECT is_binary FROM project_files LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE project_files ADD COLUMN is_binary INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    # Migration: migrate projects.source into project_files for existing projects
    rows = conn.execute("""
        SELECT p.id, p.source FROM projects p
        WHERE NOT EXISTS (SELECT 1 FROM project_files pf WHERE pf.project_id = p.id)
        AND p.source != ''
    """).fetchall()
    for row in rows:
        file_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO project_files (id, project_id, filename, content, created_at, updated_at) VALUES (?, ?, 'main.tex', ?, ?, ?)",
            (file_id, row["id"], row["source"], now, now),
        )
    if rows:
        conn.commit()

    conn.close()

# --- Users ---

def create_user(email: str, password_hash: str) -> dict:
    db = get_db()
    user_id = str(uuid.uuid4())
    try:
        db.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, email, password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return None
    user = db.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return dict(user)

def get_user_by_email(email: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return dict(row) if row else None

# --- Projects ---

def create_project(user_id: str, title: str = "Untitled Project", source: str = "") -> dict:
    db = get_db()
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO projects (id, user_id, title, source, main_file, created_at, updated_at) VALUES (?, ?, ?, ?, 'main.tex', ?, ?)",
        (project_id, user_id, title, source, now, now),
    )
    # Also create the main.tex file in project_files
    file_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO project_files (id, project_id, filename, content, created_at, updated_at) VALUES (?, ?, 'main.tex', ?, ?, ?)",
        (file_id, project_id, source, now, now),
    )
    db.commit()
    row = db.execute("SELECT id, user_id, title, source, main_file, created_at, updated_at FROM projects WHERE id = ?", (project_id,)).fetchone()
    db.close()
    return dict(row)

def list_projects(user_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, title, created_at, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_project(project_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT id, user_id, title, source, main_file, created_at, updated_at FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None

def update_project(project_id: str, title: str | None = None, source: str | None = None) -> dict | None:
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        db.close()
        return None
    new_title = title if title is not None else project["title"]
    new_source = source if source is not None else project["source"]
    now = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE projects SET title = ?, source = ?, updated_at = ? WHERE id = ?",
        (new_title, new_source, now, project_id),
    )
    # Also sync source to the main file in project_files
    if source is not None:
        main_file = project["main_file"] if "main_file" in project.keys() else "main.tex"
        existing = db.execute(
            "SELECT id FROM project_files WHERE project_id = ? AND filename = ?",
            (project_id, main_file),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE project_files SET content = ?, updated_at = ? WHERE id = ?",
                (source, now, existing["id"]),
            )
        else:
            file_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO project_files (id, project_id, filename, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, project_id, main_file, source, now, now),
            )
    db.commit()
    row = db.execute("SELECT id, user_id, title, source, main_file, created_at, updated_at FROM projects WHERE id = ?", (project_id,)).fetchone()
    db.close()
    return dict(row)

def save_cached_render(project_id: str, pdf_base64: str, synctex_json: str | None):
    db = get_db()
    db.execute(
        "UPDATE projects SET last_pdf_base64 = ?, last_synctex_json = ? WHERE id = ?",
        (pdf_base64, synctex_json, project_id),
    )
    db.commit()
    db.close()

def get_cached_render(project_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT last_pdf_base64, last_synctex_json FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    db.close()
    if not row or not row["last_pdf_base64"]:
        return None
    return {"pdf_base64": row["last_pdf_base64"], "synctex_json": row["last_synctex_json"]}

def delete_project(project_id: str):
    db = get_db()
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    db.close()

# --- Project Files ---

def create_project_file(project_id: str, filename: str, content: str = "", is_binary: bool = False) -> dict:
    db = get_db()
    file_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO project_files (id, project_id, filename, content, is_binary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (file_id, project_id, filename, content, 1 if is_binary else 0, now, now),
    )
    # Touch project updated_at
    db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
    db.commit()
    row = db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)).fetchone()
    db.close()
    return dict(row)

def list_project_files(project_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, filename, is_binary, created_at, updated_at FROM project_files WHERE project_id = ? ORDER BY filename",
        (project_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_project_file(file_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)).fetchone()
    db.close()
    return dict(row) if row else None

def get_project_file_by_name(project_id: str, filename: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT * FROM project_files WHERE project_id = ? AND filename = ?",
        (project_id, filename),
    ).fetchone()
    db.close()
    return dict(row) if row else None

def update_project_file(file_id: str, filename: str | None = None, content: str | None = None) -> dict | None:
    db = get_db()
    f = db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        db.close()
        return None
    now = datetime.utcnow().isoformat()
    new_filename = filename if filename is not None else f["filename"]
    new_content = content if content is not None else f["content"]
    db.execute(
        "UPDATE project_files SET filename = ?, content = ?, updated_at = ? WHERE id = ?",
        (new_filename, new_content, now, file_id),
    )
    # Touch project updated_at
    db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, f["project_id"]))
    db.commit()
    row = db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)).fetchone()
    db.close()
    return dict(row)

def delete_project_file(file_id: str) -> bool:
    db = get_db()
    f = db.execute("SELECT project_id FROM project_files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        db.close()
        return False
    db.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
    now = datetime.utcnow().isoformat()
    db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, f["project_id"]))
    db.commit()
    db.close()
    return True

def delete_all_project_files(project_id: str):
    db = get_db()
    db.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
    db.commit()
    db.close()

# --- Share Links ---

def create_share_link(project_id: str, access_level: str) -> dict:
    db = get_db()
    link_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO share_links (id, project_id, access_level) VALUES (?, ?, ?)",
        (link_id, project_id, access_level),
    )
    db.commit()
    row = db.execute("SELECT * FROM share_links WHERE id = ?", (link_id,)).fetchone()
    db.close()
    return dict(row)

def get_share_link(link_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        """SELECT sl.id, sl.project_id, sl.access_level, sl.created_at,
                  p.title, p.source, p.user_id
           FROM share_links sl JOIN projects p ON sl.project_id = p.id
           WHERE sl.id = ?""",
        (link_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None

def list_share_links(project_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, access_level, created_at FROM share_links WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def delete_share_link(link_id: str):
    db = get_db()
    db.execute("DELETE FROM share_links WHERE id = ?", (link_id,))
    db.commit()
    db.close()
