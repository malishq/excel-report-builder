import math
from pathlib import Path

import pandas as pd
import pytest

from report_builder.cleaning import EMPTY_TEXT, map_columns, normalize_header, parse_amount, parse_dates, prepare
from report_builder.config import Config, ConfigError, load_config
from report_builder.readers import SourceFile


@pytest.mark.parametrize("raw,expected", [
    ("12 500,00", 12500.0),
    ("12500", 12500.0),
    ("1,234.50", 1234.5),
    ("1 234,5", 1234.5),
    ("49 990,00 руб.", 49990.0),
    ("12 500 ₽", 12500.0),
    ("5\xa0990,00", 5990.0),
    ("-300", -300.0),
    ("(1 200,50)", -1200.5),
    ("12.500,75", 12500.75),
    ("1.234.567", 1234567.0),
    (12500, 12500.0),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "   ", "abc", None, "руб."])
def test_parse_amount_invalid(raw):
    assert math.isnan(parse_amount(raw))


def test_parse_dates_mixed_formats():
    series = pd.Series(["01.07.2026", "2026-07-02", "03.07.2026 14:20", "04/07/2026", "2026-07-05 10:00:00", "45870", "дата уточняется", ""])
    parsed = parse_dates(series, Config().date_formats)
    assert parsed.iloc[0] == pd.Timestamp("2026-07-01")
    assert parsed.iloc[1] == pd.Timestamp("2026-07-02")
    assert parsed.iloc[2] == pd.Timestamp("2026-07-03")
    assert parsed.iloc[3] == pd.Timestamp("2026-07-04")
    assert parsed.iloc[4] == pd.Timestamp("2026-07-05")
    assert parsed.iloc[5] == pd.Timestamp("2025-08-01")
    assert pd.isna(parsed.iloc[6])
    assert pd.isna(parsed.iloc[7])


def test_map_columns_is_case_and_space_insensitive():
    config = Config.from_dict({"columns": {"date": "Дата заказа", "amount": ["Сумма, руб"], "manager": ["Менеджер"]}})
    mapping = map_columns(["﻿дата  заказа", "СУММА, РУБ", "Регион"], config)
    assert mapping == {"date": "﻿дата  заказа", "amount": "СУММА, РУБ"}
    assert normalize_header("  Сумма,   руб ") == "сумма, руб"


def test_map_columns_reports_missing_required():
    with pytest.raises(ConfigError) as error:
        map_columns(["Дата", "Менеджер"], Config.from_dict(None))
    assert "Сумма" in str(error.value)
    assert "Менеджер" in str(error.value)


def make_source(name, rows, columns):
    return SourceFile(path=Path(name), frame=pd.DataFrame(rows, columns=columns))


def test_prepare_cleans_and_merges():
    first = make_source("a.csv", [
        ["01.07.2026", "12 500,00", "  Иванова   Анна ", "Москва"],
        ["01.07.2026", "12 500,00", "Иванова Анна", "Москва"],
        ["", "", "", ""],
        ["02.07.2026", "", "Петров Сергей", "Москва"],
        ["нет даты", "100", "Петров Сергей", ""],
    ], ["Дата", "Сумма", "Менеджер", "Регион"])
    second = make_source("b.csv", [
        ["2026-08-01", "990.50", "Смирнова Ольга", ""],
        ["2026-08-02", "-200", "Смирнова Ольга", "Казань"],
    ], ["date", "amount", "manager", "region"])
    frame, stats = prepare([first, second], Config.from_dict(None))
    assert stats.rows_in == 7
    assert stats.empty == 1
    assert stats.bad_date == 1
    assert stats.bad_amount == 1
    assert stats.duplicates == 1
    assert stats.rows_out == 3
    assert stats.missing == ["quantity", "category", "client"]
    assert stats.mappings["b.csv"]["amount"] == "amount"
    assert frame["manager"].tolist() == ["Иванова Анна", "Смирнова Ольга", "Смирнова Ольга"]
    assert frame["region"].tolist() == ["Москва", EMPTY_TEXT, "Казань"]
    assert frame["amount"].tolist() == [12500.0, 990.5, -200.0]
    assert frame["source"].tolist() == ["a.csv", "b.csv", "b.csv"]
    assert str(frame["date"].dtype).startswith("datetime64")


def test_prepare_can_drop_negative_and_keep_duplicates():
    source = make_source("a.csv", [
        ["01.07.2026", "100"],
        ["01.07.2026", "100"],
        ["02.07.2026", "-50"],
    ], ["Дата", "Сумма"])
    config = Config.from_dict({"cleaning": {"drop_duplicates": False, "drop_negative": True}})
    frame, stats = prepare([source], config)
    assert len(frame) == 2
    assert stats.negative == 1
    assert stats.duplicates == 0


def test_prepare_fails_when_nothing_left():
    source = make_source("a.csv", [["x", "y"]], ["Дата", "Сумма"])
    with pytest.raises(ConfigError):
        prepare([source], Config.from_dict(None))


def test_load_config_and_errors(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("columns:\n  date: [Дата]\n  amount: [Сумма]\nreport:\n  title: Продажи\n  top_n: 3\n", encoding="utf-8")
    config = load_config(str(path))
    assert config.title == "Продажи"
    assert config.top_n == 3
    assert config.columns["date"] == ["Дата"]
    assert config.currency == "₽"
    with pytest.raises(ConfigError):
        Config.from_dict({"columns": {"price": ["Цена"]}})
    with pytest.raises(ConfigError):
        Config.from_dict({"columns": {"date": ["Дата"]}})
    with pytest.raises(ConfigError):
        Config.from_dict({"report": {"top_n": "много"}})
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "missing.yml"))
