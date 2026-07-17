"""Brand identity used by the PDF and Word report templates.

Edit these values to re-brand every exported report in one place.
"""

from core.settings import PROJECT_ROOT

BRAND_NAME = "Sahil Sharma — Data Analyst"
PRIMARY_COLOR = "#1A2B4C"  # navy blue
ACCENT_COLOR = "#C9A94D"   # gold
WATERMARK_TEXT = "Prepared by Sahil"

# Very light diagonal watermark repeated on every report page
PAGE_WATERMARK_TEXT = "Sahil Sharma"

# Multi-series chart palette (fixed order, never cycled). Chart-tuned
# variants of the brand hues - validated for colorblind separation and
# contrast; the raw brand navy/gold are kept for single-series marks.
SERIES_PALETTE = ["#3D5C9E", "#A8862F", "#00969B"]

# Drop your real logo at this path; reports fall back to a monogram until then.
LOGO_PATH = PROJECT_ROOT / "assets" / "logo.png"

# Handwritten signature image; appears at the end of every report. First
# existing file wins; without one, reports show a typed sign-off block.
_SIGNATURE_CANDIDATES = [
    PROJECT_ROOT / "assets" / "signature.png",
    PROJECT_ROOT / "assets" / "signature.jpg",
]
SIGNATURE_PATH = next(
    (p for p in _SIGNATURE_CANDIDATES if p.exists()), _SIGNATURE_CANDIDATES[0]
)

# Text written inside the double-line page frame on PDF reports
FRAME_TEXT = "SAHIL SHARMA  ·  DATA ANALYST"

# Monogram shown in place of the logo while assets/logo.png doesn't exist
MONOGRAM = "".join(
    word[0] for word in BRAND_NAME.split("—")[0].split() if word[0].isalpha()
).upper()
