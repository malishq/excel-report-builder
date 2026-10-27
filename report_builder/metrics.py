from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import Config
from .formatting import month_label, month_short

DIMENSIONS = ("manager", "category", "region")
OTHER_LABEL = "Прочее"
REST_LABEL = "Остальные"
OTHER_LABELS = {OTHER_LABEL, REST_LABEL}


@dataclass
class Report:
    data: pd.DataFrame
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    revenue: float
    orders: int
    avg_check: float
    quantity: Optional[float]
    clients: Optional[int]
    growth: Optional[float]
    growth_label: str
    months: List[pd.Period]
    by_month: pd.DataFrame
    by_day: pd.DataFrame
    by_dim: Dict[str, pd.DataFrame] = field(default_factory=dict)
    top: Dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def last_month_label(self) -> Optional[str]:
        if not self.months:
            return None
        return month_short(self.months[-1])


def summarize_months(frame: pd.DataFrame) -> pd.DataFrame:
    period = frame["date"].dt.to_period("M")
    grouped = frame.groupby(period)
    out = pd.DataFrame({"revenue": grouped["amount"].sum(), "orders": grouped.size()})
    if "quantity" in frame.columns:
        out["quantity"] = grouped["quantity"].sum(min_count=1)
    out["avg_check"] = out["revenue"] / out["orders"]
    out["growth"] = out["revenue"].pct_change(fill_method=None)
    out = out.sort_index().reset_index().rename(columns={"date": "month"})
    out["label"] = out["month"].map(month_label)
    return out


def summarize_days(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(frame["date"].dt.normalize())
    out = pd.DataFrame({"revenue": grouped["amount"].sum(), "orders": grouped.size()})
    full_range = pd.date_range(frame["date"].min().normalize(), frame["date"].max().normalize(), freq="D")
    out = out.reindex(full_range, fill_value=0)
    out["avg_check"] = np.where(out["orders"] > 0, out["revenue"] / out["orders"].replace(0, np.nan), np.nan)
    out.index.name = "date"
    return out.reset_index()


def summarize_dimension(frame: pd.DataFrame, key: str, months: List[pd.Period]) -> pd.DataFrame:
    grouped = frame.groupby(key)
    out = pd.DataFrame({"revenue": grouped["amount"].sum(), "orders": grouped.size()})
    if "quantity" in frame.columns:
        out["quantity"] = grouped["quantity"].sum(min_count=1)
    out["avg_check"] = out["revenue"] / out["orders"]
    total = out["revenue"].sum()
    out["share"] = out["revenue"] / total if total else np.nan
    if len(months) >= 2:
        period = frame["date"].dt.to_period("M")
        last = frame.loc[period == months[-1]].groupby(key)["amount"].sum()
        prev = frame.loc[period == months[-2]].groupby(key)["amount"].sum()
        out["last_month"] = last.reindex(out.index).fillna(0.0)
        out["prev_month"] = prev.reindex(out.index).fillna(0.0)
        out["growth"] = np.where(out["prev_month"] > 0, out["last_month"] / out["prev_month"] - 1, np.nan)
    out = out.sort_values(["revenue", "orders"], ascending=[False, False]).reset_index()
    return out.rename(columns={key: "name"})


def top_with_other(frame: pd.DataFrame, top_n: int, columns: Optional[List[str]] = None, other_label: str = OTHER_LABEL) -> pd.DataFrame:
    columns = columns or ["name", "revenue", "orders", "share"]
    columns = [column for column in columns if column in frame.columns]
    head = frame[columns].head(top_n).copy()
    rest = frame.iloc[top_n:]
    if not rest.empty:
        other = {"name": other_label}
        for column in columns:
            if column != "name":
                other[column] = rest[column].sum()
        head = pd.concat([head, pd.DataFrame([other])[columns]], ignore_index=True)
    return head.reset_index(drop=True)


def build_report(frame: pd.DataFrame, config: Config) -> Report:
    by_month = summarize_months(frame)
    months = list(by_month["month"])
    revenue = float(frame["amount"].sum())
    orders = int(len(frame))
    growth = None
    growth_label = ""
    if len(months) >= 2:
        value = by_month["growth"].iloc[-1]
        growth = None if pd.isna(value) else float(value)
        growth_label = f"{month_short(months[-1])} к {month_short(months[-2])}"
    quantity = float(frame["quantity"].sum()) if "quantity" in frame.columns else None
    clients = int(frame["client"].nunique()) if "client" in frame.columns else None
    report = Report(
        data=frame,
        period_start=frame["date"].min(),
        period_end=frame["date"].max(),
        revenue=revenue,
        orders=orders,
        avg_check=revenue / orders if orders else 0.0,
        quantity=quantity,
        clients=clients,
        growth=growth,
        growth_label=growth_label,
        months=months,
        by_month=by_month,
        by_day=summarize_days(frame),
    )
    for key in DIMENSIONS:
        if key in frame.columns:
            report.by_dim[key] = summarize_dimension(frame, key, months)
            label = OTHER_LABEL if key == "category" else REST_LABEL
            report.top[key] = top_with_other(report.by_dim[key], config.top_n, other_label=label)
    return report
