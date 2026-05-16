import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.expanduser('~/.local/share/tuxscribe')
DB_PATH = os.path.join(DB_DIR, 'tuxscribe.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS global_excluded_phrases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phrase TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    project_type TEXT DEFAULT 'novel',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS brief_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS writing_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL UNIQUE,
    content TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voice_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL UNIQUE,
    profile_text TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    title TEXT DEFAULT '',
    synopsis TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'planned',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""


class Database:
    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(projects)").fetchall()]
        if 'project_type' not in cols:
            self.conn.execute("ALTER TABLE projects ADD COLUMN project_type TEXT DEFAULT 'novel'")
        src_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(sources)").fetchall()]
        if 'summary' not in src_cols:
            self.conn.execute("ALTER TABLE sources ADD COLUMN summary TEXT DEFAULT ''")
        for col in ('cite_title', 'cite_author', 'cite_year', 'cite_publisher', 'cite_city'):
            if col not in src_cols:
                self.conn.execute(f"ALTER TABLE sources ADD COLUMN {col} TEXT DEFAULT ''")
        self.conn.commit()

    def _now(self):
        return datetime.now().isoformat(sep=' ', timespec='seconds')

    # Projects
    def create_project(self, name, project_type='novel'):
        cur = self.conn.execute(
            "INSERT INTO projects (name, project_type) VALUES (?, ?)", (name, project_type)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_projects(self):
        return self.conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall()

    def get_project(self, project_id):
        return self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    def rename_project(self, project_id, name):
        self.conn.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
            (name, self._now(), project_id)
        )
        self.conn.commit()

    def delete_project(self, project_id):
        self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()

    def touch_project(self, project_id):
        self.conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (self._now(), project_id)
        )
        self.conn.commit()

    # Brief messages
    def get_brief_messages(self, project_id):
        return self.conn.execute(
            "SELECT * FROM brief_messages WHERE project_id = ? ORDER BY id",
            (project_id,)
        ).fetchall()

    def add_brief_message(self, project_id, role, content):
        cur = self.conn.execute(
            "INSERT INTO brief_messages (project_id, role, content) VALUES (?, ?, ?)",
            (project_id, role, content)
        )
        self.conn.commit()
        self.touch_project(project_id)
        return cur.lastrowid

    def clear_brief_messages(self, project_id):
        self.conn.execute(
            "DELETE FROM brief_messages WHERE project_id = ?", (project_id,)
        )
        self.conn.commit()

    # Writing examples
    def get_writing_examples(self, project_id):
        row = self.conn.execute(
            "SELECT content FROM writing_examples WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        return row['content'] if row else ''

    def save_writing_examples(self, project_id, content):
        self.conn.execute(
            """INSERT INTO writing_examples (project_id, content, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id) DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at""",
            (project_id, content, self._now())
        )
        self.conn.commit()
        self.touch_project(project_id)

    # Voice profile
    def get_voice_profile(self, project_id):
        row = self.conn.execute(
            "SELECT profile_text FROM voice_profile WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        return row['profile_text'] if row else ''

    def save_voice_profile(self, project_id, profile_text):
        self.conn.execute(
            """INSERT INTO voice_profile (project_id, profile_text, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id) DO UPDATE SET profile_text=excluded.profile_text, updated_at=excluded.updated_at""",
            (project_id, profile_text, self._now())
        )
        self.conn.commit()
        self.touch_project(project_id)

    # Chapters
    def get_chapters(self, project_id):
        return self.conn.execute(
            "SELECT * FROM chapters WHERE project_id = ? ORDER BY chapter_number",
            (project_id,)
        ).fetchall()

    def get_chapter(self, chapter_id):
        return self.conn.execute(
            "SELECT * FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()

    def create_chapter(self, project_id, chapter_number, title='', synopsis=''):
        cur = self.conn.execute(
            "INSERT INTO chapters (project_id, chapter_number, title, synopsis) VALUES (?, ?, ?, ?)",
            (project_id, chapter_number, title, synopsis)
        )
        self.conn.commit()
        self.touch_project(project_id)
        return cur.lastrowid

    def update_chapter(self, chapter_id, **kwargs):
        allowed = {'title', 'synopsis', 'content', 'status', 'chapter_number'}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields['updated_at'] = self._now()
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [chapter_id]
        self.conn.execute(
            f"UPDATE chapters SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

    def delete_chapter(self, chapter_id):
        row = self.conn.execute(
            "SELECT project_id FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        self.conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        self.conn.commit()
        if row:
            self.touch_project(row['project_id'])

    # Sources
    def get_sources(self, project_id):
        return self.conn.execute(
            "SELECT id, project_id, filename, created_at FROM sources WHERE project_id = ? ORDER BY created_at",
            (project_id,)
        ).fetchall()

    def get_source_content(self, source_id):
        row = self.conn.execute(
            "SELECT content FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        return row['content'] if row else ''

    def add_source(self, project_id, filename, content):
        cur = self.conn.execute(
            "INSERT INTO sources (project_id, filename, content) VALUES (?, ?, ?)",
            (project_id, filename, content)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_source(self, source_id):
        self.conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self.conn.commit()

    def get_all_source_content(self, project_id):
        return self.conn.execute(
            """SELECT id, filename, content, summary,
                      cite_title, cite_author, cite_year, cite_publisher, cite_city
               FROM sources WHERE project_id = ? ORDER BY created_at""",
            (project_id,)
        ).fetchall()

    def save_source_summary(self, source_id, summary):
        self.conn.execute(
            "UPDATE sources SET summary = ? WHERE id = ?", (summary, source_id)
        )
        self.conn.commit()

    def save_source_citation(self, source_id, cite_title, cite_author, cite_year, cite_publisher, cite_city):
        self.conn.execute(
            """UPDATE sources SET cite_title=?, cite_author=?, cite_year=?, cite_publisher=?, cite_city=?
               WHERE id = ?""",
            (cite_title, cite_author, cite_year, cite_publisher, cite_city, source_id)
        )
        self.conn.commit()

    def get_sources_for_references(self, project_id):
        return self.conn.execute(
            """SELECT filename, cite_title, cite_author, cite_year, cite_publisher, cite_city
               FROM sources WHERE project_id = ? ORDER BY created_at""",
            (project_id,)
        ).fetchall()

    # Global excluded phrases (shared across all projects)
    def get_excluded_phrases(self):
        return self.conn.execute(
            "SELECT * FROM global_excluded_phrases ORDER BY created_at"
        ).fetchall()

    def add_excluded_phrase(self, phrase):
        cur = self.conn.execute(
            "INSERT INTO global_excluded_phrases (phrase) VALUES (?)",
            (phrase,)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_excluded_phrase(self, phrase_id):
        self.conn.execute("DELETE FROM global_excluded_phrases WHERE id = ?", (phrase_id,))
        self.conn.commit()

    def reorder_chapters(self, project_id):
        chapters = self.get_chapters(project_id)
        for i, ch in enumerate(chapters, 1):
            self.conn.execute(
                "UPDATE chapters SET chapter_number = ? WHERE id = ?",
                (i, ch['id'])
            )
        self.conn.commit()
