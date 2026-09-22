"""Общие валидаторы справочников (Этап 5, F12–F14/F07).

Единый контракт:
- даты — строго ISO ``YYYY-MM-DD`` (канонические; ``YYYYMMDD`` и ``2026-1-1``
  отклоняются, а не нормализуются молча — иначе строковое сравнение в SQLite
  расходится с календарной датой, F13);
- деньги — HALF_UP до копеек везде (устраняет расхождение TOML ``int(x*100)``
  против ``set_pay_settings``, F12); конечность/диапазон/вместимость INTEGER;
- структура TOML — списки словарей; ошибки полем, а не TypeError (F12).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from core.money import as_decimal, quantize_money

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

#: SQLite INTEGER — знаковый 64-бит.
SQLITE_INT_MAX = 9223372036854775807


def normalize_date(value: object) -> str:
    """Проверить и вернуть каноническую дату ``YYYY-MM-DD``.

    Отклоняет не-строки, некомпактные формы (``YYYYMMDD``), неполные
    (``2026-1-1``) и невозможные календарные даты. Возвращает ``isoformat``
    разобранной даты (для канонического входа совпадает со входом).
    """
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValueError(
            f'Некорректная дата действия {value!r}: нужен ISO YYYY-MM-DD')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f'Некорректная дата действия {value!r}: нужен ISO YYYY-MM-DD') from None
    return parsed.isoformat()


def is_valid_date(value: object) -> bool:
    """Строгая проверка даты без исключений (для TOML-валидации)."""
    try:
        normalize_date(value)
        return True
    except (ValueError, TypeError):
        return False


def parse_money_value(value: object) -> Decimal:
    """Разобрать денежное значение в Decimal с проверкой конечности."""
    try:
        amount = as_decimal(value)  # type: ignore[arg-type]
    except (InvalidOperation, ValueError, AttributeError, TypeError):
        raise ValueError(f'Некорректная денежная сумма {value!r}') from None
    if amount.is_nan() or amount.is_infinite():
        raise ValueError(f'Некорректная денежная сумма {value!r}')
    return amount


def money_to_cents(value: object, field: str, allow_zero: bool = True) -> int:
    """Единый перевод денег в целые копейки (HALF_UP).

    Отрицательные при ``allow_zero=True`` запрещены; при
    ``allow_zero=False`` запрещены и нулевые — в том числе после округления
    (R14: ``"0.001"`` округляется до 0 копеек и отвергается здесь, а не
    ограничением SQLite при применении). Переполнение SQLite INTEGER
    отклоняется явной ошибкой. ``bool`` отклоняется явно (R14).
    """
    if isinstance(value, bool):
        raise ValueError(f'{field}: булево значение недопустимо ({value!r})')
    amount = parse_money_value(value)
    if allow_zero:
        if amount < 0:
            raise ValueError(f'{field}: отрицательная сумма {amount}')
    elif amount <= 0:
        raise ValueError(f'{field}: нужна положительная сумма, получено {amount}')
    try:
        rounded = quantize_money(amount)
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f'{field}: некорректная сумма {value!r}: {e}') from None
    cents = int(rounded * 100)
    if not allow_zero and cents <= 0:
        raise ValueError(f'{field}: сумма {value!r} после округления до копеек равна 0')
    if abs(cents) > SQLITE_INT_MAX:
        raise ValueError(f'{field}: сумма {amount} вне диапазона SQLite INTEGER')
    return cents


def require_int_id(value: object, field: str) -> int:
    """Строгий ID: точный ``int`` (``bool``/``list``/``str`` отклоняются, R14)."""
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError(f'{field}: нужен целый ID, получено {value!r}')
    if value < 0:
        raise ValueError(f'{field}: ID должен быть неотрицательным, получено {value!r}')
    if value > SQLITE_INT_MAX:
        raise ValueError(f'{field}: ID {value!r} вне диапазона SQLite INTEGER')
    return value


def parse_finite_decimal(value: object, field: str, allow_zero: bool = False) -> Decimal:
    """Конечный Decimal > 0 (или >= 0): отклоняет NaN/Infinity/bool (R14)."""
    if isinstance(value, bool):
        raise ValueError(f'{field}: булево значение недопустимо ({value!r})')
    try:
        amount = as_decimal(value)  # type: ignore[arg-type]
    except (InvalidOperation, ValueError, AttributeError, TypeError):
        raise ValueError(f'{field}: некорректное число {value!r}') from None
    if amount.is_nan() or amount.is_infinite():
        raise ValueError(f'{field}: нужна конечная величина, получено {value!r}')
    if allow_zero:
        if amount < 0:
            raise ValueError(f'{field}: нужна величина >= 0, получено {value!r}')
    elif amount <= 0:
        raise ValueError(f'{field}: нужна положительная величина, получено {value!r}')
    return amount


def require_month_start(value: str, field: str = 'effective_from') -> str:
    """Дата версии/назначения — строго 1-е число месяца (R06, spec §6)."""
    canon = normalize_date(value)
    if not canon.endswith('-01'):
        raise ValueError(
            f'{field}: {canon} — версии действуют только с 1-го числа месяца '
            f'(mid-month запрещён, spec §6)')
    return canon


def require_month_end_or_none(value: str | None, field: str = 'effective_to') -> str | None:
    """Окончание назначения — None или последний день месяца (R06)."""
    if value is None:
        return None
    canon = normalize_date(value)
    import calendar as _cal

    year, month, day = int(canon[:4]), int(canon[5:7]), int(canon[8:10])
    last = _cal.monthrange(year, month)[1]
    if day != last:
        raise ValueError(
            f'{field}: {canon} — окончание назначается только на последний день '
            f'месяца ({year:04d}-{month:02d}-{last:02d}) или бессрочно')
    return canon


def section_records(data: dict, name: str, errors: list[str]) -> list[tuple[int, dict]]:
    """Извлечь записи раздела TOML как ``[(индекс, словарь)]``.

    Не-список раздела и не-словарные записи превращаются в предметные
    ошибки ``раздел.поле`` вместо ``TypeError``/``AttributeError`` (F12).
    """
    if name not in data:
        return []
    raw = data[name]
    if not isinstance(raw, list):
        errors.append(f'{name}: нужен список записей [[{name}]]')
        return []
    out: list[tuple[int, dict]] = []
    for idx, rec in enumerate(raw):
        if not isinstance(rec, dict):
            errors.append(f'{name}[#{idx}]: нужна запись-словарь')
            continue
        out.append((idx, rec))
    return out


def find_noncanonical_dates(con) -> list[str]:
    """Проверить БД на неканонические даты (аудит F13).

    Возвращает описания ``таблица[ключ].поле = значение`` для всех значений,
    не проходящих :func:`normalize_date` или отличающихся от канона.
    Пустой список — даты каноничны.
    """
    problems: list[str] = []
    checks: list[tuple[str, str, str]] = [
        ('SELECT effective_from AS v, effective_from AS k FROM pay_settings', 'pay_settings', 'effective_from'),
        ('SELECT role_id || \"@\" || effective_from AS k, effective_from AS v FROM role_rules', 'role_rules', 'effective_from'),
        ('SELECT id AS k, hire_date AS v FROM employees WHERE hire_date IS NOT NULL', 'employees', 'hire_date'),
        ('SELECT emp_id || \"@\" || effective_from AS k, effective_from AS v FROM assignments', 'assignments', 'effective_from'),
        ('SELECT emp_id || \"@\" || effective_from AS k, effective_to AS v FROM assignments WHERE effective_to IS NOT NULL', 'assignments', 'effective_to'),
        ('SELECT effective_from AS k, effective_from AS v FROM seniority_scale', 'seniority_scale', 'effective_from'),
    ]
    for sql, table, field in checks:
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            continue  # таблицы может не быть в частично созданной БД
        for row in rows:
            val = row['v']
            try:
                canon = normalize_date(val)
            except (ValueError, TypeError):
                problems.append(f'{table}[{row["k"]}].{field} = {val!r}: не ISO YYYY-MM-DD')
                continue
            if val != canon:
                problems.append(f'{table}[{row["k"]}].{field} = {val!r}: неканоническое (нужно {canon!r})')
    return problems
