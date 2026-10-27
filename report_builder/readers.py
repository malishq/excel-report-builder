from __future__ import annotations

import csv
import glob
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import pandas as pd

from .formatting import delimiter_name, plural

ENCODINGS = ("utf-8-sig", "utf-8", "cp1251")
DELIMITERS = (";", ",", "\t")
CSV_SUFFIXES = {".csv", ".txt", ".tsv"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}


class InputError(ValueError):
    pass


@dataclass
class SourceFile:
    path: Path
    frame: pd.DataFrame
    encoding: Optional[str] = None
    delimiter: Optional[str] = None

    @property
    def rows(self) -> int:
        return len(self.frame)

    def describe(self) -> str:
        if self.encoding is None:
            kind = "Excel"
        else:
            kind = f"{self.encoding}, разделитель: {delimiter_name(self.delimiter)}"
        return f"{self.path.name} — {kind}, {plural(self.rows, 'строка', 'строки', 'строк')}"


def expand_inputs(patterns: Sequence[str]) -> List[Path]:
    found: List[Path] = []
    for pattern in patterns:
        path = Path(pattern).expanduser()
        if path.is_dir():
            candidates = sorted(p for p in path.iterdir() if p.suffix.lower() in CSV_SUFFIXES | EXCEL_SUFFIXES)
        elif path.is_file():
            candidates = [path]
        else:
            candidates = sorted(Path(p) for p in glob.glob(str(path)))
        if not candidates:
            raise InputError(f"Ничего не найдено по пути «{pattern}»")
        for candidate in candidates:
            if candidate.is_file() and candidate not in found and not candidate.name.startswith("~$"):
                found.append(candidate)
    return found


def detect_encoding(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp1251"):
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "cp1251"


def detect_delimiter(text: str, candidates: Sequence[str] = DELIMITERS) -> str:
    lines = [line for line in text.splitlines() if line.strip()][:50]
    if not lines:
        return candidates[0]
    best = candidates[0]
    best_key: Optional[Tuple[bool, bool, int]] = None
    for delimiter in candidates:
        counts = []
        for line in lines:
            fields = next(csv.reader([line], delimiter=delimiter))
            counts.append(len(fields) - 1)
        key = (min(counts) > 0, max(counts) == min(counts), min(counts))
        if best_key is None or key > best_key:
            best, best_key = delimiter, key
    return best


def read_csv_bytes(data: bytes) -> Tuple[pd.DataFrame, str, str]:
    encoding = detect_encoding(data)
    text = data.decode(encoding, errors="replace")
    delimiter = detect_delimiter(text)
    frame = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=True,
        engine="python",
    )
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame, encoding, delimiter


def read_excel_file(path: Path, sheet: Any = 0) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False, engine="openpyxl")
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def read_source(path: Path, sheet: Any = 0) -> SourceFile:
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        return SourceFile(path=path, frame=read_excel_file(path, sheet))
    if suffix in CSV_SUFFIXES:
        frame, encoding, delimiter = read_csv_bytes(path.read_bytes())
        return SourceFile(path=path, frame=frame, encoding=encoding, delimiter=delimiter)
    raise InputError(f"Неподдерживаемый формат файла: {path.name} (нужен CSV или XLSX)")


def read_sources(patterns: Sequence[str], sheet: Any = 0) -> List[SourceFile]:
    paths = expand_inputs(patterns)
    return [read_source(path, sheet) for path in paths]
