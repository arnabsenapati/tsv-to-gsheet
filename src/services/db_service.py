"""
SQLite data access helper for questions, configs, and custom lists.
"""

from __future__ import annotations

import json
import mimetypes
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from utils.helpers import normalize_magazine_edition, normalize_page, normalize_qno


class DatabaseService:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def set_db_path(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def fetch_questions_df(self, subject_name: str) -> pd.DataFrame:
        """
        Return a DataFrame shaped like the Excel import with standard headers.
        Columns: Qno, PageNo, Magazine Edition, Name of Question Set, Full Question Text, High level chapter, QuestionID
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT q.id, q.question_number, q.page_range, q.edition, q.question_set,
                       q.question_set_name, q.chapter, q.high_level_chapter,
                       q.question_text, q.magazine
                FROM questions q
                JOIN subjects s ON s.id = q.subject_id
                WHERE lower(s.name) = lower(?)
                """,
                (subject_name,),
            )
            rows = cur.fetchall()

        data = []
        for row in rows:
            magazine = row["magazine"] or ""
            edition = row["edition"] or ""
            mag_edition = f"{magazine} | {edition}" if magazine or edition else ""
            data.append(
                {
                    "Qno": row["question_number"] or "",
                    "PageNo": row["page_range"] or "",
                    "Magazine Edition": mag_edition,
                    "Name of Question Set": row["question_set_name"] or row["question_set"] or "",
                    "Full Question Text": row["question_text"] or "",
                    "High level chapter": row["high_level_chapter"] or row["chapter"] or "",
                    "QuestionID": row["id"],
                }
            )

        return pd.DataFrame(data)

    def load_config(self, key: str) -> Dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute("SELECT value_json FROM configs WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return {}
            try:
                return json.loads(row["value_json"])
            except json.JSONDecodeError:
                return {}

    def save_config(self, key: str, payload: Dict[str, Any]) -> None:
        value_json = json.dumps(payload, indent=2)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO configs(key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value_json),
            )

    # ------------------------------------------------------------------
    # Question lists
    # ------------------------------------------------------------------
    def _ensure_subject(self, name: str) -> int:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (name,))
            row = conn.execute("SELECT id FROM subjects WHERE lower(name)=lower(?)", (name,)).fetchone()
            if not row:
                raise RuntimeError(f"Failed to ensure subject '{name}'.")
            return int(row[0])

    def _collect_existing_triplets(self, subject_id: int) -> Dict[tuple, tuple]:
        """
        Return existing (normalized_magazine, normalized_qno, normalized_page) -> (magazine, qno, page, question_id)
        """
        result: Dict[tuple, tuple] = {}
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, normalized_magazine, question_number, page_range
                FROM questions
                WHERE subject_id = ?
                """,
                (subject_id,),
            ).fetchall()
        for row in rows:
            norm_mag = row["normalized_magazine"] or ""
            norm_qno = normalize_qno(row["question_number"])
            norm_page = normalize_page(row["page_range"])
            if norm_mag and norm_qno and norm_page:
                result[(norm_mag, norm_qno, norm_page)] = (
                    row["normalized_magazine"] or "",
                    str(row["question_number"] or ""),
                    str(row["page_range"] or ""),
                    int(row["id"]),
                )
        return result

    def insert_questions_from_tsv(
        self,
        subject_name: str,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[int], List[tuple]]:
        """
        Insert question records into DB with duplicate detection.

        Returns (inserted_ids, duplicates) where duplicates is a list of tuples:
        (magazine, qno, page, existing_qno, existing_page).
        """
        subject_id = self._ensure_subject(subject_name)
        existing = self._collect_existing_triplets(subject_id)
        duplicates: List[tuple] = []
        inserts: List[Tuple] = []

        for rec in records:
            norm_mag = normalize_magazine_edition(rec.get("magazine", ""))
            norm_qno = normalize_qno(rec.get("question_number"))
            norm_page = normalize_page(rec.get("page_range"))
            combo = (norm_mag, norm_qno, norm_page)
            if norm_mag and norm_qno and norm_page and combo in existing:
                _, ex_qno, ex_page, _ = existing[combo]
                duplicates.append(
                    (
                        rec.get("magazine") or "",
                        rec.get("question_number") or "",
                        rec.get("page_range") or "",
                        ex_qno,
                        ex_page,
                    )
                )
                continue

            edition = ""
            issue_year = None
            issue_month = None
            if norm_mag:
                parts = norm_mag.split("|", 1)
                if len(parts) > 1:
                    edition = parts[1]
                    if len(edition) == 7 and edition[4] == "-":
                        try:
                            issue_year = int(edition[:4])
                            issue_month = int(edition[5:7])
                        except Exception:
                            issue_year = None
                            issue_month = None

            inserts.append(
                (
                    subject_id,
                    rec.get("source") or "",
                    rec.get("magazine") or "",
                    norm_mag,
                    edition or rec.get("edition") or "",
                    issue_year,
                    issue_month,
                    rec.get("page_range") or "",
                    rec.get("question_set") or "",
                    rec.get("question_set_name") or "",
                    rec.get("chapter") or "",
                    rec.get("high_level_chapter") or "",
                    rec.get("question_number") or "",
                    rec.get("question_text") or "",
                    rec.get("answer_text"),
                    rec.get("explanation"),
                    rec.get("metadata_json"),
                )
            )

        inserted_ids: List[int] = []
        if inserts:
            with self._connect() as conn:
                cur = conn.executemany(
                    """
                    INSERT INTO questions (
                        subject_id, source, magazine, normalized_magazine, edition,
                        issue_year, issue_month, page_range, question_set, question_set_name,
                        chapter, high_level_chapter, question_number, question_text,
                        answer_text, explanation, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    inserts,
                )
                inserted_ids = [cur.lastrowid] if cur.lastrowid else []
                # When using executemany, lastrowid is the last inserted; fetch range manually
                if cur.lastrowid and len(inserts) > 1:
                    start_id = cur.lastrowid - len(inserts) + 1
                    inserted_ids = list(range(start_id, cur.lastrowid + 1))

        return inserted_ids, duplicates

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------
    def add_question_image(self, question_id: int, kind: str, file_path: Path) -> int:
        """
        Store an image for a question.

        Args:
            question_id: ID of the question the image belongs to
            kind: "question" or "answer" (stored in images.kind)
            file_path: Path to the image file

        Returns:
            Newly inserted image ID.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Image file not found: {path}")

        mime_type, _ = mimetypes.guess_type(path.name)
        mime_type = mime_type or "application/octet-stream"
        data = path.read_bytes()

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO images (question_id, kind, mime_type, data)
                VALUES (?, ?, ?, ?)
                """,
                (question_id, kind, mime_type, sqlite3.Binary(data)),
            )
            return cur.lastrowid or 0

    def get_image_counts(self, question_id: int) -> Dict[str, int]:
        """Return a dict of image counts grouped by kind for a question."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT kind, COUNT(*) as cnt FROM images WHERE question_id = ? GROUP BY kind",
                (question_id,),
            ).fetchall()
        return {row["kind"]: int(row["cnt"]) for row in rows}

    def load_question_lists(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
        """
        Return (question_lists, metadata) where question_lists is name -> list[dict],
        metadata is name -> dict (metadata_json contents).
        """
        question_lists: Dict[str, List[Dict[str, Any]]] = {}
        metadata: Dict[str, Dict[str, Any]] = {}

        with self._connect() as conn:
            list_rows = conn.execute("SELECT id, name, metadata_json FROM question_lists").fetchall()
            for list_row in list_rows:
                list_id = list_row["id"]
                list_name = list_row["name"]
                meta = {}
                if list_row["metadata_json"]:
                    try:
                        meta = json.loads(list_row["metadata_json"])
                    except json.JSONDecodeError:
                        meta = {}
                metadata[list_name] = meta

                item_rows = conn.execute(
                    """
                    SELECT q.*, qi.position
                    FROM question_list_items qi
                    JOIN questions q ON q.id = qi.question_id
                    WHERE qi.list_id = ?
                    ORDER BY qi.position
                    """,
                    (list_id,),
                ).fetchall()

                questions: List[Dict[str, Any]] = []
                for item in item_rows:
                    magazine = item["magazine"] or ""
                    edition = item["edition"] or ""
                    mag_edition = f"{magazine} | {edition}" if magazine or edition else ""
                    questions.append(
                        {
                            "group": item["high_level_chapter"] or item["chapter"] or "",
                            "question_set": item["question_set"] or "",
                            "question_set_name": item["question_set_name"] or item["question_set"] or "",
                            "group_key": item["question_set_name"] or item["question_set"] or "",
                            "qno": item["question_number"] or "",
                            "page": item["page_range"] or "",
                            "magazine": mag_edition,
                            "text": item["question_text"] or "",
                            "row_number": item["id"],
                            "question_id": item["id"],
                        }
                    )
                question_lists[list_name] = questions
        return question_lists, metadata

    def save_question_list(self, list_name: str, questions: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
        meta_json = json.dumps(metadata or {}, indent=2)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO question_lists(name, metadata_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    metadata_json = excluded.metadata_json
                """,
                (list_name, meta_json),
            )
            list_id = cur.lastrowid
            if not list_id:
                list_row = conn.execute("SELECT id FROM question_lists WHERE name = ?", (list_name,)).fetchone()
                list_id = list_row["id"]

            conn.execute("DELETE FROM question_list_items WHERE list_id = ?", (list_id,))

            position = 0
            for q in questions:
                qid = q.get("question_id") or q.get("row_number")
                if not qid:
                    continue
                conn.execute(
                    """
                    INSERT INTO question_list_items(list_id, question_id, position)
                    VALUES (?, ?, ?)
                    """,
                    (list_id, int(qid), position),
                )
                position += 1

    def delete_question_list(self, list_name: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM question_lists WHERE name = ?", (list_name,)).fetchone()
            if not row:
                return
            conn.execute("DELETE FROM question_lists WHERE id = ?", (row["id"],))

    def update_questions_chapter(self, question_ids: List[int], target_group: str) -> None:
        if not question_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "UPDATE questions SET high_level_chapter = ?, chapter = ? WHERE id = ?",
                [(target_group, target_group, qid) for qid in question_ids],
            )
