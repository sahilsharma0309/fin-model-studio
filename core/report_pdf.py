"""Branded PDF export via WeasyPrint.

Builds a self-contained HTML document (charts and logo embedded as data
URIs) and renders it to PDF bytes. The same AnalysisResult objects the
Streamlit UI displays are the input, so what you see is what you export.
"""

import base64
import html
from datetime import date

import pandas as pd
from weasyprint import HTML

from core.result import AnalysisResult
from core.i18n import t
from core.branding import (
    ACCENT_COLOR,
    BRAND_NAME,
    FRAME_TEXT,
    LOGO_PATH,
    MONOGRAM,
    PAGE_WATERMARK_TEXT,
    PRIMARY_COLOR,
    SIGNATURE_PATH,
    WATERMARK_TEXT,
)

# Page-frame background repeated on every page: a double black line on the
# left/right/top with the brand name written in the gap between the two
# lines, plus the light diagonal watermark. WeasyPrint positions the @page
# background against the content area, so coordinates are in content-box
# units (A4 minus our margins ~ 487x711 CSS px) and the body is padded to
# keep content clear of the lines.
_PRIMARY_ENC = PRIMARY_COLOR.replace("#", "%23")
_PAGE_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='487' height='711'"
    " viewBox='0 0 487 711'>"
    # outer line: down-left, across-top, down-right
    "<path d='M3,711 L3,4 L484,4 L484,711' fill='none'"
    " stroke='%23111111' stroke-width='1.4'/>"
    # inner line, leaving a gap that carries the name at the top
    "<path d='M14,711 L14,23 L473,23 L473,711' fill='none'"
    " stroke='%23111111' stroke-width='0.7'/>"
    # name centered inside the top gap
    "<text x='243' y='17.5' font-size='9.5' font-family='Helvetica,Arial'"
    f" fill='{_PRIMARY_ENC}' text-anchor='middle' letter-spacing='3'>"
    f"{FRAME_TEXT}</text>"
    # light diagonal watermark
    "<text x='243' y='370' font-size='40' font-family='Helvetica,Arial'"
    f" fill='{_PRIMARY_ENC}' fill-opacity='0.05' text-anchor='middle'"
    " transform='rotate(-35 243 370)'>"
    f"{PAGE_WATERMARK_TEXT}</text>"
    "</svg>"
)

MAX_TABLE_ROWS = 20

_CSS = """
@page {
    size: A4;
    margin: 2.1cm 1.9cm 2.4cm 1.9cm;
    /* clears the frame lines + name band on every page */
    padding: 34px 26px 8px 26px;
    background: url("%(page_svg)s") no-repeat center center;
    background-size: 100%% 100%%;
    @bottom-center {
        content: "%(watermark)s";
        color: %(accent)s;
        font-size: 9pt;
        font-style: italic;
        font-family: Georgia, serif;
    }
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        color: #8a8f98;
        font-size: 8pt;
    }
}
body { font-family: Helvetica, Arial, 'Noto Sans Devanagari', 'Noto Sans', sans-serif;
       color: #23272e; font-size: 10.5pt; }
.client-line { font-size: 11.5pt; color: %(primary)s; font-weight: bold;
               margin: 0 0 14px 0; }
.client-line span { border-bottom: 2px solid %(accent)s; padding-bottom: 2px; }
.header { border: 2px solid %(primary)s; border-bottom: 3px solid %(accent)s;
          padding: 10px 14px; margin-bottom: 10px;
          display: flex; align-items: center; }
.logo { height: 52px; margin-right: 14px; }
.monogram { display: inline-block; width: 52px; height: 52px; line-height: 52px;
            border-radius: 50%%; background: %(primary)s; color: %(accent)s;
            font-weight: bold; font-size: 18pt; text-align: center; margin-right: 14px; }
.brand { color: %(primary)s; font-size: 16pt; font-weight: bold; }
.meta { color: #6a707a; font-size: 9pt; margin-bottom: 16px; }
.kpis { display: flex; gap: 10px; margin: 0 0 24px 0; }
.kpi { flex: 1; border: 1px solid #e3e5e8; border-top: 3px solid %(accent)s;
       padding: 8px 12px; }
.kpi-label { font-size: 7.5pt; color: #6a707a; text-transform: uppercase;
             letter-spacing: 0.06em; }
.kpi-value { font-size: 15pt; color: %(primary)s; font-weight: bold; }
.kpi-delta { font-size: 7.5pt; color: %(accent)s; }
h1 { color: %(primary)s; font-size: 15pt; margin: 18px 0 4px 0; }
.section { margin-bottom: 22px; page-break-inside: avoid; }
.question { color: %(primary)s; font-size: 12pt; font-weight: bold;
            border-left: 4px solid %(accent)s; padding-left: 8px; margin-bottom: 8px; }
.chart { max-width: 100%%; margin: 6px 0; }
.insight { background: #f6f4ee; border-left: 3px solid %(accent)s;
           padding: 8px 12px; font-size: 10pt; }
.guide { color: #6a707a; font-size: 8.5pt; font-style: italic; margin: 4px 0 0 0; }
table { border-collapse: collapse; width: 100%%; font-size: 9pt; margin: 6px 0; }
th { background: %(primary)s; color: white; padding: 5px 8px; text-align: left; }
td { border-bottom: 1px solid #e3e5e8; padding: 4px 8px; }
tr:nth-child(even) td { background: #f4f6f9; }
.truncated { color: #8a8f98; font-size: 8pt; font-style: italic; }
.error { color: #a33; }
.summary { border: 1px solid #e3e5e8; border-left: 4px solid %(accent)s;
           padding: 10px 14px; margin-bottom: 22px; }
.summary-title { color: %(primary)s; font-weight: bold; font-size: 11pt;
                 margin: 0 0 6px 0; }
.summary ul { margin: 0; padding-left: 16px; }
.summary li { font-size: 9.5pt; margin-bottom: 4px; }
.signature { margin-top: 34px; text-align: right; page-break-inside: avoid; }
.sign-img { display: block; margin-left: auto; height: 48px; margin-bottom: 2px; }
.sign-name { display: inline-block; border-top: 1.2px solid #23272e;
             padding-top: 5px; font-size: 9.5pt; color: #23272e; margin: 0; }
.sign-date { font-size: 8pt; color: #8a8f98; margin: 2px 0 0 0; }
""" % {
    "primary": PRIMARY_COLOR,
    "accent": ACCENT_COLOR,
    "watermark": WATERMARK_TEXT,
    "page_svg": _PAGE_SVG,
}


