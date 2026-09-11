"""Месячный пакет нового расчёта: единый набор входных данных (план, шаг 4).

Расчётные функции получают всё явно (общие условия, версии правил и назначений,
стаж, календарь, участники); скрытого чтения ставок/БД в формулах нет.
Старый режим для периодов без действующих общих условий считает legacy-адаптер
(core.calculations.calculate_wages) — новая база к старым месяцам не применяется.

Допущения шага 0, зафиксированные здесь явно:
- факт месяца = сумма фактических часов рабочих дней + выходных/праздников
  (выходные входят в факт и при превышении нормы становятся переработкой);
- смена роли внутри месяца: используется правило на 1-е число, в отчёт идёт
  предупреждение (поинтервальный учёт — следующий шаг);
- дата приёма неизвестна (перенос из .dat без hire_date) — считаем занятость
  весь месяц; стаж при неизвестной дате = 0%;
- молоко: фактическим участникам 40 ₽ × (будни + выходные выходы),
  фиксированной смене — 0 (как в старом режиме у роли 3); в основу стажа не входит.
"""

from __future__ import annotations

import calendar as _calendar
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from core.constants import MILK_ALLOWANCE_PER_DAY
from core.money import as_decimal, timedelta_to_hours
from core.pay_calc import PayInputs, PayResult, calculate_pay, seniority_rate_for_service
from core.pay_calendar import working_days_in_month
from core.roles import TIME_ACTUAL, RoleRule


class PayrollError(RuntimeError):
    """Неполная настройка справочника: понятная ошибка до правок и отчётов."""


@dataclass
class PayEmployeeResult:
    emp_id: int
    name: str
    rule: RoleRule
    inputs: PayInputs
    result: PayResult


