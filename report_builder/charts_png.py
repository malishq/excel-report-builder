from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

from .config import Config
from .formatting import fmt_compact, fmt_date
from .metrics import OTHER_LABEL, OTHER_LABELS, Report

ACCENT = "#2a78d6"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#ffffff"
OTHER_COLOR = "#c3c2b7"
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
DARK_LABEL_ON = {"#eda100"}


def setup_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 11,
        "text.color": INK,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": False,
        "legend.fontsize": 10,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.dpi": 160,
        "savefig.facecolor": SURFACE,
    })


def style_axes(ax, axis: str = "y") -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.spines["left" if axis == "y" else "bottom"].set_visible(False)


def compact_formatter():
    return FuncFormatter(lambda value, _: fmt_compact(value) if value else "0")


def titles(fig, title: str, note: str) -> None:
    fig.text(0.04, 0.955, title, fontsize=15, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.04, 0.895, note, fontsize=10, color=MUTED, ha="left", va="top")


def finish(fig, path: Path) -> None:
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path)
    plt.close(fig)


def period_text(report: Report) -> str:
    return f"{fmt_date(report.period_start)} — {fmt_date(report.period_end)}"


def chart_months(report: Report, config: Config, path: Path) -> None:
    frame = report.by_month
    fig, ax = plt.subplots(figsize=(10, 5.4))
    positions = np.arange(len(frame))
    values = frame["revenue"].to_numpy(dtype=float)
    ax.bar(positions, values, width=0.5, color=ACCENT, zorder=3)
    ax.set_xticks(positions)
    ax.set_xticklabels(frame["label"])
    style_axes(ax)
    ax.yaxis.set_major_formatter(compact_formatter())
    top = float(values.max()) if len(values) else 1.0
    ax.set_ylim(0, top * 1.18)
    if len(values) <= 8:
        labelled = set(range(len(values)))
    else:
        labelled = {int(values.argmax()), len(values) - 1}
    for index in labelled:
        ax.annotate(fmt_compact(values[index], config.currency), (positions[index], values[index]), xytext=(0, 6), textcoords="offset points", ha="center", color=INK_SECONDARY, fontsize=10)
    titles(fig, "Выручка по месяцам", f"Период {period_text(report)}, {config.currency}")
    finish(fig, path)


def chart_categories(report: Report, config: Config, path: Path) -> None:
    top = report.top["category"]
    names = list(top["name"])
    values = top["revenue"].to_numpy(dtype=float)
    shares = values / values.sum() if values.sum() else values
    colors = [OTHER_COLOR if name in OTHER_LABELS else PALETTE[index % len(PALETTE)] for index, name in enumerate(names)]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False, wedgeprops={"linewidth": 2, "edgecolor": SURFACE}, radius=1.0)
    ax.set_position([0.02, 0.02, 0.56, 0.8])
    for wedge, share, color in zip(wedges, shares, colors):
        if share < 0.05:
            continue
        angle = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
        label_color = INK if color in DARK_LABEL_ON or color == OTHER_COLOR else SURFACE
        ax.text(0.66 * np.cos(angle), 0.66 * np.sin(angle), f"{share * 100:.0f} %", ha="center", va="center", color=label_color, fontsize=10, fontweight="bold")
    legend_labels = [f"{name} — {fmt_compact(value, config.currency)}" for name, value in zip(names, values)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.02, 0.5), handlelength=1.2, borderaxespad=0)
    ax.set_aspect("equal")
    titles(fig, "Доля категорий в выручке", f"Топ-{config.top_n} категорий, остальные объединены в «{OTHER_LABEL}»")
    fig.savefig(path)
    plt.close(fig)


def chart_days(report: Report, config: Config, path: Path) -> None:
    days = report.by_day
    dates = days["date"]
    values = days["revenue"].to_numpy(dtype=float)
    rolling = days["revenue"].rolling(7, min_periods=1).mean().to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.plot(dates, values, color=BASELINE, linewidth=1.2, label="Выручка за день", zorder=2)
    ax.plot(dates, rolling, color=ACCENT, linewidth=2.2, label="Среднее за 7 дней", zorder=3, solid_capstyle="round")
    if len(values):
        peak = int(values.argmax())
        ax.scatter([dates.iloc[peak]], [values[peak]], s=60, color=ACCENT, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.annotate(f"пик {fmt_date(dates.iloc[peak])}: {fmt_compact(values[peak], config.currency)}", (dates.iloc[peak], values[peak]), xytext=(8, 4), textcoords="offset points", color=INK_SECONDARY, fontsize=10)
        ax.set_ylim(0, float(values.max()) * 1.2)
    style_axes(ax)
    ax.yaxis.set_major_formatter(compact_formatter())
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.legend(loc="upper left", ncol=2)
    titles(fig, "Выручка по дням", f"Период {period_text(report)}, {config.currency}")
    finish(fig, path)


def chart_managers(report: Report, config: Config, path: Path) -> None:
    frame = report.by_dim["manager"].head(10).iloc[::-1]
    names = list(frame["name"])
    values = frame["revenue"].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, 5.4))
    positions = np.arange(len(frame))
    ax.barh(positions, values, height=0.55, color=ACCENT, zorder=3)
    ax.set_yticks(positions)
    ax.set_yticklabels(names)
    style_axes(ax, axis="x")
    ax.xaxis.set_major_formatter(compact_formatter())
    top = float(values.max()) if len(values) else 1.0
    ax.set_xlim(0, top * 1.22)
    for position, value in zip(positions, values):
        ax.annotate(fmt_compact(value, config.currency), (value, position), xytext=(6, 0), textcoords="offset points", va="center", color=INK_SECONDARY, fontsize=10)
    titles(fig, "Выручка по менеджерам", f"Топ-{len(frame)} за период {period_text(report)}, {config.currency}")
    finish(fig, path)


def save_charts(report: Report, config: Config, out_dir: Path) -> List[Path]:
    setup_style()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [("01_revenue_by_month.png", chart_months)]
    if "category" in report.top:
        jobs.append(("02_categories_share.png", chart_categories))
    jobs.append(("03_daily_revenue.png", chart_days))
    if "manager" in report.by_dim:
        jobs.append(("04_managers.png", chart_managers))
    written = []
    for name, job in jobs:
        path = out_dir / name
        job(report, config, path)
        written.append(path)
    return written
