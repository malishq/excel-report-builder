from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

MANAGERS = [
    ("Иванова Анна", 1.7),
    ("Петров Сергей", 1.4),
    ("Смирнова Ольга", 1.2),
    ("Кузнецов Дмитрий", 1.0),
    ("Соколова Мария", 0.9),
    ("Попов Алексей", 0.8),
    ("Лебедева Екатерина", 0.6),
    ("Новиков Игорь", 0.4),
]

CATEGORIES = [
    ("Смартфоны", (14990, 129990), 1.6),
    ("Ноутбуки", (44990, 189990), 1.1),
    ("Телевизоры", (24990, 159990), 0.8),
    ("Бытовая техника", (6990, 89990), 1.2),
    ("Аудио", (2490, 59990), 0.9),
    ("Аксессуары", (490, 7990), 2.4),
    ("Игровые консоли", (29990, 69990), 0.5),
    ("Фототехника", (19990, 219990), 0.3),
]

REGIONS = [
    ("Москва", 3.0),
    ("Санкт-Петербург", 1.8),
    ("Московская область", 1.4),
    ("Краснодарский край", 0.9),
    ("Свердловская область", 0.8),
    ("Новосибирская область", 0.7),
    ("Республика Татарстан", 0.7),
    ("Нижегородская область", 0.6),
    ("Самарская область", 0.5),
    ("Ростовская область", 0.5),
]

COMPANIES = [
    "Вектор", "Техносфера", "Альфа-Трейд", "Северный ветер", "Гарант", "Медиа-Лайн", "Прогресс",
    "Орион", "Цифра", "Контур", "Байт", "Логос", "Квант", "Мегаполис", "Спектр", "Эталон", "Фокус",
    "Апогей", "Импульс", "Ресурс", "Атлант", "Синтез", "Формат", "Горизонт", "Первый склад",
]
PERSONS = [
    "Смирнов А. В.", "Волкова Е. С.", "Козлов И. Н.", "Морозова Т. П.", "Зайцев К. Д.", "Павлова Н. А.",
    "Семёнов Р. О.", "Голубева Ю. В.", "Виноградов П. С.", "Богданова Л. И.", "Воробьёв М. Е.", "Фёдорова А. Р.",
]

QUANTITY_WEIGHTS = [(1, 70), (2, 17), (3, 8), (4, 3), (5, 2)]
WEEKDAY_FACTOR = [1.0, 1.05, 1.0, 1.05, 1.15, 0.55, 0.4]


@dataclass
class FileSpec:
    name: str
    encoding: str
    delimiter: str
    headers: Tuple[str, ...]
    order: Tuple[str, ...]
    date_format: str
    amount_style: str
    growth: float


FILE_SPECS = [
    FileSpec(
        name="sales_{month}.csv",
        encoding="cp1251",
        delimiter=";",
        headers=("Дата", "Клиент", "Менеджер", "Категория", "Регион", "Количество", "Сумма"),
        order=("date", "client", "manager", "category", "region", "quantity", "amount"),
        date_format="%d.%m.%Y",
        amount_style="ru_spaces",
        growth=1.0,
    ),
    FileSpec(
        name="sales_{month}.csv",
        encoding="utf-8",
        delimiter="\t",
        headers=("Дата заказа", "Контрагент", "Категория товара", "Кол-во", "Сумма, руб", "Менеджер", "Регион"),
        order=("date", "client", "category", "quantity", "amount", "manager", "region"),
        date_format="%d.%m.%Y %H:%M",
        amount_style="ru_comma",
        growth=1.07,
    ),
    FileSpec(
        name="sales_{month}.csv",
        encoding="utf-8-sig",
        delimiter=",",
        headers=("date", "manager", "region", "client", "category", "qty", "amount"),
        order=("date", "manager", "region", "client", "category", "quantity", "amount"),
        date_format="%Y-%m-%d",
        amount_style="plain",
        growth=1.16,
    ),
]


def weighted_choice(rng: random.Random, items: Sequence[Tuple]) -> Tuple:
    weights = [item[-1] for item in items]
    return rng.choices(items, weights=weights, k=1)[0]


