from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from .config import FIELDS, LABELS, REQUIRED, Config, ConfigError
from .readers import SourceFile

EMPTY_TEXT = "Не указано"
TEXT_FIELDS = ("manager", "category", "region", "client")
SPACES_RE = re.compile(r"\s+")
AMOUNT_JUNK_RE = re.compile(r"[^\d,.\-]")
EDGE_JUNK_RE = re.compile(r"^[^\d]+|[^\d]+$")
SERIAL_RE = re.compile(r"^\d{5}(\.\d+)?$")


@dataclass
class CleanStats:
    rows_in: int = 0
    empty: int = 0
    bad_date: int = 0
    bad_amount: int = 0
    negative: int = 0
    duplicates: int = 0
    rows_out: int = 0
    mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)

    @property
    def dropped(self) -> int:
        return self.empty + self.bad_date + self.bad_amount + self.negative + self.duplicates


def normalize_header(name) -> str:
    text = str(name).replace("﻿", "")
    return SPACES_RE.sub(" ", text).strip().lower()


def map_columns(columns: Sequence[str], config: Config) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for column in columns:
        lookup.setdefault(normalize_header(column), column)
    mapping: Dict[str, str] = {}
    for key in FIELDS:
        for alias in config.columns.get(key, []):
            source = lookup.get(normalize_header(alias))
            if source is not None:
                mapping[key] = source
                break
    missing = [key for key in REQUIRED if key not in mapping]
    if missing:
        wanted = "; ".join(f"{LABELS[key]}: {', '.join(config.columns.get(key, []))}" for key in missing)
        raise ConfigError(
            f"Не найдены обязательные колонки ({wanted}). "
            f"Колонки в файле: {', '.join(str(c) for c in columns)}. "
            "Добавьте нужное название в раздел columns файла настроек."
        )
    return mapping


def parse_amount(value) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).strip()
    if not text:
        return math.nan
    text = text.replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = EDGE_JUNK_RE.sub("", text)
    text = AMOUNT_JUNK_RE.sub("", text).replace("-", "")
    if not text:
        return math.nan
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            text = parts[0] + "." + parts[1]
        else:
            text = "".join(parts)
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        number = float(text)
    except ValueError:
        return math.nan
    return -number if negative else number


def parse_amounts(series: pd.Series) -> pd.Series:
    text = series.astype(str)
    unique = {value: parse_amount(value) for value in text.unique()}
    return text.map(unique).astype(float)


def parse_dates(series: pd.Series, formats: Sequence[str]) -> pd.Series:
    text = series.astype(str).str.strip()
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in formats:
        pending = result.isna() & (text != "")
        if not pending.any():
            break
        parsed = pd.to_datetime(text[pending], format=fmt, errors="coerce")
        result.loc[pending] = parsed
    pending = result.isna() & text.str.match(SERIAL_RE)
    if pending.any():
        serial = pd.to_numeric(text[pending], errors="coerce")
        result.loc[pending] = pd.to_datetime(serial, unit="D", origin="1899-12-30", errors="coerce")
    pending = result.isna() & (text != "")
    if pending.any():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result.loc[pending] = pd.to_datetime(text[pending], errors="coerce", dayfirst=True)
    return result.dt.normalize()


def normalize_text(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.replace(SPACES_RE, " ", regex=True).str.strip()
    return text.where(text != "", EMPTY_TEXT)


def select_columns(source: SourceFile, config: Config) -> Tuple[pd.DataFrame, Dict[str, str]]:
    mapping = map_columns(list(source.frame.columns), config)
    part = source.frame[[mapping[key] for key in mapping]].copy()
    part.columns = list(mapping.keys())
    part["source"] = source.path.name
    return part, mapping


def prepare(sources: Sequence[SourceFile], config: Config) -> Tuple[pd.DataFrame, CleanStats]:
    if not sources:
        raise ConfigError("Нет входных файлов")
    stats = CleanStats()
    parts = []
    for source in sources:
        part, mapping = select_columns(source, config)
        stats.mappings[source.path.name] = mapping
        parts.append(part)
    frame = pd.concat(parts, ignore_index=True, sort=False)
    stats.rows_in = len(frame)
    fields = [key for key in FIELDS if key in frame.columns]
    stats.missing = [key for key in FIELDS if key not in frame.columns]
    for key in fields:
        frame[key] = frame[key].fillna("").astype(str).str.strip()
    empty = (frame[fields] == "").all(axis=1)
    stats.empty = int(empty.sum())
    frame = frame.loc[~empty].copy()
    frame["date"] = parse_dates(frame["date"], config.date_formats)
    bad_date = frame["date"].isna()
    stats.bad_date = int(bad_date.sum())
    frame = frame.loc[~bad_date].copy()
    frame["amount"] = parse_amounts(frame["amount"])
    bad_amount = frame["amount"].isna()
    stats.bad_amount = int(bad_amount.sum())
    frame = frame.loc[~bad_amount].copy()
    if config.drop_negative:
        negative = frame["amount"] < 0
        stats.negative = int(negative.sum())
        frame = frame.loc[~negative].copy()
    if "quantity" in frame.columns:
        frame["quantity"] = parse_amounts(frame["quantity"])
    for key in TEXT_FIELDS:
        if key in frame.columns:
            frame[key] = normalize_text(frame[key])
    if config.drop_duplicates:
        duplicates = frame.duplicated(subset=fields)
        stats.duplicates = int(duplicates.sum())
        frame = frame.loc[~duplicates].copy()
    frame = frame.sort_values(["date", "source"], kind="stable").reset_index(drop=True)
    stats.rows_out = len(frame)
    if frame.empty:
        raise ConfigError("После очистки не осталось ни одной строки: проверьте форматы дат и сумм")
    return frame, stats
