from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from ui_v2 import run_v2


def main() -> None:
    db = DatabaseManager()
    run_v2(db=db)


if __name__ == "__main__":
    main()
