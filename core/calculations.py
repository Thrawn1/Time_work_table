from datetime import timedelta
from decimal import Decimal
from core.config import load_wage_rates, staff_or_default
from core.constants import (
    WORKING_DAY_HOURS,
    MILK_ALLOWANCE_PER_DAY,
    OVERTIME_WEEKDAY_MULTIPLIER,
    OVERTIME_WEEKEND_MULTIPLIER,
)
from core.money import as_decimal, quantize_money, timedelta_to_hours
from core.roles import TIME_ACTUAL, TIME_FIXED_SHIFT, resolve_rule
from core.day_models import (
    ATTENDANCE_TAGS,
    NO_OVERTIME,
    OVERTIME,
    TAG_SICK,
    TAG_TRUANCY,
    TAG_VACATION,
    TAG_WORK,
    UNDERTIME,
    DayWork,
    EmployeeMonth,
    HolidayGroup,
    Summary,
    TimeTable,
    WageResult,
    Wages,
    WEEKEND_TAGS,
    WorkGroup,
    WorkTime,
)


def str_timedelta(td: timedelta) -> str:
    total = int(td.total_seconds())
    sign = '-' if total < 0 else ''
    total = abs(total)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f'{sign}{h:02d}:{m:02d}:{s:02d}'


def calculate_hours_per_day(time_table: TimeTable, employees: dict | None = None,
                            rules_by_role: dict | None = None) -> WorkTime:
    """Учёт времени по действующим правилам ролей (R02), без решений по ID.

    time_mode 'actual': факт = выход − вход, переработка/недоработка от нормы
    смены правила (SQLite-версия в new-режиме, иначе DAT-умолчание).
    time_mode 'fixed_shift': норма смены за рабочий выход независимо от отметок.
    Роль вне участия (напр. 0/4) в результат не попадает — её состав
    определяется фильтром участников до расчёта.

    employees=None — DAT-справочник запуска. rules_by_role — действующие
    SQLite-правила {role_id: RoleRule}; отсутствие версии — понятная ошибка
    до правок/отчётов (R02), а не KeyError в середине дневных строк.
    """
    staff = staff_or_default(employees)
    result: WorkTime = {}
    for date_key, employees_in_day in time_table.items():
        result[date_key] = {}
        for emp_id, marks in employees_in_day.items():
            emp = staff.get(emp_id)
            if emp is None:
                continue
            role_id = getattr(emp, 'role_id', None)
            rule = resolve_rule(role_id, rules_by_role)
            if rule is None:
                if rules_by_role is not None:
                    raise ValueError(
                        f'ID {emp_id}: нет версии правил роли {role_id} на месяц — '
                        f'заведите версию правил до анализа')
                raise ValueError(
                    f'ID {emp_id}: неизвестная роль {role_id} — нет правила учёта/оплаты')
            if not rule.participates:
                continue
            try:
                norm = timedelta(hours=float(rule.shift_norm_hours))
            except (ValueError, TypeError):
                raise ValueError(
                    f'ID {emp_id}: некорректная норма смены роли {role_id}: '
                    f'{rule.shift_norm_hours!r}') from None
            result[date_key][emp_id] = _day_work(marks, rule.time_mode, norm, emp_id, role_id)
    return result


def _day_work(marks, time_mode: str, norm: timedelta, emp_id: int, role_id) -> DayWork:
    if time_mode == TIME_ACTUAL:
        worked = marks.go - marks.come
        delta = worked - norm
        return DayWork(delta=abs(delta), worked=worked,
                       overtime_tag=OVERTIME if delta > timedelta(0) else UNDERTIME,
                       day_tag=marks.tag)
    if time_mode == TIME_FIXED_SHIFT:
        # Выход — норма смены; отсутствие и неизвестный тег — 0 ч (рабочий день не выдумываем).
        worked = norm if marks.tag in ATTENDANCE_TAGS else timedelta(0)
        return DayWork(delta=timedelta(0), worked=worked,
                       overtime_tag=NO_OVERTIME, day_tag=marks.tag)
    raise ValueError(f'ID {emp_id}: неизвестный time_mode {time_mode!r} роли {role_id}')


