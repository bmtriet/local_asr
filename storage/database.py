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
                    used_in_training INTEGER DEFAULT 0,
                    profile_id TEXT DEFAULT 'default'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration: Ensure profile_id column exists in transcriptions table
            cursor.execute("PRAGMA table_info(transcriptions)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "profile_id" not in columns:
                cursor.execute("ALTER TABLE transcriptions ADD COLUMN profile_id TEXT DEFAULT 'default'")

            # Ensure default profile exists
            cursor.execute("SELECT id FROM profiles WHERE id = 'default'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO profiles (id, name, description, is_active) VALUES ('default', 'Default Profile', 'Standard User Profile', 1)"
                )
            else:
                # Ensure at least one active profile
                cursor.execute("SELECT id FROM profiles WHERE is_active = 1")
                if not cursor.fetchone():
                    cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = 'default'")

            conn.commit()

    # Profile Management Methods
    def get_profiles(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, is_active, created_at FROM profiles ORDER BY created_at ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_active_profile(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, is_active, created_at FROM profiles WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"id": "default", "name": "Default Profile", "description": "", "is_active": 1}

    def set_active_profile(self, profile_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,))
            if not cursor.fetchone():
                return False
            cursor.execute("UPDATE profiles SET is_active = 0")
            cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (profile_id,))
            conn.commit()
            return True

    def create_profile(self, profile_id: str, name: str, description: str = "") -> bool:
        profile_id = profile_id.strip().lower()
        if not profile_id:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,))
            if cursor.fetchone():
                return False
            cursor.execute(
                "INSERT INTO profiles (id, name, description, is_active) VALUES (?, ?, ?, 0)",
                (profile_id, name.strip() or profile_id, description.strip())
            )
            conn.commit()
            return True

    def update_profile(self, profile_id: str, name: str, description: str = "") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE profiles SET name = ?, description = ? WHERE id = ?",
                (name.strip(), description.strip(), profile_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_profile(self, profile_id: str) -> bool:
        if profile_id == "default":
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # If deleting active profile, activate default
            cursor.execute("SELECT is_active FROM profiles WHERE id = ?", (profile_id,))
            row = cursor.fetchone()
            if row and row["is_active"] == 1:
                cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = 'default'")
            cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            conn.commit()
            return cursor.rowcount > 0

    def save_transcription(
        self,
        audio_path: str,
        duration: float,
        raw_text: str,
        corrected_text: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> int:
        """Save a new transcription log."""
        if corrected_text is None:
            corrected_text = raw_text
        if not profile_id:
            profile_id = self.get_active_profile().get("id", "default")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcriptions (audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training, profile_id)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (audio_path, duration, raw_text, corrected_text, profile_id)
            )
            conn.commit()
            return cursor.lastrowid

    def get_transcriptions_count(self, filter_type: str = "all", search: str = "", profile_id: Optional[str] = None) -> int:
        """Count total transcriptions matching filter, search and profile."""
        query = "SELECT COUNT(*) FROM transcriptions WHERE 1=1"
        params = []
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
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
        search: str = "",
        profile_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve latest transcriptions with pagination, filter, search, and profile."""
        query = """
            SELECT id, timestamp, audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training, profile_id
            FROM transcriptions
            WHERE 1=1
        """
        params = []
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
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

    def get_samples_for_training(self, profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve samples marked as reviewed that have not yet been used in training for given profile."""
        if not profile_id:
            profile_id = self.get_active_profile().get("id", "default")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, audio_path, duration, raw_text, corrected_text, profile_id
                FROM transcriptions
                WHERE is_reviewed = 1 AND used_in_training = 0 AND profile_id = ?
                ORDER BY id ASC
                """,
                (profile_id,)
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

    def get_reviewed_vocabulary(self, profile_id: Optional[str] = None) -> str:
        """Extract user-reviewed keywords, corrections, and proper nouns as context for active profile."""
        if not profile_id:
            profile_id = self.get_active_profile().get("id", "default")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT raw_text, corrected_text
                FROM transcriptions
                WHERE is_reviewed = 1 AND profile_id = ?
                ORDER BY id DESC
                LIMIT 50
                """,
                (profile_id,)
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

    def get_user_phrase_replacements(self, profile_id: Optional[str] = None) -> dict:
        """Fetch user-reviewed custom replacements mapping raw spoken phrases to preferred output for active profile."""
        if not profile_id:
            profile_id = self.get_active_profile().get("id", "default")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT raw_text, corrected_text
                FROM transcriptions
                WHERE is_reviewed = 1 AND raw_text != corrected_text AND profile_id = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (profile_id,)
            )
            rows = cursor.fetchall()
            
        replacements = {}
        for r in rows:
            raw = r["raw_text"].strip()
            corr = r["corrected_text"].strip()
            if raw and corr and len(raw) < 120:
                replacements[raw.lower()] = corr
        return replacements
