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


def str_timedelta(td: timedelta) -> str:
    total = int(td.total_seconds())
    h = total // 3600
    m = (total - h * 3600) // 60
    s = total - h * 3600 - m * 60
    return f'{h:02d}:{m:02d}:{s:02d}'


def calculate_hours_per_day(time_table: dict) -> dict[str, dict[int, tuple]]:
    result: dict[str, dict[int, tuple]] = {}
    for date_key, employees in time_table.items():
        result[date_key] = {}
        for emp_id, marks in employees.items():
            emp = EMPLOYEES.get(emp_id)
            if emp is None:
                continue
            if emp.role_id in (1, 2, 4):
                worked = marks[0] - marks[1]
                standard = timedelta(hours=WORKING_DAY_HOURS)
                delta = worked - standard
                abs_delta = abs(delta)
                tag_overtime = 'переработка' if delta > timedelta(0) else 'недоработка'
                tag_day = marks[2]
                result[date_key][emp_id] = (abs_delta, worked, tag_overtime, tag_day)
            elif emp.role_id == 3:
                tag_day = marks[2]
                if tag_day in ('vacation', 'truancy'):
                    result[date_key][emp_id] = (
                        timedelta(0), timedelta(0), '', tag_day
                    )
                elif tag_day in ('work', 'weekend', 'holiday'):
                    result[date_key][emp_id] = (
                        timedelta(0), timedelta(hours=WORKING_DAY_HOURS), '', tag_day
                    )
                else:
                    # Неизвестный тег — не выдумываем рабочий день, сохраняем как есть с 0ч
                    result[date_key][emp_id] = (
                        timedelta(0), timedelta(0), '', tag_day
                    )
    return result


def calculate_hours_per_month(work_time: dict) -> tuple[dict[int, tuple], dict]:
    restructured: dict[int, list] = {}
    for date_key, employees in work_time.items():
        for emp_id, data in employees.items():
            if emp_id not in restructured:
                restructured[emp_id] = [[], [], [], []]
            tag_day = data[3]
            if tag_day == 'work':
                cell = (data[0], data[2], date_key)
                restructured[emp_id][0].append(cell)
            elif tag_day in ('weekend', 'holiday'):
                cell = (data[0], data[2], data[1], date_key)
                restructured[emp_id][1].append(cell)
            elif tag_day == 'vacation':
                cell = (data[0], data[2], date_key)
                restructured[emp_id][2].append(cell)
            elif tag_day == 'truancy':
                cell = (data[0], data[2], date_key)
                restructured[emp_id][3].append(cell)
    summary: dict[int, tuple] = {}
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
            if tag == 'переработка':
                overtime_weekday += delta
            else:
                undertime_weekday += delta
        overtime_weekend = timedelta(0)
        undertime_weekend = timedelta(0)
        total_worked_weekend = timedelta(0)
        for delta, tag, worked, _ in holiday_days:
            total_worked_weekend += worked
            if tag == 'переработка':
                overtime_weekend += delta
            else:
                undertime_weekend += delta
        summary[emp_id] = (
            (total_work, overtime_weekday, undertime_weekday),
            (total_holiday, overtime_weekend, undertime_weekend, total_worked_weekend),
            vacation_days,
            truancy_days,
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


def calculate_wages(summary: dict) -> dict[int, tuple[Decimal, Decimal, Decimal]]:
    """Начислить зарплату. Ставка — руб/смена 8ч (Decimal), итог — копейки HALF_UP.

    Роли 1,4: будни = rate*дни + 1.5*(rate/8)*переработка_ч - (rate/8)*недоработка_ч;
      выходные = 1.5*(rate/8)*факт_ч; отпуск = rate*дни.
    Роль 2 (кладовщик): без оплаты переработок, выходные по одинарной ставке.
    Роль 3: rate*(будни+выходные), без молока.
    Молоко: 40.00 * (будни_дни + выходные_дни).
    Квантование только финального итога (промежуточное — полная точность).
    """
    rates = load_wage_rates()
    result: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
    for emp_id, data in summary.items():
        emp = EMPLOYEES.get(emp_id)
        if emp is None:
            continue
        if emp.role_id in (1, 4):
            rate = _rate_for(rates, emp_id)
            hourly = _hourly_fraction(rate)
            work_weekdays = data[0][0]
            overtime_h = timedelta_to_hours(data[0][1])
            undertime_h = timedelta_to_hours(data[0][2])
            work_holidays = data[1][0]
            # overtime/undertime выходных в оплату не входят отдельно:
            # total_worked_holiday уже содержит весь факт (иначе 2.25x / минусы).
            worked_holiday_h = timedelta_to_hours(data[1][3])
            vacation_days = data[2]
            money_for_milk = MILK_ALLOWANCE_PER_DAY * (work_weekdays + work_holidays)
            salary_weekdays = (rate * work_weekdays
                               + OVERTIME_WEEKDAY_MULTIPLIER * hourly * overtime_h
                               - hourly * undertime_h)
            salary_weekends = OVERTIME_WEEKEND_MULTIPLIER * hourly * worked_holiday_h
            salary_vacation = rate * vacation_days
            total = quantize_money(salary_weekdays + salary_weekends + salary_vacation)
            total_with_milk = quantize_money(total + money_for_milk)
            result[emp_id] = (total, quantize_money(money_for_milk), total_with_milk)
        elif emp.role_id == 2:
            # Кладовщик: как обычный работник, но без оплаты переработок.
            # Будни: ставка за дни минус недоработка (сверхурочные не плюсуются).
            # Выходные: факт по одинарной ставке (без 1.5x). Отпуск/молоко — как у роли 1.
            rate = _rate_for(rates, emp_id)
            hourly = _hourly_fraction(rate)
            work_weekdays = data[0][0]
            undertime_h = timedelta_to_hours(data[0][2])
            work_holidays = data[1][0]
            worked_holiday_h = timedelta_to_hours(data[1][3])
            vacation_days = data[2]
            money_for_milk = MILK_ALLOWANCE_PER_DAY * (work_weekdays + work_holidays)
            salary_weekdays = (rate * work_weekdays
                               - hourly * undertime_h)
            salary_weekends = hourly * worked_holiday_h
            salary_vacation = rate * vacation_days
            total = quantize_money(salary_weekdays + salary_weekends + salary_vacation)
            total_with_milk = quantize_money(total + money_for_milk)
            result[emp_id] = (total, quantize_money(money_for_milk), total_with_milk)
        elif emp.role_id == 3:
            rate = _rate_for(rates, emp_id)
            total = quantize_money(rate * (data[0][0] + data[1][0]))
            result[emp_id] = (total, Decimal('0.00'), total)
    return result