def calculate_hours_per_month(work_time: WorkTime) -> Summary:
    """Месячные итоги сотрудников: будни, выходные/праздники, отпуск, прогул, больничный."""
    zero = timedelta(0)
    summary: Summary = {}
    for employees in work_time.values():
        for emp_id, day in employees.items():
            month = summary.get(emp_id)
            if month is None:
                month = summary[emp_id] = EmployeeMonth(
                    work=WorkGroup(days=0, overtime=zero, undertime=zero),
                    holiday=HolidayGroup(days=0, overtime=zero, undertime=zero, worked=zero),
                    vacation_days=0, truancy_days=0)
            if day.day_tag == TAG_WORK:
                group = month.work
            elif day.day_tag in WEEKEND_TAGS:
                group = month.holiday
                group.worked += day.worked
            else:
                if day.day_tag == TAG_VACATION:
                    month.vacation_days += 1
                elif day.day_tag == TAG_TRUANCY:
                    month.truancy_days += 1
                elif day.day_tag == TAG_SICK:
                    month.sick_days += 1
                continue
            group.days += 1
            if day.overtime_tag == OVERTIME:
                group.overtime += day.delta
            else:
                group.undertime += day.delta
    return summary


def _shift_hours() -> Decimal:
    """Длительность стандартной смены в часах (ставка — руб/смена за 8ч)."""
    return Decimal(str(WORKING_DAY_HOURS))


def _rate_for(rates: dict, emp_id: int) -> Decimal:
    """Ставка сотрудника как Decimal руб/смена (моки с int/float тоже годятся)."""
    return as_decimal(rates.get(emp_id, Decimal('0.00')))


def _hourly_fraction(daily_rate: Decimal) -> Decimal:
    """Часовая доля дневной ставки (точная, без округления до копеек)."""
    return daily_rate / _shift_hours()


def calculate_wages(summary: Summary, rates: dict | None = None,
                    employees: dict | None = None) -> Wages:
    """Начислить зарплату. Ставка — руб/смена 8ч (Decimal), итог — копейки HALF_UP.

    Роли 1,4: будни = rate*дни + 1.5*(rate/8)*переработка_ч - (rate/8)*недоработка_ч;
      выходные = 1.5*(rate/8)*факт_ч; отпуск = rate*дни.
    Роль 2 (кладовщик): без оплаты переработок, выходные по одинарной ставке.
    Роль 3: rate*(будни+выходные), без молока.
    Молоко: 40.00 * (будни_дни + выходные_дни).
    Квантование только финального итога (промежуточное — полная точность).

    rates=None — ставки из wage_rates.dat; основной сценарий грузит их один раз
    после set_secret_key и передаёт явно. employees=None — DAT-справочник запуска.
    """
    if rates is None:
        rates = load_wage_rates()
    staff = staff_or_default(employees)
    result: Wages = {}
    for emp_id, data in summary.items():
        emp = staff.get(emp_id)
        if emp is None or emp.role_id not in (1, 2, 3, 4):
            continue
        work_days, overtime_wd, undertime_wd = data.work.days, data.work.overtime, data.work.undertime
        hol_days, hol_worked = data.holiday.days, data.holiday.worked
        vacation_days = data.vacation_days
        rate = _rate_for(rates, emp_id)
        if emp.role_id == 3:
            salary = rate * (work_days + hol_days)
            milk = Decimal('0.00')
        else:
            hourly = _hourly_fraction(rate)
            overtime_h = timedelta_to_hours(overtime_wd)
            undertime_h = timedelta_to_hours(undertime_wd)
            worked_holiday_h = timedelta_to_hours(hol_worked)
            # Legacy-кладовщик: без оплаты сверхурочных, выходные по одинарной.
            weekday_coef = Decimal('0') if emp.role_id == 2 else OVERTIME_WEEKDAY_MULTIPLIER
            weekend_coef = Decimal('1') if emp.role_id == 2 else OVERTIME_WEEKEND_MULTIPLIER
            salary_weekdays = (rate * work_days + weekday_coef * hourly * overtime_h
                               - hourly * undertime_h)
            # Весь факт выходного уже здесь: отклонения повторно не оплачиваются.
            salary_weekends = weekend_coef * hourly * worked_holiday_h
            salary = salary_weekdays + salary_weekends + rate * vacation_days
            milk = MILK_ALLOWANCE_PER_DAY * (work_days + hol_days)
        total = quantize_money(salary)
        result[emp_id] = WageResult(
            salary=total,
            milk=quantize_money(milk),
            total_with_milk=quantize_money(total + milk),
        )
    return result
