"""Shared result containers — what every model returns and what the
report engine consumes. No LLM anywhere in this platform: models are
pure formulas, so results are instant and deterministic."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class AnalysisResult:
    """One chart/section, in a form both the UI and reports can render."""

    question: str
    kind: str  # "chart" | "dataframe" | "text" | "error"
    text: str = ""
    chart_path: str | None = None
    dataframe: pd.DataFrame | None = field(default=None, repr=False)
    figure: object | None = field(default=None, repr=False)
    guide: str = ""
    priority: int = 9


def story_order(results: list["AnalysisResult"]) -> list["AnalysisResult"]:
    return sorted(results, key=lambda r: r.priority)


@dataclass
class Kpi:
    label: str
    value: str
    delta: str = ""
