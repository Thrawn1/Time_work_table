"""Производственный календарь для новой модели оплаты (план roles_rates, §2.1/§4).

Один календарь для D (число рабочих дней месяца), классификации дат и анализа
пропусков. Использует существующие справочники data/variable_data_for_app:
holidays.dat (дни-месяц) и postponed_working_days.dat (переносы на выходные).

D = число будней (Пн–Пт) минус праздники плюс перенесённые рабочие дни.
D == 0 — явная диагностика у вызывающей стороны, здесь возвращается 0.
"""

from __future__ import annotations

import calendar as _calendar

from core.file_parser import definition_of_working_day


def classify_day(date_key: str) -> str:
    """Классификация даты: 'work' | 'weekend' | 'holiday'."""
    return definition_of_working_day(date_key)[0]


def month_date_keys(year: int, month: int) -> list[str]:
    """Все даты месяца как 'YYYY-MM-DD'."""
    n_days = _calendar.monthrange(year, month)[1]
    return [f'{year:04d}-{month:02d}-{day:02d}' for day in range(1, n_days + 1)]


def working_days_in_month(year: int, month: int) -> int:
    """Число рабочих дней D полного расчётного месяца.

    Будний день, не попавший в holidays.dat, плюс перенесённые рабочие дни
    (даже если выпадают на Сб/Вс). Праздники/выходные не считаются.
    """
    count = 0
    for date_key in month_date_keys(year, month):
        if classify_day(date_key) == 'work':
            count += 1
    return count


def workday_keys_in_month(year: int, month: int) -> list[str]:
    """Даты рабочих дней месяца (для проверки критерия полного месяца)."""
    return [d for d in month_date_keys(year, month) if classify_day(d) == 'work']
