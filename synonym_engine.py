"""
synonym_engine.py
-----------------
Provides word/phrase replacements for the humanizer pipeline.

Two modes:
  1. DB mode  — reads from MySQL (word_replacements table) when db_config is supplied.
  2. Fallback — uses a built-in dictionary when MySQL is unavailable.

Usage:
    engine = SynonymEngine()                    # fallback (no DB needed)
    engine = SynonymEngine(db_config={...})     # MySQL mode

    replacements = engine.get_all_replacements()
    # → { "delve": ["look into", "dig into", ...], ... }
"""

import json


# ---------------------------------------------------------------------------
# Built-in fallback data  (mirrors seed_data in db_builder.py)
# ---------------------------------------------------------------------------
_BUILTIN_REPLACEMENTS = {
    # Common AI words
    "delve":              ["look into", "dig into", "check out"],
    "intricate":          ["complex", "detailed", "tricky"],
    "utilize":            ["use", "apply", "work with"],
    "furthermore":        ["also", "plus", "and"],
    "moreover":           ["also", "on top of that", "plus"],
    "however":            ["but", "still", "though"],
    "thus":               ["so", "therefore", "because of that"],
    "hence":              ["so", "that's why", "for that reason"],
    "indeed":             ["really", "actually", "in fact"],

    # AI phrases
    "it is worth noting": ["note that", "keep in mind", "remember"],
    "in conclusion":      ["to sum up", "in short", "basically"],
    "in addition":        ["also", "plus", "on top of that"],
    "as a result":        ["so", "because of this", "that's why"],
    "on the other hand":  ["but", "at the same time", "still"],

    # Formal → human
    "testament":          ["proof", "evidence", "sign"],
    "demonstrates":       ["shows", "proves", "explains"],
    "facilitates":        ["helps", "makes easier", "supports"],
    "implements":         ["builds", "creates", "sets up"],
    "leverages":          ["uses", "takes advantage of", "works with"],

    # Tech AI words
    "robust":             ["strong", "reliable", "solid"],
    "scalable":           ["can grow", "handles more load", "expandable"],
    "optimize":           ["improve", "make better", "tune"],
    "efficient":          ["fast", "quick", "works well"],
    "seamless":           ["smooth", "easy", "without issues"],

    # Academic → human
    "significant":        ["important", "big", "major"],
    "numerous":           ["many", "a lot of", "plenty of"],
    "approximately":      ["about", "around", "roughly"],
    "subsequently":       ["later", "after that", "then"],

    # Passive voice
    "is utilized":        ["is used", "gets used"],
    "is implemented":     ["is built", "is created"],
    "has been developed": ["was built", "we built"],
    "was performed":      ["was done", "we did"],

    # Wordy filler
    "in order to":             ["to", "so we can"],
    "due to the fact that":    ["because", "since"],
    "a large number of":       ["many", "a lot of"],
    "at this point in time":   ["now", "right now"],
    "it is important to note": ["note that", "keep in mind"],
    "plays a vital role":      ["matters a lot", "is key", "is important"],
    "this demonstrates":       ["this shows", "this proves"],
    "crucial":                 ["key", "important", "critical"],
    "essential":               ["needed", "important", "key"],
    "additionally":            ["also", "plus", "and"],
    "in summary":              ["in short", "to wrap up", "basically"],
}


class SynonymEngine:
    """
    Loads word replacements from MySQL or falls back to built-in dictionary.
    """

    def __init__(self, db_config: dict = None):
        """
        Parameters
        ----------
        db_config : dict, optional
            MySQL connection config, e.g.:
            {"host": "localhost", "user": "root",
             "password": "pass", "database": "Humanizer_data"}
            If None or connection fails, built-in fallback is used.
        """
        self._replacements: dict[str, list[str]] = {}
        self._source = "builtin"

        if db_config:
            self._load_from_db(db_config)
        else:
            self._load_builtin()

    # ------------------------------------------------------------------
    def _load_builtin(self):
        self._replacements = dict(_BUILTIN_REPLACEMENTS)
        self._source = "builtin"
        print("  [SynonymEngine] Using built-in replacement dictionary "
              f"({len(self._replacements)} entries).")

    # ------------------------------------------------------------------
    def _load_from_db(self, db_config: dict):
        try:
            import mysql.connector  # optional dependency

            conn   = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT ai_words, alternatives FROM word_replacements")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if rows:
                for ai_word, alts_json in rows:
                    alts = json.loads(alts_json) if isinstance(alts_json, str) else alts_json
                    self._replacements[ai_word] = alts
                self._source = "mysql"
                print(f"  [SynonymEngine] Loaded {len(self._replacements)} entries from MySQL.")
            else:
                print("  [SynonymEngine] MySQL table is empty — falling back to built-in.")
                self._load_builtin()

        except Exception as exc:
            print(f"  [SynonymEngine] MySQL unavailable ({exc}) — falling back to built-in.")
            self._load_builtin()

    # ------------------------------------------------------------------
    def get_all_replacements(self) -> dict[str, list[str]]:
        """Return the full replacement mapping {ai_word: [alternatives]}."""
        return dict(self._replacements)

    # ------------------------------------------------------------------
    def get_alternatives(self, word: str) -> list[str]:
        """Return alternatives for a single word/phrase, or [] if not found."""
        return self._replacements.get(word.lower(), [])

    # ------------------------------------------------------------------
    @property
    def source(self) -> str:
        """'mysql' or 'builtin'."""
        return self._source


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    engine = SynonymEngine()
    print("\nSample replacements:")
    for word in ["delve", "utilize", "robust", "in conclusion"]:
        print(f"  {word!r:30s} → {engine.get_alternatives(word)}")