"""Rebuild the derived Chroma index from active KnowledgeDocument rows."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.services.kb_service import reindex_all


def main() -> None:
    app = create_app()
    with app.app_context():
        count = reindex_all()
        print(f"Reindexed {count} active knowledge documents.")


if __name__ == "__main__":
    main()
