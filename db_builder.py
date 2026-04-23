"""
db_builder.py  (FIXED)
-----------------------
Fixes applied
─────────────
1. BUG: Function named `intitialize_database` (double-i typo).
   FIX: Renamed to `initialize_database` throughout.

2. BUG: No error handling — if MySQL is down the whole script crashes with
   an unreadable traceback.
   FIX: Wrapped in try/except with a clear error message.

3. BUG: `human_feedback_log` columns `original_ai_text` and `ai_generated_text`
   are confusingly named (both sound like AI text).
   FIX: Renamed second column to `humanized_text` to match its actual role.

4. IMPROVEMENT: Added `phrase_pattern` seed rows so that table is useful
   out of the box.

5. IMPROVEMENT: Added `check_tables()` helper to verify DB state without
   rebuilding.
"""

import json
import sys

# ── MySQL connection config ────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "pass",
    "database": "Humanizer_data",
}


# ── Table creation ─────────────────────────────────────────────────────────
def initialize_database(config: dict = None) -> bool:          # FIX 1: typo fixed
    """
    Create all tables and seed initial data.
    Returns True on success, False on failure.
    """
    cfg = config or DB_CONFIG

    try:
        import mysql.connector
    except ImportError:
        print("❌  mysql-connector-python not installed.")
        print("    Run: pip install mysql-connector-python")
        return False

    try:
        print("Connecting to MySQL...")
        conn   = mysql.connector.connect(**cfg)
        cursor = conn.cursor()

        # ── 1. AI overused words + human alternatives ──────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_replacements (
                ai_words     VARCHAR(255) PRIMARY KEY,
                alternatives JSON         NOT NULL,
                register     VARCHAR(50)  DEFAULT 'both'
            )
        """)

        # ── 2. WordNet synonym cache ───────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synonym_cache (
                word     VARCHAR(255) NOT NULL,
                pos      VARCHAR(10)  NOT NULL,
                synonyms JSON,
                PRIMARY KEY (word, pos)
            )
        """)

        # ── 3. Human phrase pattern templates ─────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phrase_pattern (
                id                   INT AUTO_INCREMENT PRIMARY KEY,
                pattern_regex        TEXT NOT NULL,
                replacement_template TEXT NOT NULL,
                category             VARCHAR(50)
            )
        """)

        # ── 4. Human feedback log  (FIX 3: column rename) ─────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_feedback_log (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                original_ai_text TEXT,
                humanized_text   TEXT,          -- FIX 3: was ai_generated_text
                human_edited_text TEXT,
                quality_score    FLOAT   DEFAULT 0,
                status           ENUM('pending','approved','rejected','trained')
                                         DEFAULT 'pending',
                model_version    VARCHAR(50),
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(status)
            )
        """)

        # ── Seed word_replacements ─────────────────────────────────────
        word_seed = [
            # Common AI words
            ("delve",              json.dumps(["look into", "dig into", "check out"]),          "both"),
            ("intricate",          json.dumps(["complex", "detailed", "tricky"]),               "both"),
            ("utilize",            json.dumps(["use", "apply", "work with"]),                   "both"),
            ("furthermore",        json.dumps(["also", "plus", "and"]),                         "informal"),
            ("moreover",           json.dumps(["also", "on top of that", "plus"]),              "informal"),
            ("however",            json.dumps(["but", "still", "though"]),                      "informal"),
            ("thus",               json.dumps(["so", "therefore", "because of that"]),          "both"),
            ("hence",              json.dumps(["so", "that's why", "for that reason"]),         "both"),
            ("indeed",             json.dumps(["really", "actually", "in fact"]),               "informal"),
            # AI phrases
            ("it is worth noting", json.dumps(["note that", "keep in mind", "remember"]),       "both"),
            ("in conclusion",      json.dumps(["to sum up", "in short", "basically"]),          "informal"),
            ("in addition",        json.dumps(["also", "plus", "on top of that"]),              "informal"),
            ("as a result",        json.dumps(["so", "because of this", "that's why"]),         "both"),
            ("on the other hand",  json.dumps(["but", "at the same time", "still"]),            "both"),
            # Formal → human
            ("testament",          json.dumps(["proof", "evidence", "sign"]),                   "formal"),
            ("demonstrates",       json.dumps(["shows", "proves", "explains"]),                 "both"),
            ("facilitates",        json.dumps(["helps", "makes easier", "supports"]),           "both"),
            ("implements",         json.dumps(["builds", "creates", "sets up"]),                "both"),
            ("leverages",          json.dumps(["uses", "takes advantage of", "works with"]),    "both"),
            # Tech AI
            ("robust",             json.dumps(["strong", "reliable", "solid"]),                 "both"),
            ("scalable",           json.dumps(["can grow", "handles more load", "expandable"]), "both"),
            ("optimize",           json.dumps(["improve", "make better", "tune"]),              "both"),
            ("efficient",          json.dumps(["fast", "quick", "works well"]),                 "informal"),
            ("seamless",           json.dumps(["smooth", "easy", "without issues"]),            "informal"),
            # Academic → human
            ("significant",        json.dumps(["important", "big", "major"]),                   "both"),
            ("numerous",           json.dumps(["many", "a lot of", "plenty of"]),               "informal"),
            ("approximately",      json.dumps(["about", "around", "roughly"]),                  "both"),
            ("subsequently",       json.dumps(["later", "after that", "then"]),                 "informal"),
            # Passive voice
            ("is utilized",        json.dumps(["is used", "gets used"]),                        "both"),
            ("is implemented",     json.dumps(["is built", "is created"]),                      "both"),
            ("has been developed", json.dumps(["was built", "we built"]),                       "informal"),
            ("was performed",      json.dumps(["was done", "we did"]),                          "informal"),
            # Wordy filler
            ("in order to",             json.dumps(["to", "so we can"]),                        "informal"),
            ("due to the fact that",    json.dumps(["because", "since"]),                       "informal"),
            ("a large number of",       json.dumps(["many", "a lot of"]),                       "informal"),
            ("at this point in time",   json.dumps(["now", "right now"]),                       "informal"),
            # Extra AI patterns  (additions)
            ("crucial",                 json.dumps(["key", "important", "critical"]),           "both"),
            ("essential",               json.dumps(["needed", "important", "key"]),             "both"),
            ("additionally",            json.dumps(["also", "plus", "and"]),                    "informal"),
            ("in summary",              json.dumps(["in short", "to wrap up", "basically"]),    "informal"),
            ("plays a vital role",      json.dumps(["matters a lot", "is key"]),                "both"),
            ("this demonstrates",       json.dumps(["this shows", "this proves"]),              "both"),
            ("it is worth noting that", json.dumps(["note that", "keep in mind"]),              "both"),
        ]

        cursor.executemany(
            "INSERT IGNORE INTO word_replacements (ai_words, alternatives, register) "
            "VALUES (%s, %s, %s)",
            word_seed,
        )

        # ── Seed phrase_pattern  (FIX 4: was empty) ───────────────────
        phrase_seed = [
            (r"\bIt is (crucial|essential|important) to\b",
             "You need to",
             "opener"),
            (r"\bThis (demonstrates|shows|illustrates) that\b",
             "This means",
             "connector"),
            (r"\bIn (conclusion|summary|closing)[,.]?\b",
             "To wrap up,",
             "closer"),
            (r"\bFurthermore[,.]?\b",
             "Also,",
             "connector"),
            (r"\bMoreover[,.]?\b",
             "On top of that,",
             "connector"),
            (r"\bAs a result[,.]?\b",
             "So,",
             "connector"),
            (r"\bDue to the fact that\b",
             "Because",
             "clause"),
            (r"\bIn order to\b",
             "To",
             "clause"),
            (r"\b(utilize[sd]?|utilise[sd]?)\b",
             "use",
             "word"),
            (r"\bleverages?\b",
             "uses",
             "word"),
        ]

        cursor.executemany(
            "INSERT INTO phrase_pattern (pattern_regex, replacement_template, category) "
            "VALUES (%s, %s, %s)",
            phrase_seed,
        )

        conn.commit()
        cursor.close()
        conn.close()
        print("✅  MySQL DB built and seeded successfully.")
        return True

    except Exception as exc:          # FIX 2: error handling
        print(f"❌  Database error: {exc}")
        return False


# ── Helper: inspect existing tables ────────────────────────────────────────
def check_tables(config: dict = None) -> None:
    """Print row counts for every humanizer table."""
    cfg = config or DB_CONFIG
    try:
        import mysql.connector
        conn   = mysql.connector.connect(**cfg)
        cursor = conn.cursor()
        for table in ("word_replacements", "synonym_cache",
                      "phrase_pattern", "human_feedback_log"):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table:<30} {count:>5} rows")
            except Exception:
                print(f"  {table:<30}  (table missing)")
        cursor.close()
        conn.close()
    except Exception as exc:
        print(f"❌  Could not connect: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = initialize_database()
    if ok:
        print("\nTable summary:")
        check_tables()