"""Месячный пакет нового расчёта: единый набор входных данных (spec_payroll.md §4–§6).

Расчётные функции получают всё явно (общие условия, версии правил и назначений,
стаж, календарь, участники); скрытого чтения ставок/БД в формулах нет.
Старый режим для периодов без действующих общих условий считает legacy-адаптер
(core.calculations.calculate_wages) — новая база к старым месяцам не применяется.

Действующие правила (spec v1.0):
- факт месяца для начислений — сумма часов ТОЛЬКО будних выходов (R05, §5);
  выходные/праздники в ``fact``/``H_overtime`` не входят (их отдельная схема — OPEN);
- версии/назначения только с 1-го числа; mid-month — отказ до расчёта (R06, §6);
- стаж — полные календарные годы до 1-го числа (R17, §4);
- роль 4 — без начислений, отдельный список выходов (R04, §2);
- дата приёма неизвестна — занятость весь месяц; стаж при неизвестной дате = 0%;
- молоко: фактическим участникам 40 руб. × выходы — ДОПУЩЕНИЕ кода (spec §5 OPEN),
  фиксированной смене — 0; в основу стажа не входит.
"""

from __future__ import annotations

import calendar as _calendar
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from core.constants import MILK_ALLOWANCE_PER_DAY
from core.day_models import WageResult
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
    salary_mode: bool = True
    seniority_eff: str | None = None

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
            'seniority_scale': {
                'effective_from': self.seniority_eff,
                'thresholds': [[y, str(r)] for y, r in self.seniority_scale],
            },
            'warnings': self.warnings,
        }

    def save_versions(self, path: str) -> str:
        parent = Path(path).parent
        if str(parent) not in ('', '.'):
            parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.versions_snapshot(), ensure_ascii=False, indent=2),
                              encoding='utf-8')
        return path


def new_regime_available(db_path: str, year: int, month: int):
    """Действующие общие условия на начало месяца или None (тогда legacy-режим).

    Граница перехода — кодом, а не seed-данными: периоды раньше
    DEFAULT_TRANSITION всегда legacy, даже при случайной записи условий
    на прошлые даты (F05). Ошибки чтения/схемы БД — PayrollError
    с путём и причиной, а не raw sqlite3.OperationalError.
    """
    import sqlite3

    from core.pay_store import DEFAULT_TRANSITION, connect, get_pay_settings

    month_start = f'{year:04d}-{month:02d}-01'
    if month_start < DEFAULT_TRANSITION:
        return None
    if not Path(db_path).exists():
        return None
    try:
        con = connect(db_path)
    except sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            from core.pay_validate import find_noncanonical_dates

            _bad = find_noncanonical_dates(con)
            if _bad:
                raise PayrollError(
                    f'{db_path}: неканонические даты справочника ({len(_bad)}): '
                    + '; '.join(_bad[:5]))
            return get_pay_settings(con, month_start)
        except PayrollError:
            raise
        except ValueError as e:
            raise PayrollError(f'{db_path}: некорректный запрос условий ({e}).') from e
        except sqlite3.Error as e:
            raise PayrollError(
                f'{db_path}: ошибка чтения справочника (нет таблиц/повреждена схема?): {e}.'
            ) from e
    finally:
        try:
            con.close()
        except Exception:
            pass


def resolve_pay_mode(db_path: str, year: int, month: int) -> str:
    """Режим периода до правок и отчётов: 'new' или 'legacy'.

    'new' — есть действующие общие условия и период не раньше перехода:
    новая модель обязана применяться, её ошибки настройки фатальны
    (без silent fallback в legacy). 'legacy' — новая модель к периоду
    не применяется. Ошибки чтения БД — PayrollError.
    """
    return 'new' if new_regime_available(db_path, year, month) is not None else 'legacy'


def _service_years(hire_iso: str | None, on: date) -> Decimal | None:
    """Полные календарные годы от hire_date до даты расчёта (R17, spec §4).

    Порог достигается в годовщину. 29 февраля: в невисокосном году годовщина —
    28 февраля (предложение spec, применяется как допущение до шкалы).
    """
    if not hire_iso:
        return None
    hire = date.fromisoformat(hire_iso)
    ann_month, ann_day = hire.month, hire.day
    if ann_month == 2 and ann_day == 29:
        import calendar as _cal

        if not _cal.isleap(on.year):
            ann_day = 28
    years = on.year - hire.year - ((on.month, on.day) < (ann_month, ann_day))
    return Decimal(max(years, 0))


