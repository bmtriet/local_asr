import json
import os
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import get_settings

DEFAULT_VOCABULARY = [
    {
        "target": "IFM",
        "aliases": ["ifm", "i f m", "ai ép em", "ai ef em"],
        "description": "IFM System"
    },
    {
        "target": "Global User",
        "aliases": ["global user", "globaluser", "glo bal user"],
        "description": "Global User Account"
    },
    {
        "target": "PAB",
        "aliases": ["pab", "p a b", "pi a bi"],
        "description": "PAB Department"
    }
]

def strip_accents(s: str) -> str:
    """Remove accents from Vietnamese text for robust matching."""
    s = s.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

class VocabularyManager:
    """
    Manages custom vocabulary keywords and aliases from vocabulary.json.
    Provides fuzzy and variant mapping for speech recognition and ITN normalization,
    along with keyword biasing context for ASR.
    Supports multi-user profiles (data/profiles/<profile_id>/vocabulary.json).
    """
    def __init__(self, file_path: Optional[Path] = None, profile_id: Optional[str] = None):
        self.profile_id = profile_id or "default"
        settings = get_settings()
        if file_path is not None:
            self.file_path = Path(file_path)
        elif self.profile_id == "default":
            # For default profile, use data/vocabulary.json (or data/profiles/default/vocabulary.json)
            self.file_path = settings.VOCABULARY_PATH
        else:
            self.file_path = settings.DATA_DIR / "profiles" / self.profile_id / "vocabulary.json"

        self.items: List[Dict[str, Any]] = []
        self._compiled_patterns: List[Dict[str, Any]] = []
        self.load()

    def switch_profile(self, profile_id: str):
        """Switch active profile and load its vocabulary.json."""
        self.profile_id = profile_id.strip().lower() or "default"
        settings = get_settings()
        if self.profile_id == "default":
            self.file_path = settings.VOCABULARY_PATH
        else:
            self.file_path = settings.DATA_DIR / "profiles" / self.profile_id / "vocabulary.json"
        self.load()

    def load(self) -> List[Dict[str, Any]]:
        """Load items from vocabulary.json. If missing, creates with defaults."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            import copy
            self.save(copy.deepcopy(DEFAULT_VOCABULARY))
            return self.items

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                self.items = json.loads(content) if content else []
        except Exception as e:
            print(f"[VocabularyManager] Error loading {self.file_path}: {e}")
            self.items = list(DEFAULT_VOCABULARY)

        self._compile()
        return self.items

    def save(self, items: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Persist items to vocabulary.json."""
        if items is not None:
            self.items = items
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            self._compile()
            return True
        except Exception as e:
            print(f"[VocabularyManager] Error saving {self.file_path}: {e}")
            return False

    def _compile(self):
        """Pre-compile regex replacement rules sorted by length descending (longest match first)."""
        patterns = []
        for entry in self.items:
            target = entry.get("target", "").strip()
            if not target:
                continue

            raw_aliases = entry.get("aliases", [])
            all_aliases = set()
            all_aliases.add(target.lower())
            for a in raw_aliases:
                a_clean = a.strip().lower()
                if a_clean:
                    all_aliases.add(a_clean)

            # Generate smart fuzzy variants:
            # 1. Spaced-out variants for acronyms/short words (e.g., "ifm" -> "i f m")
            # 2. Compact variants for multi-word phrases (e.g., "global user" -> "globaluser")
            expanded_aliases = set(all_aliases)
            for a in all_aliases:
                words = a.split()
                if len(words) > 1:
                    expanded_aliases.add("".join(words)) # compact: globaluser
                    expanded_aliases.add(r"\s+".join(map(re.escape, words))) # flexible spacing
                elif len(a) <= 5 and a.isalpha():
                    # Acronym like ifm, pab: match characters separated by optional spaces: "i\s*f\s*m"
                    spaced_regex = r"\s*".join([re.escape(c) for c in a])
                    expanded_aliases.add(spaced_regex)

            # Sort patterns so longer phrases match before shorter sub-phrases
            for pattern_str in expanded_aliases:
                try:
                    # Match on word boundary. In Vietnamese, word boundaries may border accents
                    regex = re.compile(rf'(?<!\w){pattern_str}(?!\w)', re.IGNORECASE)
                    patterns.append({
                        "regex": regex,
                        "target": target,
                        "len": len(pattern_str.replace(r"\s*", "").replace(r"\s+", " "))
                    })
                except Exception as e:
                    print(f"[VocabularyManager] Regex compile error for '{pattern_str}': {e}")

        # Longest match first
        patterns.sort(key=lambda x: x["len"], reverse=True)
        self._compiled_patterns = patterns

    def get_context_string(self) -> str:
        """Returns comma-separated target keywords and main phrases for ASR context biasing."""
        targets = []
        for item in self.items:
            target = item.get("target", "").strip()
            if target and target not in targets:
                targets.append(target)
        return ", ".join(targets)

    def apply(self, text: str) -> str:
        """
        Applies vocabulary mapping to text, converting aliases and variants into the correct target word.
        Preserves punctuation.
        """
        if not text or not text.strip():
            return text

        result = text
        for p in self._compiled_patterns:
            result = p["regex"].sub(p["target"], result)

        return result

    def get_all(self) -> List[Dict[str, Any]]:
        return self.items

    def upsert(self, target: str, aliases: List[str], description: str = "") -> bool:
        """Add or update a vocabulary entry."""
        target = target.strip()
        if not target:
            return False

        clean_aliases = [a.strip() for a in aliases if a.strip()]
        updated = False
        for item in self.items:
            if item.get("target", "").strip().lower() == target.lower():
                item["target"] = target
                item["aliases"] = clean_aliases
                item["description"] = description.strip()
                updated = True
                break

        if not updated:
            self.items.append({
                "target": target,
                "aliases": clean_aliases,
                "description": description.strip()
            })

        return self.save()

    def delete(self, target: str) -> bool:
        """Delete a vocabulary entry by target word."""
        target_clean = target.strip().lower()
        initial_len = len(self.items)
        self.items = [item for item in self.items if item.get("target", "").strip().lower() != target_clean]
        if len(self.items) != initial_len:
            return self.save()
        return False
