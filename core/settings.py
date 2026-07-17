"""Central place for env-driven configuration and app paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Uploaded files and generated charts live outside git (see .gitignore)
UPLOADS_DIR = PROJECT_ROOT / "uploads"
CHARTS_DIR = PROJECT_ROOT / "exports" / "charts"
REPORTS_DIR = PROJECT_ROOT / "exports" / "reports"

for _dir in (UPLOADS_DIR, CHARTS_DIR, REPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
