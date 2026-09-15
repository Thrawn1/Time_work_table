from datetime import timedelta
from decimal import Decimal
from core.config import EMPLOYEES, load_wage_rates
from core.constants import (
    WORKING_DAY_HOURS,
    MILK_ALLOWANCE_PER_DAY,
    OVERTIME_WEEKDAY_MULTIPLIER,
    OVERTIME_WEEKEND_MULTIPLIER,
)
from core.money import as_decimal, quantize_money, timedelta_to_hours
from core.roles import TIME_ACTUAL, TIME_FIXED_SHIFT, get_default_rule
from core.day_models import (
    ATTENDANCE_TAGS,
    NO_OVERTIME,
    OVERTIME,
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


def _mark_go(marks):
    return getattr(marks, 'go', marks[0])


def _mark_come(marks):
    return getattr(marks, 'come', marks[1])


def _mark_tag(marks):
    return getattr(marks, 'tag', marks[2])


def _work_delta(entry):
    return getattr(entry, 'delta', entry[0])


def _work_worked(entry):
    return getattr(entry, 'worked', entry[1])


def _work_overtime_tag(entry):
    return getattr(entry, 'overtime_tag', entry[2])


def _work_day_tag(entry):
    return getattr(entry, 'day_tag', entry[3])


def _sum_work(entry):
    work = getattr(entry, 'work', None)
    if work is None:
        try:
            work = entry[0]
        except (IndexError, KeyError, TypeError):
            work = None
    if work is None:
        return 0, timedelta(0), timedelta(0)
    if hasattr(work, 'days'):
        return work.days, work.overtime, work.undertime
    try:
        days = work[0]
    except (IndexError, KeyError, TypeError):
        days = 0
    try:
        over = work[1]
    except (IndexError, KeyError, TypeError):
        over = timedelta(0)
    try:
        under = work[2]
    except (IndexError, KeyError, TypeError):
        under = timedelta(0)
    return days, over, under


def _sum_holiday(entry):
    hol = getattr(entry, 'holiday', None)
    if hol is None:
        try:
            hol = entry[1]
        except (IndexError, KeyError, TypeError):
            hol = None
    if hol is None:
        return 0, timedelta(0), timedelta(0), timedelta(0)
    if hasattr(hol, 'days'):
        return hol.days, hol.overtime, hol.undertime, hol.worked
    try:
        days = hol[0]
    except (IndexError, KeyError, TypeError):
        days = 0
    try:
        over = hol[1]
    except (IndexError, KeyError, TypeError):
        over = timedelta(0)
    try:
        under = hol[2]
    except (IndexError, KeyError, TypeError):
        under = timedelta(0)
    try:
        worked = hol[3]
    except (IndexError, KeyError, TypeError):
        worked = timedelta(0)
    return days, over, under, worked


def _sum_vacation(entry):
    val = getattr(entry, 'vacation_days', None)
    if val is not None:
        return val
    try:
        return entry[2]
    except (IndexError, KeyError, TypeError):
        return 0


def _sum_truancy(entry):
    val = getattr(entry, 'truancy_days', None)
    if val is not None:
        return val
    try:
        return entry[3]
    except (IndexError, KeyError, TypeError):
        return 0


def str_timedelta(td: timedelta) -> str:
    total = int(td.total_seconds())
    h = total // 3600
    m = (total - h * 3600) // 60
    s = total - h * 3600 - m * 60
    return f'{h:02d}:{m:02d}:{s:02d}'


def calculate_hours_per_day(time_table: TimeTable, employees: dict | None = None) -> WorkTime:
    """Учёт времени по единым правилам ролей (core.roles), без решений по ID.

    time_mode 'actual': факт = выход − вход, переработка/недоработка от 8 ч.
    time_mode 'fixed_shift': 8 ч за рабочий выход независимо от отметок.
    Роль вне участия (напр. 0) в результат не попадает — её состав
    определяется фильтром участников до расчёта.

    employees=None — fallback к глобалу core.config.EMPLOYEES ради старых
    тестов; новый код передает справочник явно.
    """
    # NOTE: читаем модуль-глобал на каждый вызов (не кэшируем в аргументе),
    # чтобы monkeypatch в тестах продолжал работать.
    import core.calculations as _self

    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    result: WorkTime = {}
    for date_key, employees_in_day in time_table.items():
        result[date_key] = {}
        for emp_id, marks in employees_in_day.items():
            emp = staff.get(emp_id)
            if emp is None:
                continue
            rule = get_default_rule(emp.role_id)
            if not rule.participates:
                continue
            if rule.time_mode == TIME_ACTUAL:
                worked = _mark_go(marks) - _mark_come(marks)
                standard = timedelta(hours=WORKING_DAY_HOURS)
                delta = worked - standard
                abs_delta = abs(delta)
                tag_overtime = OVERTIME if delta > timedelta(0) else UNDERTIME
                tag_day = _mark_tag(marks)
                result[date_key][emp_id] = DayWork(
                    delta=abs_delta, worked=worked,
                    overtime_tag=tag_overtime, day_tag=tag_day,
                )
            elif rule.time_mode == TIME_FIXED_SHIFT:
                tag_day = _mark_tag(marks)
                if tag_day in (TAG_VACATION, TAG_TRUANCY):
                    result[date_key][emp_id] = DayWork(
                        delta=timedelta(0), worked=timedelta(0),
                        overtime_tag=NO_OVERTIME, day_tag=tag_day,
                    )
                elif tag_day in ATTENDANCE_TAGS:
                    result[date_key][emp_id] = DayWork(
                        delta=timedelta(0), worked=timedelta(hours=WORKING_DAY_HOURS),
                        overtime_tag=NO_OVERTIME, day_tag=tag_day,
                    )
                else:
                    # Неизвестный тег — не выдумываем рабочий день, сохраняем как есть с 0ч
                    result[date_key][emp_id] = DayWork(
                        delta=timedelta(0), worked=timedelta(0),
                        overtime_tag=NO_OVERTIME, day_tag=tag_day,
                    )
    return result


def calculate_hours_per_month(work_time: WorkTime) -> tuple[Summary, dict]:
    restructured: dict[int, list] = {}
    for date_key, employees in work_time.items():
        for emp_id, data in employees.items():
            if emp_id not in restructured:
                restructured[emp_id] = [[], [], [], []]
            tag_day = _work_day_tag(data)
            if tag_day == TAG_WORK:
                cell = (_work_delta(data), _work_overtime_tag(data), date_key)
                restructured[emp_id][0].append(cell)
            elif tag_day in WEEKEND_TAGS:
                cell = (_work_delta(data), _work_overtime_tag(data), _work_worked(data), date_key)
                restructured[emp_id][1].append(cell)
            elif tag_day == TAG_VACATION:
                cell = (_work_delta(data), _work_overtime_tag(data), date_key)
                restructured[emp_id][2].append(cell)
            elif tag_day == TAG_TRUANCY:
                cell = (_work_delta(data), _work_overtime_tag(data), date_key)
                restructured[emp_id][3].append(cell)
    summary: Summary = {}
    for emp_id, groups in restructured.items():
        work_days = groups[0]
        holiday_days = groups[1]
        vacation_days = len(groups[2])
        truancy_days = len(groups[3])
        total_work = len(work_days)
        total_holiday = len(holiday_days)
        overtime_weekday = timedelta(0)
        undertime_weekday = timedelta(0)
        for delta, tag, _ in work_days:
            if tag == OVERTIME:
                overtime_weekday += delta
            else:
                undertime_weekday += delta
        overtime_weekend = timedelta(0)
        undertime_weekend = timedelta(0)
        total_worked_weekend = timedelta(0)
        for delta, tag, worked, _ in holiday_days:
            total_worked_weekend += worked
            if tag == OVERTIME:
                overtime_weekend += delta
            else:
                undertime_weekend += delta
        summary[emp_id] = EmployeeMonth(
            work=WorkGroup(days=total_work, overtime=overtime_weekday, undertime=undertime_weekday),
            holiday=HolidayGroup(
                days=total_holiday, overtime=overtime_weekend,
                undertime=undertime_weekend, worked=total_worked_weekend,
            ),
            vacation_days=vacation_days,
            truancy_days=truancy_days,
        )
    return summary, restructured


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

    rates/employees=None — fallback к глобалам ради старых тестов; новый код
    (main.py) грузит ставки один раз после set_secret_key и передает явно.
    """
    import core.calculations as _self

    if rates is None:
        rates = load_wage_rates()
    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    result: Wages = {}
    for emp_id, data in summary.items():
        emp = staff.get(emp_id)
        if emp is None:
            continue
        work_days, overtime_wd, undertime_wd = _sum_work(data)
        hol_days, _overtime_we, _undertime_we, hol_worked = _sum_holiday(data)
        vacation_days = _sum_vacation(data)
        if emp.role_id in (1, 4):
            rate = _rate_for(rates, emp_id)
            hourly = _hourly_fraction(rate)
            work_weekdays = work_days
            overtime_h = timedelta_to_hours(overtime_wd)
            undertime_h = timedelta_to_hours(undertime_wd)
            work_holidays = hol_days
            # overtime/undertime выходных в оплату не входят отдельно:
            # total_worked_holiday уже содержит весь факт (иначе 2.25x / минусы).
            worked_holiday_h = timedelta_to_hours(hol_worked)
            money_for_milk = MILK_ALLOWANCE_PER_DAY * (work_weekdays + work_holidays)
            salary_weekdays = (rate * work_weekdays
                               + OVERTIME_WEEKDAY_MULTIPLIER * hourly * overtime_h
                               - hourly * undertime_h)
            salary_weekends = OVERTIME_WEEKEND_MULTIPLIER * hourly * worked_holiday_h
            salary_vacation = rate * vacation_days
            total = quantize_money(salary_weekdays + salary_weekends + salary_vacation)
            total_with_milk = quantize_money(total + money_for_milk)
            result[emp_id] = WageResult(
                salary=total,
                milk=quantize_money(money_for_milk),
                total_with_milk=total_with_milk,
            )
        elif emp.role_id == 2:
            # Кладовщик: как обычный работник, но без оплаты переработок.
            # Будни: ставка за дни минус недоработка (сверхурочные не плюсуются).
            # Выходные: факт по одинарной ставке (без 1.5x). Отпуск/молоко — как у роли 1.
            rate = _rate_for(rates, emp_id)
            hourly = _hourly_fraction(rate)
            work_weekdays = work_days
            undertime_h = timedelta_to_hours(undertime_wd)
            work_holidays = hol_days
            worked_holiday_h = timedelta_to_hours(hol_worked)
            money_for_milk = MILK_ALLOWANCE_PER_DAY * (work_weekdays + work_holidays)
            salary_weekdays = (rate * work_weekdays
                               - hourly * undertime_h)
            salary_weekends = hourly * worked_holiday_h
            salary_vacation = rate * vacation_days
            total = quantize_money(salary_weekdays + salary_weekends + salary_vacation)
            total_with_milk = quantize_money(total + money_for_milk)
            result[emp_id] = WageResult(
                salary=total,
                milk=quantize_money(money_for_milk),
                total_with_milk=total_with_milk,
            )
        elif emp.role_id == 3:
            rate = _rate_for(rates, emp_id)
            total = quantize_money(rate * (work_days + hol_days))
            result[emp_id] = WageResult(
                salary=total, milk=Decimal('0.00'), total_with_milk=total,
            )
    return result


