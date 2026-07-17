"""Model framework — every financial model is a ModelSpec: a list of
input fields plus a pure compute function. The app renders the form from
the spec; the compute function returns KPIs + charts + a verdict that
flow straight into the branded report engine."""

from dataclasses import dataclass, field as dc_field
from typing import Callable

import pandas as pd

from core.result import AnalysisResult, Kpi


@dataclass
class Field:
    key: str
    label: dict            # {"en": ..., "hi": ...}
    kind: str = "number"   # number | percent | int | bool | table
    default: object = 0.0
    help: dict | None = None
    min_value: float | None = None
    # for kind == "table": list of (column_key, {"en":..., "hi":...})
    columns: list | None = None
    rows: int = 4          # default editable rows for tables


@dataclass
class ModelOutput:
    kpis: list[Kpi]
    results: list[AnalysisResult]
    verdict: str = ""


@dataclass
class ModelSpec:
    key: str
    category: str
    name: dict
    desc: dict
    fields: list[Field]
    compute: Callable[[dict, str], ModelOutput]
    is_mix: bool = False


REGISTRY: dict[str, list[ModelSpec]] = {}


def register(spec: ModelSpec) -> ModelSpec:
    REGISTRY.setdefault(spec.category, []).append(spec)
    return spec


def table_default(columns: list, rows: int) -> pd.DataFrame:
    return pd.DataFrame({key: [None] * rows for key, _ in columns})


def clean_table(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    """Drop empty rows, coerce numeric columns."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(how="all")
