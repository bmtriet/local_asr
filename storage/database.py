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

    def save_transcription(self, audio_path: str, duration: float, raw_text: str) -> int:
        """Save a new transcription log with initial raw_text equal to corrected_text."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcriptions (audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training)
                VALUES (?, ?, ?, ?, 0, 0)
                """,
                (audio_path, duration, raw_text, raw_text)
            )
            conn.commit()
            return cursor.lastrowid

    def get_transcriptions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve latest transcriptions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training
                FROM transcriptions
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

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
