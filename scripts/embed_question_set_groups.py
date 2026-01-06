from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
for path in (ROOT_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config.constants import DEFAULT_DB_PATH
from services.db_service import DatabaseService


def build_group_text(display_name: str) -> str:
    return display_name.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create embeddings for question set groups and store them in configs."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database.",
    )
    parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformer model name.",
    )
    parser.add_argument(
        "--config-key",
        default="QuestionSetGroupEmbeddings",
        help="Config key to store embeddings under.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"Database not found: {db_path}")
        return 1

    db = DatabaseService(db_path)
    groups_config = db.load_config("QuestionSetGroup")
    groups = groups_config.get("groups", {}) if groups_config else {}
    if not groups:
        print("No QuestionSetGroup config found in DB.")
        return 1

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        print(f"sentence-transformers not available: {exc}")
        return 1

    group_names = list(groups.keys())
    texts = []
    meta = {}
    for name in group_names:
        data = groups.get(name, {}) or {}
        display = data.get("display_name", name)
        question_sets = data.get("question_sets", []) or []
        text = build_group_text(display)
        texts.append(text)
        meta[name] = {
            "display_name": display,
            "question_sets": question_sets,
            "text": text,
        }

    model = SentenceTransformer(args.model)
    vectors = model.encode(texts, normalize_embeddings=True)
    dim = int(vectors.shape[1]) if hasattr(vectors, "shape") else len(vectors[0])

    for name, vec in zip(group_names, vectors):
        blob = np.asarray(vec, dtype="float32").tobytes()
        meta[name]["embedding_b64"] = base64.b64encode(blob).decode("ascii")

    payload = {
        "model": args.model,
        "dim": dim,
        "count": len(group_names),
        "groups": meta,
    }
    db.save_config(args.config_key, payload)
    print(f"Saved embeddings for {len(group_names)} group(s) to config '{args.config_key}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
