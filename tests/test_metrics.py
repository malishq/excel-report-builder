import pandas as pd
import pytest

from report_builder.config import Config
from report_builder.metrics import OTHER_LABEL, REST_LABEL, build_report, top_with_other


def sample_frame():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01", "2026-07-03", "2026-08-01", "2026-08-01"]),
        "amount": [100.0, 200.0, 150.0, 450.0],
        "quantity": [1.0, 2.0, 1.0, 3.0],
        "manager": ["Анна", "Борис", "Анна", "Анна"],
        "category": ["Ноутбуки", "Аудио", "Ноутбуки", "Смартфоны"],
        "region": ["Москва", "Москва", "Казань", "Казань"],
        "client": ["К1", "К2", "К1", "К3"],
        "source": ["a.csv"] * 4,
    })


def test_kpis_and_growth():
    report = build_report(sample_frame(), Config.from_dict({"report": {"top_n": 1}}))
    assert report.revenue == 900.0
    assert report.orders == 4
    assert report.avg_check == 225.0
    assert report.quantity == 7.0
    assert report.clients == 3
    assert report.growth == pytest.approx(1.0)
    assert report.growth_label == "авг. 2026 к июл. 2026"
    assert report.period_start == pd.Timestamp("2026-07-01")
    assert report.period_end == pd.Timestamp("2026-08-01")


def test_by_month_and_by_day():
    report = build_report(sample_frame(), Config.from_dict(None))
    months = report.by_month
    assert months["label"].tolist() == ["Июль 2026", "Август 2026"]
    assert months["revenue"].tolist() == [300.0, 600.0]
    assert months["orders"].tolist() == [2, 2]
    assert pd.isna(months["growth"].iloc[0])
    assert months["growth"].iloc[1] == pytest.approx(1.0)
    days = report.by_day
    assert len(days) == 32
    assert days["revenue"].iloc[1] == 0
    assert days["orders"].iloc[0] == 1
    assert days["revenue"].sum() == 900.0


def test_dimensions_and_top():
    report = build_report(sample_frame(), Config.from_dict({"report": {"top_n": 1}}))
    managers = report.by_dim["manager"]
    assert managers["name"].tolist() == ["Анна", "Борис"]
    assert managers["revenue"].tolist() == [700.0, 200.0]
    assert managers["share"].iloc[0] == pytest.approx(700 / 900)
    assert managers["last_month"].tolist() == [600.0, 0.0]
    assert managers["prev_month"].tolist() == [100.0, 200.0]
    assert managers["growth"].iloc[0] == pytest.approx(5.0)
    assert managers["growth"].iloc[1] == pytest.approx(-1.0)
    top = report.top["manager"]
    assert top["name"].tolist() == ["Анна", REST_LABEL]
    assert top["revenue"].tolist() == [700.0, 200.0]
    categories = report.top["category"]
    assert categories["name"].tolist() == ["Смартфоны", OTHER_LABEL]
    assert categories["revenue"].tolist() == [450.0, 450.0]


def test_top_without_rest_row():
    frame = pd.DataFrame({"name": ["a", "b"], "revenue": [2.0, 1.0], "orders": [1, 1], "share": [0.7, 0.3]})
    assert top_with_other(frame, 5)["name"].tolist() == ["a", "b"]


def test_single_month_has_no_growth():
    frame = sample_frame().iloc[:2]
    report = build_report(frame.drop(columns=["quantity", "client"]), Config.from_dict(None))
    assert report.growth is None
    assert report.growth_label == ""
    assert report.quantity is None
    assert report.clients is None
    assert "growth" not in report.by_dim["manager"].columns
