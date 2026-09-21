"""Выбор модели оплаты. Возвращает результат и диагностику для любого интерфейса."""

import sqlite3
from dataclasses import dataclass, field

from core import config
from core.calculations import calculate_wages
from core.data_array import get_name_employee
from core.day_models import Summary, TimeTable, Wages, WorkTime
from core.payroll import (
    PayrollBundle, PayrollError, build_bundle, bundle_to_wages, new_regime_available,
)


@dataclass
class PayrollOutcome:
    wages: Wages
    bundle: PayrollBundle | None = None
    warnings: list[str] = field(default_factory=list)


def calculate_payroll(time_table: TimeTable, work_time: WorkTime, summary: Summary,
                      year: int, month: int, db_path: str, *, salary_mode: bool,
                      employees: dict) -> PayrollOutcome:
    """Учёт без зарплаты имеет приоритет над наличием SQLite-справочника.

    В legacy ставки читаются один раз; при учёте времени ставки не нужны.
    Ошибки настройки новой модели дают прежний fallback с диагностикой.
    """
    if not salary_mode:
        return PayrollOutcome(calculate_wages(summary, rates={}, employees=employees))

    warnings = []
    try:
        if new_regime_available(db_path, year, month) is not None:
            bundle = build_bundle(time_table, work_time, summary, year, month, db_path,
                                  employees=employees)
            return PayrollOutcome(bundle_to_wages(bundle), bundle=bundle)
    except (PayrollError, sqlite3.Error) as exc:
        warnings.append(f'новая модель недоступна ({exc}). Расчет в legacy-режиме.')

    rates = config.load_wage_rates()
    wages = calculate_wages(summary, rates=rates, employees=employees)
    for emp_id in wages:
        if rates.get(emp_id, 0) == 0:
            name = get_name_employee(emp_id, employees) or emp_id
            warnings.append(f'{name} — ставка 0 (нет в wage_rates.dat или неверный ключ -k). '
                            'Оклад будет нулевым, только молоко.')
    return PayrollOutcome(wages, warnings=warnings)