def _logo_html() -> str:
    if LOGO_PATH.exists():
        encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return f'<img class="logo" src="data:image/png;base64,{encoded}" alt="logo"/>'
    return f'<span class="monogram">{html.escape(MONOGRAM)}</span>'


def _chart_html(path: str) -> str:
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode()
    return f'<img class="chart" src="data:image/png;base64,{encoded}"/>'


def _table_html(df: pd.DataFrame, lang: str = "en") -> str:
    shown = df.head(MAX_TABLE_ROWS)
    table = shown.to_html(index=False, border=0, escape=True)
    note = ""
    if len(df) > MAX_TABLE_ROWS:
        text = t("showing_first", lang).format(shown=MAX_TABLE_ROWS, total=len(df))
        note = f'<p class="truncated">{text}</p>'
    return table + note


def _section_html(result: AnalysisResult, lang: str = "en") -> str:
    parts = [f'<div class="section"><p class="question">{html.escape(result.question)}</p>']
    if result.kind == "chart":
        if result.chart_path:
            parts.append(_chart_html(result.chart_path))
        if result.text:
            parts.append(f'<p class="insight">{html.escape(result.text)}</p>')
        if result.guide:
            parts.append(
                f'<p class="guide">{t("how_to_read", lang)}: {html.escape(result.guide)}</p>'
            )
    elif result.kind == "dataframe" and result.dataframe is not None:
        parts.append(_table_html(result.dataframe, lang))
    elif result.kind == "error":
        parts.append(f'<p class="error">{html.escape(result.text)}</p>')
    else:
        parts.append(f'<p class="insight">{html.escape(result.text)}</p>')
    parts.append("</div>")
    return "".join(parts)


def _summary_html(results: list[AnalysisResult], lang: str = "en") -> str:
    """Key-findings box built from the computed insights."""
    insights = [r.text for r in results if r.kind == "chart" and r.text]
    if len(insights) < 2:
        return ""
    items = "".join(f"<li>{html.escape(t)}</li>" for t in insights[:6])
    return (
        f'<div class="summary"><p class="summary-title">{t("key_findings", lang)}</p>'
        f"<ul>{items}</ul></div>"
    )


def _signature_html() -> str:
    image = ""
    if SIGNATURE_PATH.exists():
        encoded = base64.b64encode(SIGNATURE_PATH.read_bytes()).decode()
        mime = "image/jpeg" if SIGNATURE_PATH.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        image = f'<img class="sign-img" src="data:{mime};base64,{encoded}"/>'
    return (
        f'<div class="signature">{image}'
        f'<p class="sign-name">{html.escape(BRAND_NAME)}</p>'
        f'<p class="sign-date">{date.today():%d %B %Y}</p></div>'
    )


def _kpis_html(kpis) -> str:
    if not kpis:
        return ""
    tiles = "".join(
        f'<div class="kpi"><div class="kpi-label">{html.escape(k.label)}</div>'
        f'<div class="kpi-value">{html.escape(k.value)}</div>'
        f'<div class="kpi-delta">{html.escape(k.delta)}</div></div>'
        for k in kpis
    )
    return f'<div class="kpis">{tiles}</div>'


def build_html(results: list[AnalysisResult], title: str, dataset_name: str,
               kpis=None, client_name: str = "", lang: str = "en") -> str:
    sections = "".join(_section_html(r, lang) for r in results)
    client = ""
    if client_name:
        client = (
            f'<p class="client-line">{t("prepared_for", lang)}: '
            f"<span>{html.escape(client_name)}</span></p>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
  <div class="header">{_logo_html()}<span class="brand">{html.escape(BRAND_NAME)}</span></div>
  <h1>{html.escape(title)}</h1>
  <p class="meta">{t("dataset", lang)}: {html.escape(dataset_name)} &nbsp;·&nbsp; {date.today():%d %B %Y}</p>
  {client}
  {_kpis_html(kpis)}
  {_summary_html(results, lang)}
  {sections}
  {_signature_html()}
</body></html>"""


def export_pdf(results: list[AnalysisResult], title: str, dataset_name: str,
               kpis=None, client_name: str = "", lang: str = "en") -> bytes:
    return HTML(
        string=build_html(results, title, dataset_name, kpis, client_name, lang)
    ).write_pdf()
