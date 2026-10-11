"""Именованные структуры учётного дня.

DayMark (отметки дня), DayWork (дневной учёт), EmployeeMonth (месячный итог),
WageResult (начисление). Доступ — только по именам полей.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

# --- Единые теги дня и переработки (п.2, без смены значений) -------------------
# Новый код сравнивает/присваивает через эти константы вместо строковых
# литералов, разбросанных по модулям. Значения заморожены: их же хранят
# JSON-сессии и видят тесты, поэтому меняем только имена обращений.

TAG_WORK = 'work'
TAG_WEEKEND = 'weekend'
TAG_HOLIDAY = 'holiday'
TAG_VACATION = 'vacation'
TAG_TRUANCY = 'truancy'
TAG_SICK = 'sick'

OVERTIME = 'переработка'
UNDERTIME = 'недоработка'
NO_OVERTIME = ''

WORK_TAGS: tuple[str, ...] = (TAG_WORK,)
WEEKEND_TAGS: tuple[str, ...] = (TAG_WEEKEND, TAG_HOLIDAY)
ATTENDANCE_TAGS: tuple[str, ...] = (TAG_WORK, TAG_WEEKEND, TAG_HOLIDAY)
ABSENCE_TAGS: tuple[str, ...] = (TAG_VACATION, TAG_TRUANCY, TAG_SICK)
ALLOWED_TAGS: frozenset[str] = frozenset(
    (TAG_WORK, TAG_WEEKEND, TAG_HOLIDAY, TAG_VACATION, TAG_TRUANCY, TAG_SICK)
)

#: Подписи статусов-отсутствий в отчётах (Excel/HTML).
ABSENCE_LABELS: dict[str, str] = {
    TAG_VACATION: 'Отпуск',
    TAG_TRUANCY: 'Прогул',
    TAG_SICK: 'Больничный',
}


# --- Отметки дня ---------------------------------------------------------------

@dataclass
class DayMark:
    """Один учётный день сотрудника: уход, приход, статус дня."""

    go: datetime
    come: datetime
    tag: str


# --- Дневной расчёт -------------------------------------------------------------

@dataclass
class DayWork:
    """Результат дневного учёта: отклонение, факт, тег переработки, тег дня."""

    delta: timedelta
    worked: timedelta
    overtime_tag: str
    day_tag: str


# --- Месячная агрегация --------------------------------------------------------

@dataclass
class WorkGroup:
    """Будни: число дней, переработка, недоработка."""

    days: int
    overtime: timedelta
    undertime: timedelta


@dataclass
class HolidayGroup:
    """Выходные/праздники: дни, переработка, недоработка, суммарный факт."""

    days: int
    overtime: timedelta
    undertime: timedelta
    worked: timedelta


@dataclass
class EmployeeMonth:
    """Месячный итог сотрудника: будни, выходные, отпуск, прогул.

    ``sick_days`` — больничные дни (оплата OPEN, spec п.9).
    """

    work: WorkGroup
    holiday: HolidayGroup
    vacation_days: int
    truancy_days: int
    sick_days: int = 0


# --- Зарплата ------------------------------------------------------------------

@dataclass
class WageResult:
    """Начисление: оклад, молоко, итог с молоком."""

    salary: Decimal
    milk: Decimal
    total_with_milk: Decimal


# --- Алиасы таблиц --------------------------------------------------------------

TimeTable = dict[str, dict[int, DayMark]]
WorkTime = dict[str, dict[int, DayWork]]
Summary = dict[int, EmployeeMonth]
Wages = dict[int, WageResult]
