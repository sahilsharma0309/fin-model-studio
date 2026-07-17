"""App paths. No env configuration needed — this platform calls no APIs."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Generated charts and reports live outside git (see .gitignore)
UPLOADS_DIR = PROJECT_ROOT / "uploads"
CHARTS_DIR = PROJECT_ROOT / "exports" / "charts"
REPORTS_DIR = PROJECT_ROOT / "exports" / "reports"

for _dir in (UPLOADS_DIR, CHARTS_DIR, REPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