def retail_price(rng: random.Random, low: int, high: int) -> int:
    base = rng.randint(low, high)
    return max(low, round(base / 1000) * 1000 - 10)


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def default_start(today: Optional[date] = None, months: int = 3) -> date:
    today = today or date.today()
    return add_months(month_start(today), -months)


def build_clients(rng: random.Random) -> List[Tuple[str, float]]:
    clients = [(f"ООО «{name}»", rng.uniform(0.4, 2.0)) for name in COMPANIES]
    clients += [(f"ИП {person}", rng.uniform(0.2, 0.9)) for person in PERSONS]
    return clients


def format_amount(value: float, style: str) -> str:
    if style == "plain":
        return f"{value:.2f}"
    whole = f"{int(value):,}".replace(",", " ")
    cents = f"{value - int(value):.2f}".split(".")[1]
    if style == "ru_spaces":
        return f"{whole},{cents}"
    return f"{int(value)},{cents}"


def generate_month(rng: random.Random, start: date, spec: FileSpec, rows_target: int, clients) -> List[dict]:
    end = add_months(start, 1)
    rows = []
    day = start
    while day < end:
        factor = WEEKDAY_FACTOR[day.weekday()] * spec.growth
        count = max(0, int(round(rng.gauss(rows_target / 30 * factor, 4))))
        for _ in range(count):
            category = weighted_choice(rng, CATEGORIES)
            quantity = weighted_choice(rng, QUANTITY_WEIGHTS)[0]
            amount = retail_price(rng, *category[1]) * quantity
            moment = datetime(day.year, day.month, day.day, rng.randint(9, 20), rng.randint(0, 59))
            rows.append({
                "date": moment,
                "client": weighted_choice(rng, clients)[0],
                "manager": weighted_choice(rng, MANAGERS)[0],
                "category": category[0],
                "region": weighted_choice(rng, REGIONS)[0],
                "quantity": quantity,
                "amount": float(amount),
            })
        day += timedelta(days=1)
    return rows


def render_rows(rng: random.Random, rows: List[dict], spec: FileSpec) -> List[List[str]]:
    rendered = []
    for row in rows:
        values = []
        for key in spec.order:
            value = row[key]
            if key == "date":
                text = value.strftime(spec.date_format)
            elif key == "amount":
                text = format_amount(value, spec.amount_style)
                roll = rng.random()
                if spec.encoding == "cp1251" and roll < 0.03:
                    text += " руб."
                elif spec.encoding != "cp1251" and roll < 0.03:
                    text += " ₽"
            elif key == "quantity":
                text = str(value)
            else:
                text = str(value)
                if rng.random() < 0.02:
                    text = "  " + text + " "
            values.append(text)
        rendered.append(values)
    duplicates = max(1, len(rendered) // 100)
    for _ in range(duplicates):
        rendered.insert(rng.randrange(len(rendered)), list(rng.choice(rendered)))
    for _ in range(max(1, len(rendered) // 250)):
        rendered.insert(rng.randrange(len(rendered)), [""] * len(spec.order))
    broken = list(rng.choice(rendered))
    while not any(broken):
        broken = list(rng.choice(rendered))
    broken[spec.order.index("date")] = "дата уточняется"
    rendered.insert(rng.randrange(len(rendered)), broken)
    return rendered


def write_csv(path: Path, headers: Sequence[str], rows: List[List[str]], encoding: str, delimiter: str) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding=encoding)


def generate_sample(out_dir: Path, seed: int = 42, rows_per_month: int = 900, start: Optional[date] = None) -> List[Path]:
    rng = random.Random(seed)
    start = start or default_start()
    out_dir.mkdir(parents=True, exist_ok=True)
    clients = build_clients(rng)
    written = []
    for index, spec in enumerate(FILE_SPECS):
        month = add_months(start, index)
        rows = generate_month(rng, month, spec, rows_per_month, clients)
        rendered = render_rows(rng, rows, spec)
        path = out_dir / spec.name.format(month=month.strftime("%Y-%m"))
        write_csv(path, spec.headers, rendered, spec.encoding, spec.delimiter)
        written.append(path)
    return written
