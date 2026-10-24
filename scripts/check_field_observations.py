#!/usr/bin/env python3
"""Repository launcher for the installed catch-can data-quality command."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.field_observations import main  # noqa: E402


if __name__ == "__main__":
    main()
