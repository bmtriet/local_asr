import os
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from config import get_settings
            db_path = get_settings().DB_PATH
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    audio_path TEXT NOT NULL,
                    duration REAL DEFAULT 0.0,
                    raw_text TEXT NOT NULL,
                    corrected_text TEXT NOT NULL,
                    is_reviewed INTEGER DEFAULT 0,
                    used_in_training INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_transcription(self, audio_path: str, duration: float, raw_text: str, corrected_text: Optional[str] = None) -> int:
        """Save a new transcription log."""
        if corrected_text is None:
            corrected_text = raw_text
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcriptions (audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training)
                VALUES (?, ?, ?, ?, 0, 0)
                """,
                (audio_path, duration, raw_text, corrected_text)
            )
            conn.commit()
            return cursor.lastrowid

    def get_transcriptions_count(self, filter_type: str = "all", search: str = "") -> int:
        """Count total transcriptions matching filter and search."""
        query = "SELECT COUNT(*) FROM transcriptions WHERE 1=1"
        params = []
        if filter_type == "reviewed":
            query += " AND is_reviewed = 1"
        elif filter_type == "unreviewed":
            query += " AND is_reviewed = 0"

        if search:
            query += " AND (raw_text LIKE ? OR corrected_text LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def get_transcriptions(
        self,
        limit: int = 10,
        offset: int = 0,
        filter_type: str = "all",
        search: str = ""
    ) -> List[Dict[str, Any]]:
        """Retrieve latest transcriptions with pagination, filter, and search."""
        query = """
            SELECT id, timestamp, audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training
            FROM transcriptions
            WHERE 1=1
        """
        params = []
        if filter_type == "reviewed":
            query += " AND is_reviewed = 1"
        elif filter_type == "unreviewed":
            query += " AND is_reviewed = 0"

        if search:
            query += " AND (raw_text LIKE ? OR corrected_text LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_transcription(self, item_id: int) -> bool:
        """Delete a transcription and its audio file if present."""
        item = self.get_transcription_by_id(item_id)
        if not item:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transcriptions WHERE id = ?", (item_id,))
            conn.commit()
            success = cursor.rowcount > 0
        if success and item.get("audio_path"):
            try:
                import os
                if os.path.exists(item["audio_path"]):
                    os.remove(item["audio_path"])
            except Exception:
                pass
        return success

    def get_transcription_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training
                FROM transcriptions
                WHERE id = ?
                """,
                (item_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_correction(self, item_id: int, corrected_text: str) -> bool:
        """Update corrected text and mark as reviewed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE transcriptions
                SET corrected_text = ?, is_reviewed = 1
                WHERE id = ?
                """,
                (corrected_text, item_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_samples_for_training(self) -> List[Dict[str, Any]]:
        """Retrieve samples marked as reviewed that have not yet been used in training."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, audio_path, duration, raw_text, corrected_text
                FROM transcriptions
                WHERE is_reviewed = 1 AND used_in_training = 0
                ORDER BY id ASC
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_samples_trained(self, ids: List[int]) -> bool:
        """Mark given transcription IDs as used in training."""
        if not ids:
            return True
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in ids)
            cursor.execute(
                f"""
                UPDATE transcriptions
                SET used_in_training = 1
                WHERE id IN ({placeholders})
                """,
                ids
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> bool:
        """Upsert a setting value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_reviewed_vocabulary(self) -> str:
        """Extract user-reviewed keywords, corrections, and proper nouns as context."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT raw_text, corrected_text
                FROM transcriptions
                WHERE is_reviewed = 1
                ORDER BY id DESC
                LIMIT 50
                """
            )
            rows = cursor.fetchall()
            
        vocab_set = set()
        for row in rows:
            raw = row["raw_text"].strip()
            corr = row["corrected_text"].strip()
            if corr:
                # Extract words with uppercase, digits, or distinct corrected phrases
                words = corr.split()
                for w in words:
                    w_clean = w.strip(".,?!;:-_\"'()[]{}")
                    if any(c.isupper() or c.isdigit() for c in w_clean) and len(w_clean) > 1:
                        vocab_set.add(w_clean)
                if raw != corr and len(corr) < 50:
                    vocab_set.add(corr)

        return ", ".join(sorted(vocab_set))

    def get_user_phrase_replacements(self) -> dict:
        """Fetch user-reviewed custom replacements mapping raw spoken phrases to preferred output."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT raw_text, corrected_text
                FROM transcriptions
                WHERE is_reviewed = 1 AND raw_text != corrected_text
                ORDER BY id DESC
                LIMIT 100
                """
            )
            rows = cursor.fetchall()
            
        replacements = {}
        for r in rows:
            raw = r["raw_text"].strip()
            corr = r["corrected_text"].strip()
            if raw and corr and len(raw) < 120:
                replacements[raw.lower()] = corr
        return replacements
