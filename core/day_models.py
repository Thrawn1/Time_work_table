"""Именованные структуры учётного дня (п.1 рефакторинга).

Заменяют позиционные списки/кортежи:
- было: [go, come, tag], (delta, worked, overtime_tag, day_tag),
  summary (work, holiday, vacation, truancy), wages (salary, milk, total).
- стало: DayMark, DayWork, EmployeeMonth, WageResult.

Совместимость: каждая структура поддерживает и именованный доступ
(.go/.come/.tag ...), и legacy-индексы (marks[0], wd[1], summary[101][0][0]),
чтобы миграция шла по границам без одновременного переписывания всего
проекта и без поломки 276 существующих тестов. Новый код обязан использовать
именованные поля; индексы оставлены только ради старых тестов/вызовов.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


# --- Отметки дня: [go(уход), come(приход), tag] -------------------------------

@dataclass
class DayMark:
    """Один учётный день сотрудника: уход, приход, статус дня."""

    go: datetime
    come: datetime
    tag: str

    def __len__(self) -> int:
        return 3

    def __iter__(self):
        yield self.go
        yield self.come
        yield self.tag

    def __getitem__(self, index):
        if index == 0:
            return self.go
        if index == 1:
            return self.come
        if index == 2:
            return self.tag
        raise IndexError(f'DayMark index out of range: {index!r}')

    def __setitem__(self, index, value) -> None:
        if index == 0:
            self.go = value
        elif index == 1:
            self.come = value
        elif index == 2:
            self.tag = value
        else:
            raise IndexError(f'DayMark index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, DayMark):
            return (self.go, self.come, self.tag) == (other.go, other.come, other.tag)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return (self.go, self.come, self.tag) == tuple(other)
        return NotImplemented


# --- Дневной расчёт: (delta, worked, overtime_tag, day_tag) --------------------

@dataclass
class DayWork:
    """Результат дневного учёта: отклонение, факт, тег переработки, тег дня."""

    delta: timedelta
    worked: timedelta
    overtime_tag: str
    day_tag: str

    def __len__(self) -> int:
        return 4

    def __iter__(self):
        yield self.delta
        yield self.worked
        yield self.overtime_tag
        yield self.day_tag

    def __getitem__(self, index):
        if index == 0:
            return self.delta
        if index == 1:
            return self.worked
        if index == 2:
            return self.overtime_tag
        if index == 3:
            return self.day_tag
        raise IndexError(f'DayWork index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, DayWork):
            return (self.delta, self.worked, self.overtime_tag, self.day_tag) == \
                (other.delta, other.worked, other.overtime_tag, other.day_tag)
        if isinstance(other, (list, tuple)) and len(other) == 4:
            return (self.delta, self.worked, self.overtime_tag, self.day_tag) == tuple(other)
        return NotImplemented


# --- Месячная агрегация --------------------------------------------------------

@dataclass
class WorkGroup:
    """Будни: число дней, переработка, недоработка."""

    days: int
    overtime: timedelta
    undertime: timedelta

    def __len__(self) -> int:
        return 3

    def __iter__(self):
        yield self.days
        yield self.overtime
        yield self.undertime

    def __getitem__(self, index):
        if index == 0:
            return self.days
        if index == 1:
            return self.overtime
        if index == 2:
            return self.undertime
        raise IndexError(f'WorkGroup index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, WorkGroup):
            return (self.days, self.overtime, self.undertime) == \
                (other.days, other.overtime, other.undertime)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return (self.days, self.overtime, self.undertime) == tuple(other)
        return NotImplemented


@dataclass
class HolidayGroup:
    """Выходные/праздники: дни, переработка, недоработка, суммарный факт."""

    days: int
    overtime: timedelta
    undertime: timedelta
    worked: timedelta

    def __len__(self) -> int:
        return 4

    def __iter__(self):
        yield self.days
        yield self.overtime
        yield self.undertime
        yield self.worked

    def __getitem__(self, index):
        if index == 0:
            return self.days
        if index == 1:
            return self.overtime
        if index == 2:
            return self.undertime
        if index == 3:
            return self.worked
        raise IndexError(f'HolidayGroup index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, HolidayGroup):
            return (self.days, self.overtime, self.undertime, self.worked) == \
                (other.days, other.overtime, other.undertime, other.worked)
        if isinstance(other, (list, tuple)) and len(other) == 4:
            return (self.days, self.overtime, self.undertime, self.worked) == tuple(other)
        return NotImplemented


@dataclass
class EmployeeMonth:
    """Месячный итог сотрудника: будни, выходные, отпуск, прогул."""

    work: WorkGroup
    holiday: HolidayGroup
    vacation_days: int
    truancy_days: int

    def __len__(self) -> int:
        return 4

    def __iter__(self):
        yield self.work
        yield self.holiday
        yield self.vacation_days
        yield self.truancy_days

    def __getitem__(self, index):
        if index == 0:
            return self.work
        if index == 1:
            return self.holiday
        if index == 2:
            return self.vacation_days
        if index == 3:
            return self.truancy_days
        raise IndexError(f'EmployeeMonth index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, EmployeeMonth):
            return (self.work, self.holiday, self.vacation_days, self.truancy_days) == \
                (other.work, other.holiday, other.vacation_days, other.truancy_days)
        if isinstance(other, (list, tuple)) and len(other) == 4:
            return tuple(self) == tuple(other)
        return NotImplemented


# --- Зарплата: (salary, milk, total_with_milk) ----------------------------------

@dataclass
class WageResult:
    """Начисление: оклад, молоко, итог с молоком."""

    salary: Decimal
    milk: Decimal
    total_with_milk: Decimal

    def __len__(self) -> int:
        return 3

    def __iter__(self):
        yield self.salary
        yield self.milk
        yield self.total_with_milk

    def __getitem__(self, index):
        if index == 0:
            return self.salary
        if index == 1:
            return self.milk
        if index == 2:
            return self.total_with_milk
        raise IndexError(f'WageResult index out of range: {index!r}')

    def __eq__(self, other) -> bool:
        if isinstance(other, WageResult):
            return (self.salary, self.milk, self.total_with_milk) == \
                (other.salary, other.milk, other.total_with_milk)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return (self.salary, self.milk, self.total_with_milk) == tuple(other)
        return NotImplemented


# --- Алиасы таблиц --------------------------------------------------------------

TimeTable = dict[str, dict[int, DayMark]]
WorkTime = dict[str, dict[int, DayWork]]
Summary = dict[int, EmployeeMonth]
Wages = dict[int, WageResult]
