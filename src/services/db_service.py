"""
SQLite data access helper for questions, configs, and custom lists.
"""

from __future__ import annotations

import json
import mimetypes
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import shutil
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

import pandas as pd
from utils.helpers import normalize_magazine_edition, normalize_page, normalize_qno
from services.cbt_package import load_cqt


class DatabaseService:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._unique_values_cache: Dict[Tuple[str, ...], Dict[str, List[str]]] = {}
        self._image_counts_cache: Dict[int, Dict[str, int]] = {}
        self.ensure_question_embeddings_table()

    def set_db_path(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._unique_values_cache = {}
        self._image_counts_cache = {}
        self.ensure_question_embeddings_table()

    def ensure_question_embeddings_table(self) -> None:
        """Create embeddings table if missing."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS question_embeddings (
                    question_id INTEGER PRIMARY KEY,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector BLOB NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_question_embeddings_fk(conn)

    def _ensure_question_embeddings_fk(self, conn: sqlite3.Connection) -> None:
        """Ensure question_embeddings has a foreign key to questions."""
        try:
            fk_rows = conn.execute("PRAGMA foreign_key_list(question_embeddings)").fetchall()
        except Exception:
            return
        if fk_rows:
            return
        # Remove orphaned embeddings before migration
        conn.execute(
            "DELETE FROM question_embeddings WHERE question_id NOT IN (SELECT id FROM questions)"
        )
        conn.execute("ALTER TABLE question_embeddings RENAME TO question_embeddings_old")
        conn.execute(
            """
            CREATE TABLE question_embeddings (
                question_id INTEGER PRIMARY KEY,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vector BLOB NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            INSERT INTO question_embeddings (question_id, model, dim, vector, updated_at)
            SELECT question_id, model, dim, vector, updated_at
            FROM question_embeddings_old
            """
        )
        conn.execute("DROP TABLE question_embeddings_old")

    def list_embedding_ids(self) -> List[int]:
        """Return question_ids that have stored embeddings."""
        self.ensure_question_embeddings_table()
        with self._connect() as conn:
            rows = conn.execute("SELECT question_id FROM question_embeddings").fetchall()
        return [int(r["question_id"]) for r in rows]

    def upsert_embedding(self, question_id: int, model: str, vector: bytes, dim: int) -> None:
        """Insert or replace a question embedding."""
        self.ensure_question_embeddings_table()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO question_embeddings(question_id, model, dim, vector)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET
                    model=excluded.model,
                    dim=excluded.dim,
                    vector=excluded.vector,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (int(question_id), model, int(dim), vector),
            )

    def fetch_embeddings(self, ids: List[int], model: str | None = None) -> List[Dict[str, Any]]:
        """Fetch embeddings for given IDs (optionally filtered by model)."""
        if not ids:
            return []
        self.ensure_question_embeddings_table()
        placeholders = ",".join("?" for _ in ids)
        params: List[Any] = list(ids)
        model_clause = ""
        if model:
            model_clause = " AND model = ?"
            params.append(model)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT question_id, model, dim, vector
                FROM question_embeddings
                WHERE question_id IN ({placeholders}){model_clause}
                """,
                params,
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            vec = np.frombuffer(r["vector"], dtype="float32")
            results.append(
                {
                    "question_id": int(r["question_id"]),
                    "model": r["model"],
                    "dim": int(r["dim"]),
                    "vector": vec,
                }
            )
        return results

    def fetch_questions_text(self, ids: List[int]) -> List[Dict[str, Any]]:
        """Return basic question text info for given IDs."""
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, question_text FROM questions WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        return [{"id": int(r["id"]), "question_text": r["question_text"] or ""} for r in rows]

    # ------------------------------------------------------------------
    # Snapshotting with metadata (5-day retention)
    # ------------------------------------------------------------------
    def snapshot_database(self, reason: str, retention_days: int = 5) -> Path | None:
        """
        Create a timestamped copy of the database plus a metadata file describing the change.

        Args:
            reason: Short description of the change (20-30 words preferred).
            retention_days: How many days of snapshots to keep (default 5).
        """
        db_path = Path(self.db_path)
        if not db_path.is_file():
            return None

        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        suffix = db_path.suffix
        base_name = f"{db_path.stem}-{timestamp}"
        backup_path = backup_dir / f"{base_name}{suffix}"
        meta_path = backup_dir / f"{base_name}.json"

        shutil.copy2(db_path, backup_path)
        meta = {
            "timestamp": timestamp,
            "reason": reason.strip()[:300],
            "db": str(db_path.name),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Prune older than retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        for meta_file in backup_dir.glob(f"{db_path.stem}-*.json"):
            try:
                meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
                ts = datetime.strptime(meta_data.get("timestamp", ""), "%Y%m%d-%H%M%S")
            except Exception:
                continue
            if ts < cutoff:
                db_file = backup_dir / f"{db_path.stem}-{meta_data.get('timestamp','')}{suffix}"
                meta_file.unlink(missing_ok=True)
                db_file.unlink(missing_ok=True)

        return backup_path

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Return available snapshots with timestamp and reason."""
        db_path = Path(self.db_path)
        backup_dir = db_path.parent / "backups"
        snapshots: List[Dict[str, Any]] = []
        for meta_file in backup_dir.glob(f"{db_path.stem}-*.json"):
            try:
                meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
                ts = meta_data.get("timestamp") or ""
                reason = meta_data.get("reason") or ""
                db_file = backup_dir / f"{db_path.stem}-{ts}{db_path.suffix}"
                if not db_file.is_file():
                    continue
                try:
                    size_bytes = db_file.stat().st_size
                except Exception:
                    size_bytes = None
                snapshots.append(
                    {
                        "timestamp": ts,
                        "reason": reason,
                        "db_file": str(db_file),
                        "meta_file": str(meta_file),
                        "size_bytes": size_bytes,
                        "dt": datetime.strptime(ts, "%Y%m%d-%H%M%S") if ts else None,
                    }
                )
            except Exception:
                continue
        snapshots.sort(key=lambda s: s.get("dt") or datetime.min, reverse=True)
        return snapshots

    def restore_snapshot(self, snapshot_path: Path) -> None:
        """Restore the database from the given snapshot path (creates a safety snapshot first)."""
        snapshot_path = Path(snapshot_path)
        if not snapshot_path.is_file():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")
        # Safety snapshot before restore
        self.snapshot_database("Auto-backup before restore")
        shutil.copy2(snapshot_path, self.db_path)

    def backup_database(self, max_backups: int = 10) -> Path | None:
        """
        Create a timestamped copy of the database in a sibling `backups` folder.

        Returns the backup path if created, otherwise None.
        """
        # Deprecated: use snapshot_database instead for logged snapshots
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_question_by_id(self, question_id: int) -> Dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, question_number, page_range, question_set_name, magazine, edition,
                       question_text, answer_text, chapter, high_level_chapter
                FROM questions
                WHERE id = ?
                """,
                (question_id,),
            ).fetchone()
        if not row:
            return None
        return {k: row[k] for k in row.keys()}

    def get_unique_values(self, columns: list[str]) -> Dict[str, list[str]]:
        cache_key = tuple(columns)
        if self._unique_values_cache and cache_key in self._unique_values_cache:
            cached = self._unique_values_cache[cache_key]
            return {k: list(v) for k, v in cached.items()}

        result: Dict[str, list[str]] = {}
        with self._connect() as conn:
            for col in columns:
                try:
                    rows = conn.execute(
                        f"SELECT DISTINCT {col} AS val FROM questions WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS TEXT)) <> ''"
                    ).fetchall()
                    vals = []
                    for r in rows:
                        v = r["val"]
                        if v is None:
                            continue
                        text = str(v).strip()
                        if text:
                            vals.append(text)
                    result[col] = sorted(set(vals), key=lambda s: s.lower())
                except Exception:
                    result[col] = []
        self._unique_values_cache[cache_key] = {k: list(v) for k, v in result.items()}
        return result

    def _update_unique_values_cache(self, updates: Dict[str, Any]) -> None:
        """Merge new values into the cached unique values, if present."""
        if not updates or not self._unique_values_cache:
            return
        for cache_key, cached in self._unique_values_cache.items():
            updated = False
            for col in cache_key:
                if col not in updates:
                    continue
                value = updates.get(col)
                if value is None:
                    continue
                text = str(value).strip()
                if not text:
                    continue
                values = cached.get(col, [])
                if text not in values:
                    values.append(text)
                    values.sort(key=lambda s: s.lower())
                    cached[col] = values
                    updated = True
            if updated:
                self._unique_values_cache[cache_key] = cached

    def get_questions_with_missing(self, required_columns: list[str]) -> list[Dict[str, Any]]:
        if not required_columns:
            return []
        with self._connect() as conn:
            existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(questions)")]
            cols = [c for c in required_columns if c in existing_cols]
            if not cols:
                return []
            conditions = [f"COALESCE(TRIM(CAST({col} AS TEXT)),'') = ''" for col in cols]
            where_clause = " OR ".join(conditions)
            select_cols = ", ".join(
                [
                    "id",
                    "question_number",
                    "page_range",
                    "question_set_name",
                    "magazine",
                    "chapter",
                    "high_level_chapter",
                    "question_text",
                ]
            )
            query = f"SELECT {select_cols} FROM questions WHERE {where_clause}"
            rows = conn.execute(query).fetchall()
        results: list[Dict[str, Any]] = []
        for row in rows:
            data = {k: row[k] for k in row.keys()}
            missing = []
            for col in cols:
                val = row[col] if col in row.keys() else None
                if val is None:
                    missing.append(col)
                else:
                    text = str(val).strip()
                    if text == "":
                        missing.append(col)
            data["missing"] = missing
            results.append(data)
        return results

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
                       q.question_text, q.magazine, q.issue_year, q.issue_month
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
                    "Issue Year": row["issue_year"] or "",
                    "Issue Month": row["issue_month"] or "",
                    "Name of Question Set": row["question_set_name"] or row["question_set"] or "",
                    "Full Question Text": row["question_text"] or "",
                    "High level chapter": row["high_level_chapter"] or row["chapter"] or "",
                    "QuestionID": row["id"],
                }
            )

        return pd.DataFrame(data)

    def recompute_magazine_metadata(
        self, progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> tuple[int, int]:
        """
        Recompute normalized_magazine, issue_year, and issue_month using magazine + edition.

        Returns:
            (total_rows, updated_rows)
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, magazine, edition, normalized_magazine, issue_year, issue_month
                FROM questions
                """
            ).fetchall()

        updates: list[tuple] = []
        total = len(rows)
        for idx, row in enumerate(rows, start=1):
            if progress_cb:
                progress_cb(idx, total)
            magazine = row["magazine"] or ""
            edition = row["edition"] or ""
            mag_edition = f"{magazine} | {edition}" if magazine or edition else ""
            normalized = normalize_magazine_edition(mag_edition)
            issue_year = None
            issue_month = None
            if normalized:
                parts = normalized.split("|", 1)
                if len(parts) > 1:
                    edition_norm = parts[1].strip()
                    if len(edition_norm) == 7 and edition_norm[4] == "-":
                        try:
                            issue_year = int(edition_norm[:4])
                            issue_month = int(edition_norm[5:7])
                        except Exception:
                            issue_year = None
                            issue_month = None

            if (
                normalized != (row["normalized_magazine"] or "")
                or issue_year != row["issue_year"]
                or issue_month != row["issue_month"]
            ):
                updates.append((normalized, issue_year, issue_month, int(row["id"])))

        if updates:
            with self._connect() as conn:
                self.snapshot_database("Recompute normalized magazine/issue fields")
                conn.executemany(
                    """
                    UPDATE questions
                    SET normalized_magazine = ?, issue_year = ?, issue_month = ?
                    WHERE id = ?
                    """,
                    updates,
                )

        return len(rows), len(updates)

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
            self.snapshot_database(f"Config change: {key}")
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
        overwrite_duplicates: bool = False,
    ) -> Tuple[List[int], List[tuple], List[int]]:
        """
        Insert question records into DB with duplicate detection.

        Returns (inserted_ids, duplicates, updated_ids) where duplicates is a list of tuples:
        (magazine, qno, page, existing_qno, existing_page).
        """
        self.snapshot_database(f"Import questions for subject {subject_name}")
        subject_id = self._ensure_subject(subject_name)
        existing = self._collect_existing_triplets(subject_id)
        duplicates: List[tuple] = []
        inserts: List[Tuple] = []
        updates: List[Tuple] = []
        updated_ids: List[int] = []

        for rec in records:
            mag_val = rec.get("magazine") or ""
            ed_val = rec.get("edition") or ""
            mag_edition = f"{mag_val} | {ed_val}" if ed_val else mag_val
            norm_mag = normalize_magazine_edition(mag_edition)
            norm_qno = normalize_qno(rec.get("question_number"))
            norm_page = normalize_page(rec.get("page_range"))
            combo = (norm_mag, norm_qno, norm_page)
            if norm_mag and norm_qno and norm_page and combo in existing:
                _, ex_qno, ex_page, existing_id = existing[combo]
                if overwrite_duplicates:
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
                    updates.append(
                        (
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
                            int(existing_id),
                        )
                    )
                    updated_ids.append(int(existing_id))
                    continue
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

        if updates:
            with self._connect() as conn:
                conn.executemany(
                    """
                    UPDATE questions
                    SET source = ?, magazine = ?, normalized_magazine = ?, edition = ?,
                        issue_year = ?, issue_month = ?, page_range = ?, question_set = ?,
                        question_set_name = ?, chapter = ?, high_level_chapter = ?,
                        question_number = ?, question_text = ?, answer_text = ?,
                        explanation = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    updates,
                )
                if overwrite_duplicates and updated_ids:
                    unique_ids = sorted(set(updated_ids))
                    conn.executemany(
                        "DELETE FROM question_embeddings WHERE question_id = ?",
                        [(qid,) for qid in unique_ids],
                    )
        return inserted_ids, duplicates, updated_ids

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
            self.snapshot_database(f"Add {kind} image for question {question_id}")
            cur = conn.execute(
                """
                INSERT INTO images (question_id, kind, mime_type, data)
                VALUES (?, ?, ?, ?)
                """,
                (question_id, kind, mime_type, sqlite3.Binary(data)),
            )
            try:
                self._image_counts_cache.pop(int(question_id), None)
            except Exception:
                pass
            return cur.lastrowid or 0

    def add_question_image_bytes(self, question_id: int, kind: str, data: bytes, mime_type: str = "application/octet-stream") -> int:
        """Store an in-memory image blob for a question."""
        with self._connect() as conn:
            self.snapshot_database(f"Add {kind} image for question {question_id}")
            cur = conn.execute(
                """
                INSERT INTO images (question_id, kind, mime_type, data)
                VALUES (?, ?, ?, ?)
                """,
                (question_id, kind, mime_type, sqlite3.Binary(data)),
            )
            try:
                self._image_counts_cache.pop(int(question_id), None)
            except Exception:
                pass
            return cur.lastrowid or 0

    def get_image_counts_bulk(self, question_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """Return image counts grouped by kind for multiple questions."""
        if not question_ids:
            return {}
        ids: List[int] = []
        for qid in question_ids:
            if isinstance(qid, bool):
                continue
            try:
                ids.append(int(qid))
            except (TypeError, ValueError):
                continue
        if not ids:
            return {}
        unique_ids = sorted(set(ids))
        results: Dict[int, Dict[str, int]] = {qid: {} for qid in unique_ids}
        with self._connect() as conn:
            chunk_size = 900
            for start in range(0, len(unique_ids), chunk_size):
                chunk = unique_ids[start : start + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT question_id, kind, COUNT(*) as cnt
                    FROM images
                    WHERE question_id IN ({placeholders})
                    GROUP BY question_id, kind
                    """,
                    chunk,
                ).fetchall()
                for row in rows:
                    qid = int(row["question_id"])
                    results.setdefault(qid, {})[row["kind"]] = int(row["cnt"])
        self._image_counts_cache.update(results)
        return results

    def get_image_counts(self, question_id: int) -> Dict[str, int]:
        """Return a dict of image counts grouped by kind for a question."""
        qid = int(question_id)
        cached = self._image_counts_cache.get(qid)
        if cached is not None:
            return dict(cached)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT kind, COUNT(*) as cnt FROM images WHERE question_id = ? GROUP BY kind",
                (qid,),
            ).fetchall()
        result = {row["kind"]: int(row["cnt"]) for row in rows}
        self._image_counts_cache[qid] = dict(result)
        return result

    def get_images(self, question_id: int, kind: str) -> List[Dict[str, Any]]:
        """Return images for a question/kind."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, mime_type, data
                FROM images
                WHERE question_id = ? AND kind = ?
                ORDER BY id
                """,
                (question_id, kind),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": int(row["id"]),
                    "mime_type": row["mime_type"] or "application/octet-stream",
                    "data": row["data"],
                }
            )
        return result

    def delete_images(self, question_id: int, kind: str | None = None) -> int:
        """
        Delete images for a question. If kind is provided, only that category is removed.

        Returns the number of deleted rows.
        """
        with self._connect() as conn:
            self.snapshot_database(f"Delete images ({kind or 'all'}) for question {question_id}")
            if kind:
                cur = conn.execute(
                    "DELETE FROM images WHERE question_id = ? AND kind = ?",
                    (question_id, kind),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM images WHERE question_id = ?",
                    (question_id,),
                )
            deleted = cur.rowcount or 0
        try:
            self._image_counts_cache.pop(int(question_id), None)
        except Exception:
            pass
        return deleted

    # ------------------------------------------------------------------
    # Question updates
    # ------------------------------------------------------------------
    def update_question_fields(self, question_id: int, fields: Dict[str, Any]) -> None:
        """Update allowed fields on a question row."""
        if not fields:
            return
        allowed = {
            "question_number",
            "page_range",
            "question_set_name",
            "magazine",
            "edition",
            "question_text",
            "answer_text",
            "chapter",
            "high_level_chapter",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return

        self.snapshot_database(f"Update question {question_id}")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        values.append(question_id)
        with self._connect() as conn:
            if "question_text" in updates:
                row = conn.execute(
                    "SELECT question_text FROM questions WHERE id = ?",
                    (question_id,),
                ).fetchone()
                previous_text = (row["question_text"] if row else None) or ""
                next_text = updates.get("question_text") or ""
                if previous_text.strip() != str(next_text).strip():
                    cur = conn.execute(
                        "DELETE FROM question_embeddings WHERE question_id = ?",
                        (question_id,),
                    )
                    if cur.rowcount:
                        pass
            conn.execute(f"UPDATE questions SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        self._update_unique_values_cache(updates)

    def load_question_lists(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
        """
        Return (question_lists, metadata) where question_lists is name -> list[dict],
        metadata is name -> dict (metadata_json contents).
        """
        question_lists: Dict[str, List[Dict[str, Any]]] = {}
        metadata: Dict[str, Dict[str, Any]] = {}

        with self._connect() as conn:
            list_rows = conn.execute("SELECT id, name, metadata_json, created_at FROM question_lists").fetchall()
            for list_row in list_rows:
                list_id = list_row["id"]
                list_name = list_row["name"]
                meta = {}
                if list_row["metadata_json"]:
                    try:
                        meta = json.loads(list_row["metadata_json"])
                    except json.JSONDecodeError:
                        meta = {}
                created_at = list_row["created_at"] if "created_at" in list_row.keys() else None
                if created_at:
                    meta["_created_at"] = created_at
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
                            "issue_year": item["issue_year"],
                            "issue_month": item["issue_month"],
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
        self.snapshot_database(f"Save question list {list_name}")
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

    def set_list_archived(self, list_name: str, archived: bool) -> None:
        """Mark a saved list as archived by updating its metadata."""
        with self._connect() as conn:
            row = conn.execute("SELECT metadata_json FROM question_lists WHERE name = ?", (list_name,)).fetchone()
            meta = {}
            if row and row["metadata_json"]:
                try:
                    meta = json.loads(row["metadata_json"]) or {}
                except Exception:
                    meta = {}
            meta["archived"] = bool(archived)
            meta_json = json.dumps(meta, ensure_ascii=False, indent=2)
            self.snapshot_database(f"{'Archive' if archived else 'Unarchive'} list {list_name}")
            conn.execute(
                """
                INSERT INTO question_lists(name, metadata_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET metadata_json = excluded.metadata_json
                """,
                (list_name, meta_json),
            )

    def get_list_theory(self, list_name: str) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT metadata_json FROM question_lists WHERE name = ?", (list_name,)).fetchone()
        if not row or not row["metadata_json"]:
            return ""
        try:
            meta = json.loads(row["metadata_json"]) or {}
        except Exception:
            meta = {}
        return meta.get("theory_latex", "") or ""

    def set_list_theory(self, list_name: str, theory_text: str) -> None:
        with self._connect() as conn:
            self.snapshot_database(f"Update theory for list {list_name}")
            row = conn.execute("SELECT metadata_json FROM question_lists WHERE name = ?", (list_name,)).fetchone()
            meta = {}
            if row and row["metadata_json"]:
                try:
                    meta = json.loads(row["metadata_json"]) or {}
                except Exception:
                    meta = {}
            meta["theory_latex"] = theory_text or ""
            meta_json = json.dumps(meta, ensure_ascii=False, indent=2)
            conn.execute(
                """
                INSERT INTO question_lists(name, metadata_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET metadata_json = excluded.metadata_json
                """,
                (list_name, meta_json),
            )

    def delete_question_list(self, list_name: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM question_lists WHERE name = ?", (list_name,)).fetchone()
            if not row:
                return
            self.snapshot_database(f"Delete question list {list_name}")
            conn.execute("DELETE FROM question_lists WHERE id = ?", (row["id"],))

    def update_questions_chapter(self, question_ids: List[int], target_group: str) -> None:
        if not question_ids:
            return
        self.snapshot_database(f"Update chapters for {len(question_ids)} questions")
        with self._connect() as conn:
            conn.executemany(
                "UPDATE questions SET high_level_chapter = ?, chapter = ? WHERE id = ?",
                [(target_group, target_group, qid) for qid in question_ids],
            )

    def delete_question(self, question_id: int) -> None:
        """Delete a question and its related data."""
        if not question_id:
            return
        self.snapshot_database(f"Delete question {question_id}")
        with self._connect() as conn:
            conn.execute("DELETE FROM question_embeddings WHERE question_id = ?", (question_id,))
            conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        try:
            self._image_counts_cache.pop(int(question_id), None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Exams (.cqt import)
    # ------------------------------------------------------------------
    def _ensure_exam_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    list_name TEXT,
                    imported_at TEXT,
                    evaluated INTEGER DEFAULT 0,
                    evaluated_at TEXT,
                    total_questions INTEGER,
                    answered INTEGER,
                    correct INTEGER,
                    wrong INTEGER,
                    score INTEGER,
                    percent REAL,
                    source_path TEXT,
                    payload_json TEXT
                )
                """
            )
            self._add_column_if_missing(conn, "exam_questions", "eval_status", "TEXT")
            self._add_column_if_missing(conn, "exam_questions", "eval_comment", "TEXT")

    def _add_column_if_missing(self, conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
        cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exam_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id INTEGER NOT NULL,
                    q_index INTEGER,
                    question_json TEXT,
                    response_json TEXT,
                    correct INTEGER,
                    answered INTEGER,
                    score INTEGER,
                    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
                )
                """
            )

    def import_exam_from_cqt(self, path: str, package_password: str) -> Dict[str, Any]:
        """Import a .cqt package, compute stats, and persist as an exam record."""
        self.snapshot_database("Import exam from CQT")
        self._ensure_exam_tables()
        payload = load_cqt(path, package_password)
        questions = payload.get("questions", [])
        responses = payload.get("responses", {}) or {}
        evaluated = bool(payload.get("evaluated"))
        evaluated_at = payload.get("evaluated_at")
        total = len(questions)

        def _qkey(q: Dict[str, Any], idx: int) -> str:
            if q.get("question_id") not in (None, ""):
                return str(q.get("question_id"))
            if q.get("qno") not in (None, ""):
                return f"qno_{q.get('qno')}"
            return f"idx_{idx}"

        def _extract_answer(resp: Any) -> Any:
            if isinstance(resp, dict):
                return resp.get("answer")
            return resp

        def _normalize_mcq_response(resp_val: Any) -> list[str]:
            if resp_val is None:
                return []
            if isinstance(resp_val, str):
                text = resp_val.strip()
                if not text:
                    return []
                if "," in text:
                    return [part.strip() for part in text.split(",") if part.strip()]
                return [text]
            if isinstance(resp_val, (list, tuple, set)):
                items: list[str] = []
                for item in resp_val:
                    text = str(item).strip()
                    if text:
                        items.append(text)
                return items
            return []

        def _normalize_numerical_response(resp_val: Any) -> str:
            if resp_val is None:
                return ""
            if isinstance(resp_val, (int, float)):
                return str(resp_val).strip()
            return str(resp_val).strip()

        def _answered(qtype: str, resp_val: Any) -> bool:
            if qtype == "numerical":
                return bool(_normalize_numerical_response(resp_val))
            return bool(_normalize_mcq_response(resp_val))

        def _is_correct(q: Dict[str, Any], resp_val: Any) -> bool:
            qtype = q.get("question_type", "mcq_single") or "mcq_single"
            if qtype == "numerical":
                answer_val = str(q.get("numerical_answer", "")).strip()
                sel_val = _normalize_numerical_response(resp_val)
                return bool(answer_val) and sel_val == answer_val
            sel_list = _normalize_mcq_response(resp_val)
            correct_opts_raw = q.get("correct_options", []) or []
            if isinstance(correct_opts_raw, str):
                correct_opts = [correct_opts_raw]
            else:
                correct_opts = [str(opt).strip() for opt in correct_opts_raw if str(opt).strip()]
            return bool(correct_opts) and set(sel_list) == set(correct_opts)

        answered_cnt = 0
        correct_cnt = 0
        wrong_cnt = 0
        question_rows: List[Tuple] = []

        for idx, q in enumerate(questions):
            key = _qkey(q, idx)
            resp = responses.get(str(key))
            resp_val = _extract_answer(resp)
            qtype = q.get("question_type", "mcq_single") or "mcq_single"
            is_ans = _answered(qtype, resp_val)
            is_correct = _is_correct(q, resp_val) if evaluated else False
            if is_ans:
                answered_cnt += 1
            if evaluated:
                if is_correct:
                    correct_cnt += 1
                elif is_ans:
                    wrong_cnt += 1
            q_score = 4 if is_correct else (-1 if evaluated and is_ans and not is_correct else 0)
            correct_opts = q.get("correct_options", [])
            numerical_answer = q.get("numerical_answer")
            qid = q.get("question_id")
            qno = q.get("qno")
            # Debug prints removed
            question_rows.append(
                (
                    idx,
                    json.dumps(q, ensure_ascii=False),
                    json.dumps(resp, ensure_ascii=False),
                    1 if is_correct else 0,
                    1 if is_ans else 0,
                    q_score,
                )
            )

        score = correct_cnt * 4 - wrong_cnt
        percent = (correct_cnt * 4 / (total * 4)) * 100 if total else 0.0
        imported_at = datetime.utcnow().isoformat() + "Z"

        exam_id = None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO exams (
                    name, list_name, imported_at, evaluated, evaluated_at, total_questions,
                    answered, correct, wrong, score, percent, source_path, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    Path(path).name,
                    payload.get("list_name", ""),
                    imported_at,
                    1 if evaluated else 0,
                    evaluated_at if evaluated else None,
                    total,
                    answered_cnt,
                    correct_cnt,
                    wrong_cnt,
                    score,
                    percent,
                    str(path),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            exam_id = cur.lastrowid
            conn.executemany(
                """
                INSERT INTO exam_questions (
                    exam_id, q_index, question_json, response_json, correct, answered, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [(exam_id, *row) for row in question_rows],
            )

        return {
            "exam_id": exam_id,
            "imported_at": imported_at,
            "total": total,
            "answered": answered_cnt,
            "correct": correct_cnt,
            "wrong": wrong_cnt,
            "score": score,
            "percent": percent,
            "evaluated": evaluated,
            "evaluated_at": evaluated_at,
        }

    def list_exams(self) -> List[Dict[str, Any]]:
        self._ensure_exam_tables()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM exams
                ORDER BY imported_at DESC, id DESC
                """
            ).fetchall()
        result = []
        for row in rows:
            result.append({k: row[k] for k in row.keys()})
        return result

    def get_exam_questions(self, exam_id: int) -> List[Dict[str, Any]]:
        self._ensure_exam_tables()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT q_index, question_json, response_json, correct, answered, score, eval_status, eval_comment
                FROM exam_questions
                WHERE exam_id = ?
                ORDER BY q_index
                """,
                (exam_id,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            try:
                question = json.loads(row["question_json"] or "{}")
            except json.JSONDecodeError:
                question = {}
            try:
                response = json.loads(row["response_json"] or "null")
            except json.JSONDecodeError:
                response = None
            result.append(
                {
                    "index": row["q_index"],
                    "question": question,
                    "response": response,
                    "correct": bool(row["correct"]),
                    "answered": bool(row["answered"]),
                    "score": row["score"],
                    "eval_status": row["eval_status"],
                    "eval_comment": row["eval_comment"],
                }
            )
        return result

    def get_exam_by_id(self, exam_id: int) -> Dict[str, Any] | None:
        self._ensure_exam_tables()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
        if not row:
            return None
        return {k: row[k] for k in row.keys()}

    def delete_exam(self, exam_id: int) -> None:
        """Delete an exam and its questions."""
        self._ensure_exam_tables()
        self.snapshot_database(f"Delete exam {exam_id}")
        with self._connect() as conn:
            conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))

    def update_exam_question_evaluation(self, exam_id: int, q_index: int, status: str, comment: str) -> Dict[str, Any]:
        """
        Override evaluation for a question and recompute exam aggregates.
        status: 'correct' | 'incorrect' | 'unanswered'
        comment: required note for this override
        """
        self._ensure_exam_tables()
        if not comment:
            raise ValueError("Evaluation comment is required.")
        status = (status or "").lower()
        if status not in ("correct", "incorrect", "unanswered"):
            raise ValueError("Invalid evaluation status.")
        self.snapshot_database(f"Exam {exam_id} eval override q{q_index} -> {status}")
        correct = 1 if status == "correct" else 0
        answered = 0 if status == "unanswered" else 1
        score = 4 if status == "correct" else (-1 if status == "incorrect" else 0)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE exam_questions
                SET correct = ?, answered = ?, score = ?, eval_status = ?, eval_comment = ?
                WHERE exam_id = ? AND q_index = ?
                """,
                (correct, answered, score, status, comment, exam_id, q_index),
            )
            agg = conn.execute(
                """
                SELECT
                    SUM(correct) AS correct,
                    SUM(answered) AS answered,
                    COUNT(*) AS total,
                    SUM(score) AS score
                FROM exam_questions
                WHERE exam_id = ?
                """,
                (exam_id,),
            ).fetchone()
            correct_cnt = int(agg["correct"] or 0)
            answered_cnt = int(agg["answered"] or 0)
            total = int(agg["total"] or 0)
            score_sum = int(agg["score"] or 0)
            wrong_cnt = max(answered_cnt - correct_cnt, 0)
            percent = (score_sum / (total * 4)) * 100 if total else 0.0
            evaluated_at = datetime.utcnow().isoformat() + "Z"
            conn.execute(
                """
                UPDATE exams
                SET correct = ?, answered = ?, wrong = ?, score = ?, percent = ?, evaluated = 1, evaluated_at = ?
                WHERE id = ?
                """,
                (correct_cnt, answered_cnt, wrong_cnt, score_sum, percent, evaluated_at, exam_id),
            )
        return {
            "correct": correct_cnt,
            "answered": answered_cnt,
            "wrong": wrong_cnt,
            "score": score_sum,
            "percent": percent,
            "evaluated_at": evaluated_at,
        }
