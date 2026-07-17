"""Brand-styled plotly helpers shared by every model."""

import time

import numpy as np
import plotly.graph_objects as go

from core.branding import ACCENT_COLOR, PRIMARY_COLOR
from core.result import AnalysisResult
from core.settings import CHARTS_DIR

INK = "#23272e"
MUTED = "#6a707a"
GRID = "#e8eaed"
FONT_STACK = "Helvetica, Arial, 'Noto Sans Devanagari', 'Noto Sans', sans-serif"

_AXIS = dict(
    gridcolor=GRID, zeroline=False, linecolor=GRID,
    tickfont=dict(color=MUTED, size=12), title=None,
)


def base_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.01, font=dict(size=17, color=INK)),
        xaxis=_AXIS, yaxis=_AXIS,
        font=dict(family=FONT_STACK, color=INK, size=13),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=70, r=40, t=70, b=60),
        hoverlabel=dict(bgcolor=PRIMARY_COLOR, font=dict(color="white", size=12)),
        showlegend=False, barcornerradius=5,
    )
    return fig


def save_png(fig: go.Figure) -> str:
    path = CHARTS_DIR / f"model_{int(time.time() * 1000)}_{np.random.randint(1e6)}.png"
    fig.write_image(str(path), width=1000, height=560, scale=2)
    return str(path)


def chart_result(title: str, fig: go.Figure, insight: str,
                 guide: str = "", priority: int = 5) -> AnalysisResult:
    return AnalysisResult(
        question=title, kind="chart", text=insight,
        chart_path=save_png(fig), figure=fig, guide=guide, priority=priority,
    )


def fmt(value: float) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}K"
    if abs(value) >= 100 or float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}"
