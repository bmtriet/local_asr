import os
from typing import List, Dict, Any, Optional
from storage.database import Database

class DatasetBuilder:
    """Extracts reviewed & corrected speech samples from Database and formats for PEFT training."""
    def __init__(self, db: Optional[Database] = None, profile_id: Optional[str] = None):
        self.db = db or Database()
        self.profile_id = profile_id

    def collect_samples(self, profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns verified training pairs: [{'id': id, 'audio_path': path, 'text': text}, ...]."""
        p_id = profile_id or self.profile_id
        raw_samples = self.db.get_samples_for_training(profile_id=p_id)
        formatted = []
        for s in raw_samples:
            target_text = s.get("corrected_text") or s.get("raw_text")
            if target_text and target_text.strip():
                formatted.append({
                    "id": s["id"],
                    "audio_path": s["audio_path"],
                    "text": target_text.strip()
                })
        return formatted
