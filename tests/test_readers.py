import csv
import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from report_builder.readers import InputError, detect_delimiter, detect_encoding, expand_inputs, read_source, read_sources

ROWS = [
    ["Дата", "Сумма", "Менеджер"],
    ["01.07.2026", "12 500,00", "Иванова Анна"],
    ["02.07.2026", "3 990,00", "Петров Сергей"],
]


def write_csv(path, delimiter, encoding):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerows(ROWS)
    path.write_text(buffer.getvalue(), encoding=encoding)


@pytest.mark.parametrize("delimiter,encoding", [(";", "cp1251"), (",", "utf-8-sig"), ("\t", "utf-8"), (";", "utf-8")])
def test_csv_autodetect(tmp_path, delimiter, encoding):
    path = tmp_path / "sales.csv"
    write_csv(path, delimiter, encoding)
    source = read_source(path)
    assert source.delimiter == delimiter
    assert source.encoding == encoding
    assert list(source.frame.columns) == ROWS[0]
    assert source.frame.iloc[0].tolist() == ROWS[1]
    assert source.rows == 2


def test_detect_encoding_prefers_utf8_over_cp1251():
    assert detect_encoding("Дата;Сумма".encode("utf-8")) == "utf-8"
    assert detect_encoding("Дата;Сумма".encode("cp1251")) == "cp1251"
    assert detect_encoding(b"\xef\xbb\xbfdate,amount") == "utf-8-sig"


def test_detect_delimiter_ignores_decimal_commas():
    text = "Дата;Сумма\n01.07.2026;12 500,00\n02.07.2026;3 990,50\n"
    assert detect_delimiter(text) == ";"
    assert detect_delimiter("a\tb\n1\t2\n") == "\t"
    assert detect_delimiter("date,amount\n2026-07-01,12500.00\n") == ","


def test_read_xlsx(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Дата", "Сумма", "Клиент"])
    sheet.append([datetime(2026, 7, 3), 12500.5, "ООО «Вектор»"])
    sheet.append([datetime(2026, 7, 4), 300, None])
    path = tmp_path / "export.xlsx"
    workbook.save(path)
    source = read_source(path)
    assert source.encoding is None
    assert list(source.frame.columns) == ["Дата", "Сумма", "Клиент"]
    assert source.frame.iloc[0]["Сумма"] == "12500.5"
    assert source.frame.iloc[1]["Клиент"] == ""
    assert "Excel" in source.describe()


def test_expand_inputs_accepts_files_globs_and_folders(tmp_path):
    for name in ("b.csv", "a.csv", "notes.txt.bak"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    folder = tmp_path / "more"
    folder.mkdir()
    (folder / "c.xlsx").write_bytes(b"")
    found = expand_inputs([str(tmp_path / "*.csv"), str(folder), str(tmp_path / "a.csv")])
    assert [path.name for path in found] == ["a.csv", "b.csv", "c.xlsx"]
    with pytest.raises(InputError):
        expand_inputs([str(tmp_path / "missing*.csv")])


def test_read_sources_rejects_unknown_format(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(InputError):
        read_sources([str(path)])
