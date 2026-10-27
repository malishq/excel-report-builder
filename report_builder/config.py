from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

FIELDS = ("date", "amount", "quantity", "manager", "category", "region", "client")
REQUIRED = ("date", "amount")
LABELS = {
    "date": "Дата",
    "amount": "Сумма",
    "quantity": "Количество",
    "manager": "Менеджер",
    "category": "Категория",
    "region": "Регион",
    "client": "Клиент",
}

DEFAULT_DATE_FORMATS = [
    "%d.%m.%Y",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d.%m.%y",
]

DEFAULTS: Dict[str, Any] = {
    "columns": {
        "date": ["Дата", "Дата заказа", "Дата продажи", "Дата документа", "date", "order_date"],
        "amount": ["Сумма", "Сумма, руб", "Сумма заказа", "Сумма продажи", "Выручка", "amount", "total", "sum"],
        "quantity": ["Количество", "Кол-во", "Кол-во, шт", "Количество, шт", "qty", "quantity"],
        "manager": ["Менеджер", "Продавец", "Ответственный", "manager", "seller"],
        "category": ["Категория", "Категория товара", "Группа товаров", "Группа", "category"],
        "region": ["Регион", "Область", "Город", "region", "city"],
        "client": ["Клиент", "Покупатель", "Контрагент", "client", "customer"],
    },
    "report": {
        "title": "Отчёт по продажам",
        "currency": "₽",
        "top_n": 5,
    },
    "cleaning": {
        "drop_duplicates": True,
        "drop_negative": False,
        "date_formats": DEFAULT_DATE_FORMATS,
    },
    "input": {
        "sheet": 0,
    },
}


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    columns: Dict[str, List[str]] = field(default_factory=dict)
    title: str = "Отчёт по продажам"
    currency: str = "₽"
    top_n: int = 5
    drop_duplicates: bool = True
    drop_negative: bool = False
    date_formats: List[str] = field(default_factory=lambda: list(DEFAULT_DATE_FORMATS))
    sheet: Any = 0
    source: Optional[Path] = None

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]], source: Optional[Path] = None) -> "Config":
        merged = copy.deepcopy(DEFAULTS)
        raw = raw or {}
        if not isinstance(raw, dict):
            raise ConfigError("Файл настроек должен содержать словарь с ключами columns, report, cleaning, input")
        for section in ("columns", "report", "cleaning", "input"):
            value = raw.get(section)
            if value is None:
                continue
            if not isinstance(value, dict):
                raise ConfigError(f"Раздел «{section}» в настройках должен быть словарём")
            if section == "columns":
                merged[section] = value
            else:
                merged[section].update(value)
        unknown = [key for key in raw if key not in ("columns", "report", "cleaning", "input")]
        if unknown:
            raise ConfigError(f"Неизвестные разделы в настройках: {', '.join(unknown)}")
        columns: Dict[str, List[str]] = {}
        for key, aliases in merged["columns"].items():
            if key not in FIELDS:
                raise ConfigError(f"Неизвестное поле «{key}» в columns. Допустимые: {', '.join(FIELDS)}")
            if aliases is None:
                continue
            if isinstance(aliases, str):
                aliases = [aliases]
            if not isinstance(aliases, (list, tuple)):
                raise ConfigError(f"Для поля «{key}» нужен список названий колонок")
            columns[key] = [str(alias) for alias in aliases]
        for key in REQUIRED:
            if not columns.get(key):
                raise ConfigError(f"В columns обязательно поле «{key}»")
        report = merged["report"]
        cleaning = merged["cleaning"]
        try:
            top_n = int(report.get("top_n", 5))
        except (TypeError, ValueError):
            raise ConfigError("report.top_n должно быть целым числом")
        if top_n < 1:
            raise ConfigError("report.top_n должно быть не меньше 1")
        formats = cleaning.get("date_formats") or DEFAULT_DATE_FORMATS
        if isinstance(formats, str):
            formats = [formats]
        return cls(
            columns=columns,
            title=str(report.get("title") or DEFAULTS["report"]["title"]),
            currency=str(report.get("currency", "₽")),
            top_n=top_n,
            drop_duplicates=bool(cleaning.get("drop_duplicates", True)),
            drop_negative=bool(cleaning.get("drop_negative", False)),
            date_formats=[str(fmt) for fmt in formats],
            sheet=merged["input"].get("sheet", 0),
            source=source,
        )


def load_config(path: Optional[str] = None) -> Config:
    if path is None:
        return Config.from_dict(None)
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigError(f"Файл настроек не найден: {file_path}")
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Не удалось прочитать {file_path}: {exc}")
    return Config.from_dict(raw, source=file_path)
