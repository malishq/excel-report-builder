from __future__ import annotations

import math
from typing import Optional

import pandas as pd

MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return value is pd.NaT


def group_digits(value: float, decimals: int = 0) -> str:
    text = f"{abs(float(value)):,.{decimals}f}"
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", " ")
    return ("-" if value < 0 else "") + text


def fmt_money(value, currency: str = "₽", decimals: int = 0) -> str:
    if is_missing(value):
        return "—"
    return f"{group_digits(value, decimals)} {currency}".strip()


def fmt_int(value) -> str:
    if is_missing(value):
        return "—"
    return group_digits(round(float(value)))


def fmt_compact(value, currency: str = "") -> str:
    if is_missing(value):
        return "—"
    size = abs(float(value))
    if size >= 1e9:
        text = trim_decimal(value / 1e9) + " млрд"
    elif size >= 1e6:
        text = trim_decimal(value / 1e6) + " млн"
    elif size >= 1e4:
        text = trim_decimal(value / 1e3, 0) + " тыс."
    else:
        text = group_digits(value)
    return f"{text} {currency}".strip()


def trim_decimal(number: float, decimals: int = 1) -> str:
    text = f"{number:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def fmt_pct(value, signed: bool = True, decimals: int = 1) -> str:
    if is_missing(value):
        return "—"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{float(value) * 100:.{decimals}f}".replace(".", ",") + " %"


def fmt_date(value) -> str:
    if is_missing(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


def month_label(period) -> str:
    period = pd.Period(period, freq="M")
    return f"{MONTHS[period.month - 1]} {period.year}"


def month_short(period) -> str:
    period = pd.Period(period, freq="M")
    return f"{MONTHS_SHORT[period.month - 1]}. {period.year}"


def plural(count: int, one: str, few: str, many: str) -> str:
    count = abs(int(count))
    if count % 10 == 1 and count % 100 != 11:
        word = one
    elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        word = few
    else:
        word = many
    return f"{group_digits(count)} {word}"


def delimiter_name(delimiter: Optional[str]) -> str:
    names = {";": "точка с запятой", ",": "запятая", "\t": "табуляция"}
    if delimiter is None:
        return "—"
    return names.get(delimiter, repr(delimiter))
