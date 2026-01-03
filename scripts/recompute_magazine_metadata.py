from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
for path in (ROOT_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config.constants import DEFAULT_DB_PATH
from services.db_service import DatabaseService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recompute normalized_magazine, issue_year, issue_month using magazine + edition."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"Database not found: {db_path}")
        return 1

    db = DatabaseService(db_path)

    def progress(current: int, total: int) -> None:
        if total <= 0:
            return
        if current == 1 or current % 1000 == 0 or current == total:
            pct = (current / total) * 100
            print(f"\rProcessed {current}/{total} ({pct:5.1f}%)", end="", flush=True)

    total, updated = db.recompute_magazine_metadata(progress_cb=progress)
    if total:
        print()
    print(f"Scanned {total} rows, updated {updated} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