def _zeroed_for_no_salary(result) -> object:
    """Обнулить денежные компоненты при salary_mode=False; молоко сохранить."""
    from core.money import quantize_money
    from core.pay_calc import PayResult as _PayResult

    milk = quantize_money(result.milk_amount)
    return _PayResult(
        rate_day=result.rate_day, rate_hour=result.rate_hour,
        norm_hours=result.norm_hours, fact_hours=result.fact_hours,
        ordinary_hours=result.ordinary_hours, ordinary_pay=Decimal('0.00'),
        overtime_hours=result.overtime_hours, overtime_bonus=Decimal('0.00'),
        full_month_bonus=Decimal('0.00'), full_month_ok=False,
        full_month_reason='режим без зарплаты: оклады обнулены',
        seniority_rate=Decimal('0'), seniority_basis_exact=Decimal('0'),
        seniority_bonus=Decimal('0.00'), total=Decimal('0.00'),
        milk_amount=milk, total_with_milk=milk,
    )


def build_bundle(data_array: dict, work_time: dict, summary: dict, year: int, month: int,
                 db_path: str, salary_mode: bool = True,
                 employees: dict | None = None,
                 rules_by_role: dict | None = None) -> PayrollBundle:
    """Собрать месячный пакет. Кидает PayrollError при неполной настройке.

    salary_mode=False (ключи t/0/мусор): денежные начисления обнуляются,
    молоко сохраняется — одинаково для новой и legacy-модели (F01).
    Правило SQLite с participates=False исключает сотрудника из начислений (F02).
    employees — объединённый DAT+SQLite штат в new-режиме (R01–R03).
    rules_by_role — действующие SQLite-правила {role_id: RoleRule} на 1-е число;
    одиночные отметки проверяются по ним, а не по DAT-умолчанию (R01–R02).
    Факт для начислений — только будни (R05, spec §5). Версии не с 1-го числа
    и неканонические даты — отказ до расчёта (R06/R15, spec §6).
    """
    from core.analysis import _get_marks_and_missed
    from core.data_array import exclusion_reason, get_name_employee
    from core.pay_store import (
        connect, get_assignment, get_pay_settings, get_role_rule_version,
        get_seniority_version,
    )

    month_start = f'{year:04d}-{month:02d}-01'
    last_day = _calendar.monthrange(year, month)[1]
    month_end = f'{year:04d}-{month:02d}-{last_day:02d}'
    first = date(year, month, 1)

    workdays = working_days_in_month(year, month)
    if workdays == 0:
        raise PayrollError(f'{year}-{month:02d}: D=0 — пустой производственный календарь.')

    import sqlite3 as _sqlite3

    try:
        con = connect(db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            settings = get_pay_settings(con, month_start)
        except _sqlite3.Error as e:
            raise PayrollError(
                f'{db_path}: ошибка чтения общих условий (нет таблиц/повреждена схема?): {e}.'
            ) from e
        if settings is None:
            raise PayrollError(f'{year}-{month:02d}: нет действующих общих условий.')
        try:
            scale_eff, scale = get_seniority_version(con, month_start)
            emp_rows = {r['id']: r for r in con.execute('SELECT * FROM employees')}
            exceptions = {r['emp_id'] for r in con.execute('SELECT emp_id FROM settlement_exceptions')}
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения справочника ({e}).') from e
        # R15: неканонические даты в существующей БД — отказ, а не другой алгоритм.
        from core.pay_validate import find_noncanonical_dates

        _bad_dates = find_noncanonical_dates(con)
        if _bad_dates:
            raise PayrollError(
                f'{db_path}: неканонические даты справочника ({len(_bad_dates)}): '
                + '; '.join(_bad_dates[:5]))
        # R06: версии/назначения не с 1-го числа — отказ до расчёта (spec §6).
        from core.pay_store import find_midmonth_violations

        _mid = find_midmonth_violations(con)
        # Фильтруем нарушения будущими периодами? Нет: любое mid-month нарушение
        # в БД делает расчёт неоднозначным — отказываем с явным списком.
        # Исключение: нарушения позже month_end не блокируют текущий месяц.
        _relevant = []
        for _m in _mid:
            _relevant.append(_m)
        # Точная фильтрация по датам внутри месяца — ниже по условиям/назначениям;
        # здесь отказываем, если есть нарушения, затрагивающие текущий месяц.
        try:
            _mid_settings = con.execute(
                'SELECT effective_from FROM pay_settings WHERE effective_from > ?'
                ' AND effective_from <= ?', (month_start, month_end)).fetchall()
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения версий условий ({e}).') from e
        if _mid_settings:
            raise PayrollError(
                f'{year}-{month:02d}: общие условия меняются внутри месяца '
                f'({", ".join(r["effective_from"] for r in _mid_settings)}): '
                f'по spec §6 версии действуют только с 1-го числа — исправьте справочник')
        try:
            _mid_rules = con.execute(
                'SELECT role_id, effective_from FROM role_rules WHERE effective_from > ?'
                ' AND effective_from <= ?', (month_start, month_end)).fetchall()
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения версий правил ({e}).') from e
        if _mid_rules:
            raise PayrollError(
                f'{year}-{month:02d}: версии правил меняются внутри месяца '
                f'({", ".join(str(r["role_id"]) + "@" + r["effective_from"] for r in _mid_rules)}): '
                f'по spec §6 — исправьте справочник')
        # Назначения внутри месяца проверяются персонально ниже (отказ с ID).
        bundle = PayrollBundle(
            year=year, month=month, workdays=workdays,
            settings_eff=settings.effective_from, monthly_base=settings.monthly_base,
            base_day_hours=settings.base_day_hours,
            full_month_bonus=settings.full_month_bonus,
            seniority_scale=scale, rule_versions={},
            salary_mode=bool(salary_mode), seniority_eff=scale_eff,
        )
        # R06: смена условий внутри месяца уже отклонена выше отказом.
        saw_seniority_eligible = False
        for emp_id in summary:
            reason = exclusion_reason(emp_id, employees)
            if reason:
                continue  # не участник — только дашборд
            if emp_id in exceptions:
                continue
            try:
                assigned = get_assignment(con, emp_id, month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if assigned is None:
                raise PayrollError(f'ID {emp_id}: нет назначения роли на {month_start}.')
            role_id, assign_to = assigned
            try:
                found = get_role_rule_version(con, role_id, month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения правил ролей ({e}).') from e
            if found is None:
                raise PayrollError(f'ID {emp_id}: нет версии правил роли {role_id} на {month_start}.')
            rule_eff, rule = found
            if not rule.participates:
                # SQLite-правило исключает из начислений (F02): только дашборд с причиной.
                continue
            bundle.rule_versions[role_id] = rule_eff
            try:
                later = con.execute(
                    'SELECT effective_from FROM assignments WHERE emp_id=? AND effective_from > ?'
                    ' AND effective_from <= ?', (emp_id, month_start, month_end)).fetchone()
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if later or (assign_to is not None and assign_to < month_end):
                raise PayrollError(
                    f'ID {emp_id}: назначение меняется внутри месяца '
                    f'({later["effective_from"] if later else "завершается " + str(assign_to)}): '
                    f'по spec §6 смена условий внутри месяца запрещена')
            # R05/spec §5: факт для начислений — ТОЛЬКО будни. Выходные/праздники
            # в fact/H_overtime не входят (их отдельная схема — OPEN, не ноль молча).
            fact = Decimal('0')
            present_work = 0
            present_weekend = 0
            for date_key, emps in work_time.items():
                entry = emps.get(emp_id)
                if entry is None:
                    continue
                from core.day_models import TAG_WORK, WEEKEND_TAGS

                tag_day = getattr(entry, 'day_tag', entry[3])
                worked = getattr(entry, 'worked', entry[1])
                if tag_day == TAG_WORK:
                    present_work += 1
                    fact += timedelta_to_hours(worked)
                elif tag_day in WEEKEND_TAGS:
                    present_weekend += 1
            data = summary[emp_id]
            vacation_days = getattr(data, 'vacation_days', data[2])
            truancy_days = getattr(data, 'truancy_days', data[3])
            sick_days = getattr(data, 'sick_days', 0)
            singles, _missed = _get_marks_and_missed(
                data_array, emp_id, year, month,
                employees=employees, rules_by_role=(
                    {rule.role_id: rule} if rules_by_role is None else rules_by_role))
            # R01: одиночная отметка видна и блокирует бонус (spec §4).
            # _get_marks... уже учитывает SQLite-правило через rules_by_role.
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
                milk_amount=milk, sick_days=sick_days,
            )
            _result = calculate_pay(inputs)
            if not salary_mode:
                _result = _zeroed_for_no_salary(_result)
            bundle.results[emp_id] = PayEmployeeResult(
                emp_id=emp_id,
                name=get_name_employee(emp_id, employees) or f'ID {emp_id}',
                rule=rule, inputs=inputs, result=_result,
            )
        if not scale and saw_seniority_eligible:
            bundle.warnings.append('стажевая шкала не задана (данные будут позже): '
                                   'бонус стажа 0 для всех')
        if not salary_mode:
            bundle.warnings.append('режим без зарплаты: оклады обнулены, молоко сохранено')
        # P3-C: открытые вопросы spec §9 — не выдаём допущения за утверждения.
        _any_weekend_days = False
        _any_vacation = False
        for _res in bundle.results.values():
            _any_vacation = _any_vacation or (_res.inputs.vacation_days > 0)
        try:
            from core.day_models import WEEKEND_TAGS as _WT

            for _emps in work_time.values():
                for _eid, _entry in _emps.items():
                    if _eid in bundle.results:
                        _tag = getattr(_entry, 'day_tag', _entry[3])
                        if _tag in _WT:
                            _any_weekend_days = True
                            break
                if _any_weekend_days:
                    break
        except (IndexError, AttributeError, TypeError):
            pass
        if _any_weekend_days:
            bundle.warnings.append(
                'выходные/праздники: отдельная схема оплаты — OPEN (spec п.9); '
                'в переработку не входят, молоко 40 руб. x выходы — допущение кода')
        if _any_vacation:
            bundle.warnings.append('отпуск: оплата в новой модели — OPEN (spec п.9)')
        if any(_res.inputs.sick_days > 0 for _res in bundle.results.values()):
            bundle.warnings.append(
                'больничный: не оплачивается программой (оплата — OPEN, spec п.9)')
        if bundle.results:
            bundle.warnings.append(
                'молоко 40 руб. x выходы — допущение кода, не утверждение spec (п.5 OPEN)')
        return bundle
    except PayrollError:
        raise
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: ошибка чтения справочника ({e}).') from e
    finally:
        try:
            con.close()
        except Exception:
            pass


def bundle_to_wages(bundle: PayrollBundle) -> dict[int, WageResult]:
    """Отображение итога в WageResult — один результат для всех отчётов.

    При salary_mode=False оклады уже обнулены в build_bundle; для вручную
    собранных bundle с salary_mode=False — обнуляем здесь, молоко сохраняем.
    """
    from core.day_models import WageResult

    if getattr(bundle, 'salary_mode', True) is False:
        from decimal import Decimal as _Decimal

        return {emp_id: WageResult(
            salary=_Decimal('0.00'),
            milk=r.result.milk_amount,
            total_with_milk=r.result.milk_amount,
        ) for emp_id, r in bundle.results.items()}
    return {emp_id: WageResult(
        salary=r.result.total,
        milk=r.result.milk_amount,
        total_with_milk=r.result.total_with_milk,
    ) for emp_id, r in bundle.results.items()}


def pay_header_text(bundle) -> str:
    """Единый заголовок блока новой модели для консоли/Excel/HTML.

    Те же числа везде: база, D, H_base, условия, округлённые ставки.
    Считает pay_calc, здесь только отображение.
    """
    from core.money import format_money

    text = (f'Новая модель: база {format_money(bundle.monthly_base)} руб., '
            f'рабочих дней {bundle.workdays}, H_base {bundle.base_day_hours} ч '
            f'(условия с {bundle.settings_eff}).')
    if getattr(bundle, 'salary_mode', True) is False:
        text += ' Режим без зарплаты: оклады обнулены, молоко сохранено.'
    if bundle.results:
        first = next(iter(bundle.results.values())).result
        text += (f' Ставки: день ~{format_money(first.rate_day)} руб., '
                 f'час ~{format_money(first.rate_hour)} руб.')
    else:
        text += ' Участников нет.'
    return text
