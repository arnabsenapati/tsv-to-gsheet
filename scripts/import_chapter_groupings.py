"""
Load chapter grouping JSON files, tags.cfg, and QuestionSetGroup.json into the SQLite configs table.
Stores each file's JSON string keyed by its stem (e.g., PhysicsChapterGrouping).
tags.cfg is stored under the key 'TagsConfig'.
QuestionSetGroup.json is stored under the key 'QuestionSetGroup'.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(r"G:\My Drive\Aditya\IITJEE\Database\question_bank.db")
SOURCE_DIR = Path(r"G:\My Drive\Aditya\IITJEE\QuestionAnalysisJsons\ChapterGrouping")
TAGS_CFG = Path(r"G:\My Drive\Aditya\IITJEE\QuestionAnalysisJsons\TagsConfig\tags.cfg")
QUESTION_SET_GROUP = Path(r"G:\My Drive\Aditya\IITJEE\QuestionAnalysisJsons\QuestionSetGroup.json")


def main() -> None:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source directory not found: {SOURCE_DIR}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    total = 0
    for json_path in sorted(SOURCE_DIR.glob("*.json")):
        raw = json_path.read_text(encoding="utf-8")
        # Validate JSON before saving
        json.loads(raw)
        key = json_path.stem  # e.g., PhysicsChapterGrouping
        with conn:
            conn.execute(
                """
                INSERT INTO configs(key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, raw),
            )
        total += 1
        print(f"Imported {json_path.name} -> key '{key}'")

    if TAGS_CFG.exists():
        raw = TAGS_CFG.read_text(encoding="utf-8")
        json.loads(raw)  # validate
        with conn:
            conn.execute(
                """
                INSERT INTO configs(key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                ("TagsConfig", raw),
            )
        total += 1
        print(f"Imported {TAGS_CFG.name} -> key 'TagsConfig'")
    else:
        print(f"Warning: tags.cfg not found at {TAGS_CFG}")

    if QUESTION_SET_GROUP.exists():
        raw = QUESTION_SET_GROUP.read_text(encoding="utf-8")
        json.loads(raw)  # validate
        with conn:
            conn.execute(
                """
                INSERT INTO configs(key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                ("QuestionSetGroup", raw),
            )
        total += 1
        print(f"Imported {QUESTION_SET_GROUP.name} -> key 'QuestionSetGroup'")
    else:
        print(f"Warning: QuestionSetGroup.json not found at {QUESTION_SET_GROUP}")

    conn.close()
    print(f"Finished. Imported {total} config file(s).")


if __name__ == "__main__":
    main()
