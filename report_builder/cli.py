from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from . import __version__
from .cleaning import prepare
from .config import LABELS, ConfigError, load_config
from .formatting import fmt_date, fmt_int, fmt_money, fmt_pct, plural
from .metrics import build_report
from .readers import InputError, read_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m report_builder", description="Собирает отчёт Excel из выгрузок CSV и XLSX")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True, metavar="команда")
    build = commands.add_parser("build", help="собрать отчёт из выгрузок")
    build.add_argument("--input", "-i", nargs="+", required=True, metavar="ПУТЬ", help="файлы, папки или маски, например data/*.csv")
    build.add_argument("--config", "-c", metavar="config.yml", help="файл настроек (без него используются названия колонок по умолчанию)")
    build.add_argument("--out", "-o", default="report.xlsx", metavar="report.xlsx", help="куда сохранить отчёт")
    build.add_argument("--png", metavar="ПАПКА", help="дополнительно сохранить графики в PNG")
    build.add_argument("--quiet", "-q", action="store_true", help="не печатать подробности")
    sample = commands.add_parser("sample", help="сгенерировать демо-выгрузки")
    sample.add_argument("--out", "-o", default="data", metavar="ПАПКА", help="папка для файлов")
    sample.add_argument("--seed", type=int, default=42, help="зерно генератора")
    sample.add_argument("--rows", type=int, default=900, help="примерно строк на месяц")
    sample.add_argument("--start", metavar="ГГГГ-ММ", help="первый из трёх месяцев")
    return parser


def cmd_build(args: argparse.Namespace) -> int:
    from .excel import write_report

    def say(text: str = "") -> None:
        if not args.quiet:
            print(text)

    config = load_config(args.config)
    sources = read_sources(args.input, config.sheet)
    say("Файлы:")
    for source in sources:
        say(f"  {source.describe()}")
    frame, stats = prepare(sources, config)
    say("Колонки:")
    for name, mapping in stats.mappings.items():
        pairs = ", ".join(f"{LABELS[key]} ← {column}" for key, column in mapping.items())
        say(f"  {name}: {pairs}")
    if stats.missing:
        say(f"  не найдены: {', '.join(LABELS[key] for key in stats.missing)} — соответствующие разделы пропущены")
    say(
        f"Очистка: {fmt_int(stats.rows_in)} → {fmt_int(stats.rows_out)} строк "
        f"(пустых {stats.empty}, без даты {stats.bad_date}, без суммы {stats.bad_amount}, дубликатов {stats.duplicates}"
        + (f", отрицательных {stats.negative}" if stats.negative else "")
        + ")"
    )
    report = build_report(frame, config)
    info = write_report(report, config, stats, sources, Path(args.out))
    say(f"Период: {fmt_date(report.period_start)} — {fmt_date(report.period_end)}")
    growth = fmt_pct(report.growth) + (f" ({report.growth_label})" if report.growth_label else "")
    say(
        f"Выручка {fmt_money(report.revenue, config.currency)} · заказов {fmt_int(report.orders)} · "
        f"средний чек {fmt_money(report.avg_check, config.currency)} · рост к прошлому месяцу {growth}"
    )
    say(f"Готово: {info.path} — {plural(len(info.sheets), 'лист', 'листа', 'листов')}, {plural(info.charts, 'диаграмма', 'диаграммы', 'диаграмм')}")
    if args.png:
        from .charts_png import save_charts

        written = save_charts(report, config, Path(args.png))
        say(f"PNG: {args.png} — {plural(len(written), 'файл', 'файла', 'файлов')}")
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    from .sample import generate_sample

    start = None
    if args.start:
        try:
            year, month = args.start.split("-")
            start = date(int(year), int(month), 1)
        except ValueError:
            raise InputError("Параметр --start задаётся как ГГГГ-ММ, например 2026-07")
    written = generate_sample(Path(args.out), seed=args.seed, rows_per_month=args.rows, start=start)
    print("Демо-выгрузки:")
    for path in written:
        print(f"  {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            return cmd_build(args)
        return cmd_sample(args)
    except (ConfigError, InputError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Ошибка: файл не найден — {exc.filename or exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"Ошибка: нет доступа к файлу {exc.filename or exc} (возможно, он открыт в Excel)", file=sys.stderr)
        return 2