@dataclass
class PayrollBundle:
    year: int
    month: int
    workdays: int
    settings_eff: str
    monthly_base: Decimal
    base_day_hours: int
    full_month_bonus: Decimal
    seniority_scale: list[tuple[int, Decimal]]
    rule_versions: dict[int, str]
    results: dict[int, PayEmployeeResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def versions_snapshot(self) -> dict:
        return {
            'year': self.year, 'month': self.month,
            'workdays_D': self.workdays,
            'pay_settings': {
                'effective_from': self.settings_eff,
                'monthly_base': str(self.monthly_base),
                'base_day_hours': self.base_day_hours,
                'full_month_bonus': str(self.full_month_bonus),
            },
            'role_rule_versions': {str(k): v for k, v in self.rule_versions.items()},
            'seniority_scale': [[y, str(r)] for y, r in self.seniority_scale],
            'warnings': self.warnings,
        }

    def save_versions(self, path: str) -> str:
        Path(path).write_text(json.dumps(self.versions_snapshot(), ensure_ascii=False, indent=2),
                              encoding='utf-8')
        return path


def new_regime_available(db_path: str, year: int, month: int):
    """Действующие общие условия на начало месяца или None (тогда legacy-режим)."""
    from core.pay_store import connect, get_pay_settings

    if not Path(db_path).exists():
        return None
    con = connect(db_path)
    try:
        return get_pay_settings(con, f'{year:04d}-{month:02d}-01')
    finally:
        con.close()


def _service_years(hire_iso: str | None, on: date) -> Decimal | None:
    if not hire_iso:
        return None
    hire = date.fromisoformat(hire_iso)
    return as_decimal((on - hire).days) / Decimal('365.25')


def build_bundle(data_array: dict, work_time: dict, summary: dict, year: int, month: int,
                 db_path: str) -> PayrollBundle:
    """Собрать месячный пакет. Кидает PayrollError при неполной настройке."""
    from core.analysis import _get_marks_and_missed
    from core.data_array import exclusion_reason, get_name_employee
    from core.pay_store import (
        connect, get_assignment, get_pay_settings, get_role_rule, get_seniority_scale,
    )

    month_start = f'{year:04d}-{month:02d}-01'
    last_day = _calendar.monthrange(year, month)[1]
    month_end = f'{year:04d}-{month:02d}-{last_day:02d}'
    first, last = date(year, month, 1), date(year, month, last_day)

    workdays = working_days_in_month(year, month)
    if workdays == 0:
        raise PayrollError(f'{year}-{month:02d}: D=0 — пустой производственный календарь.')

    con = connect(db_path)
    try:
        settings = get_pay_settings(con, month_start)
        if settings is None:
            raise PayrollError(f'{year}-{month:02d}: нет действующих общих условий.')
        scale = get_seniority_scale(con, month_start)
        emp_rows = {r['id']: r for r in con.execute('SELECT * FROM employees')}
        exceptions = {r['emp_id'] for r in con.execute('SELECT emp_id FROM settlement_exceptions')}
        bundle = PayrollBundle(
            year=year, month=month, workdays=workdays,
            settings_eff=settings.effective_from, monthly_base=settings.monthly_base,
            base_day_hours=settings.base_day_hours,
            full_month_bonus=settings.full_month_bonus,
            seniority_scale=scale, rule_versions={},
        )
        # Предупреждение о смене условий внутри месяца.
        mid = con.execute(
            'SELECT COUNT(*) c FROM pay_settings WHERE effective_from > ? AND effective_from <= ?',
            (month_start, month_end)).fetchone()['c']
        if mid:
            bundle.warnings.append('общие условия меняются внутри месяца: расчёт по версии '
                                   f'на {month_start}')
        saw_seniority_eligible = False
        for emp_id in summary:
            reason = exclusion_reason(emp_id)
            if reason:
                continue  # не участник — только дашборд
            if emp_id in exceptions:
                continue
            assigned = get_assignment(con, emp_id, month_start)
            if assigned is None:
                raise PayrollError(f'ID {emp_id}: нет назначения роли на {month_start}.')
            role_id, assign_to = assigned
            rule = get_role_rule(con, role_id, month_start)
            if rule is None:
                raise PayrollError(f'ID {emp_id}: нет версии правил роли {role_id} на {month_start}.')
            bundle.rule_versions[role_id] = month_start
            later = con.execute(
                'SELECT effective_from FROM assignments WHERE emp_id=? AND effective_from > ?'
                ' AND effective_from <= ?', (emp_id, month_start, month_end)).fetchone()
            if later or (assign_to is not None and assign_to < month_end):
                bundle.warnings.append(
                    f'ID {emp_id}: назначение меняется внутри месяца '
                    f'({later["effective_from"] if later else "завершается " + str(assign_to)}): '
                    'расчёт по правилу на 1-е число')
            # work_time: {date: {emp: entry}} — агрегируем по сотруднику.
            fact = Decimal('0')
            present_work = 0
            present_weekend = 0
            for date_key, emps in work_time.items():
                entry = emps.get(emp_id)
                if entry is None:
                    continue
                tag_day = entry[3]
                if tag_day == 'work':
                    present_work += 1
                    fact += timedelta_to_hours(entry[1])
                elif tag_day in ('weekend', 'holiday'):
                    present_weekend += 1
                    fact += timedelta_to_hours(entry[1])
            data = summary[emp_id]
            vacation_days, truancy_days = data[2], data[3]
            singles, _missed = _get_marks_and_missed(data_array, emp_id, year, month)
            single_issue = bool(singles)
            hire_iso = emp_rows[emp_id]['hire_date'] if emp_id in emp_rows else None
            years = _service_years(hire_iso, first)
            if rule.seniority_eligible:
                saw_seniority_eligible = True
            if rule.seniority_eligible and years is not None:
                sen_rate = seniority_rate_for_service(scale, years)
            else:
                sen_rate = Decimal('0')
            whole = True
            if hire_iso and hire_iso > month_start:
                whole = False
            if rule.time_mode == TIME_ACTUAL:
                milk = MILK_ALLOWANCE_PER_DAY * (present_work + present_weekend)
            else:
                milk = Decimal('0.00')
            inputs = PayInputs(
                monthly_base=settings.monthly_base, base_day_hours=settings.base_day_hours,
                full_month_bonus=settings.full_month_bonus, workdays=workdays,
                shift_norm_hours=rule.shift_norm_hours, fact_hours=fact,
                workdays_present=present_work, vacation_days=vacation_days,
                truancy_days=truancy_days, single_mark_issue=single_issue,
                employed_whole_month=whole,
                overtime_eligible=rule.overtime_eligible,
                full_month_eligible=rule.full_month_eligible,
                seniority_eligible=rule.seniority_eligible,
                overtime_coef=rule.overtime_coef, seniority_rate=sen_rate,
                milk_amount=milk,
            )
            bundle.results[emp_id] = PayEmployeeResult(
                emp_id=emp_id, name=get_name_employee(emp_id) or f'ID {emp_id}',
                rule=rule, inputs=inputs, result=calculate_pay(inputs),
            )
        if not scale and saw_seniority_eligible:
            bundle.warnings.append('стажевая шкала не задана (данные будут позже): '
                                   'бонус стажа 0 для всех')
        return bundle
    finally:
        con.close()


def bundle_to_wages(bundle: PayrollBundle) -> dict[int, tuple[Decimal, Decimal, Decimal]]:
    """Отображение итога в формат (оклад, молоко, с молоком) — один результат для всех отчётов."""
    return {emp_id: (r.result.total, r.result.milk_amount, r.result.total_with_milk)
            for emp_id, r in bundle.results.items()}
