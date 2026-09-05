from datetime import timedelta
from core.config import EMPLOYEES, load_wage_rates
from core.constants import WORKING_DAY_HOURS, MILK_ALLOWANCE_PER_DAY, OVERTIME_WEEKDAY_MULTIPLIER


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
            if emp.role_id in (1, 4):
                worked = marks[0] - marks[1]
                standard = timedelta(hours=WORKING_DAY_HOURS)
                delta = worked - standard
                abs_delta = abs(delta)
                tag_overtime = 'переработка' if delta > timedelta(0) else 'недоработка'
                tag_day = marks[2]
                result[date_key][emp_id] = (abs_delta, worked, tag_overtime, tag_day)
            elif emp.role_id == 3:
                result[date_key][emp_id] = (
                    timedelta(0), timedelta(hours=WORKING_DAY_HOURS), '', 'work'
                )
    return result


def calculate_hours_per_month(work_time: dict) -> tuple[dict[int, tuple], dict]:
    restructured: dict[int, list] = {}
    for date_key, employees in work_time.items():
        for emp_id, data in employees.items():
            if emp_id not in restructured:
                restructured[emp_id] = [[], [], [], []]
            tag_day = data[3]
            cell = (data[0], data[2], date_key)
            if tag_day == 'work':
                restructured[emp_id][0].append(cell)
            elif tag_day == 'weekend':
                restructured[emp_id][1].append(cell)
            elif tag_day == 'vacation':
                restructured[emp_id][2].append(cell)
            elif tag_day == 'truancy':
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
        for delta, tag, _ in holiday_days:
            if tag == 'переработка':
                overtime_weekend += delta
        summary[emp_id] = (
            (total_work, overtime_weekday, undertime_weekday),
            (total_holiday, overtime_weekend),
            vacation_days,
            truancy_days,
        )
    return summary, restructured


def calculate_wages(summary: dict) -> dict[int, tuple[float, float, float]]:
    rates = load_wage_rates()
    result: dict[int, tuple[float, float, float]] = {}
    for emp_id, data in summary.items():
        emp = EMPLOYEES.get(emp_id)
        if emp is None:
            continue
        if emp.role_id in (1, 4):
            rate = rates.get(emp_id, 0)
            work_shift_secs = WORKING_DAY_HOURS * 3600
            rate_per_second = rate / work_shift_secs
            work_weekdays = data[0][0]
            overtime_weekday = data[0][1]
            undertime_weekday = data[0][2]
            work_holidays = data[1][0]
            overtime_holiday = data[1][1]
            vacation_days = data[2]
            money_for_milk = (work_weekdays + work_holidays) * MILK_ALLOWANCE_PER_DAY
            salary_weekdays = (rate * work_weekdays
                               + OVERTIME_WEEKDAY_MULTIPLIER * rate_per_second * overtime_weekday.total_seconds()
                               - rate_per_second * undertime_weekday.total_seconds())
            salary_weekends = (1.5 * rate * work_holidays
                               + 1.5 * OVERTIME_WEEKDAY_MULTIPLIER * rate_per_second * overtime_holiday.total_seconds())
            salary_vacation = rate * vacation_days
            total = round(salary_weekdays + salary_weekends + salary_vacation, 2)
            total_with_milk = total + money_for_milk
            result[emp_id] = (total, money_for_milk, total_with_milk)
        elif emp.role_id == 3:
            rate = rates.get(emp_id, 0)
            total = (data[0][0] + data[1][0]) * rate
            result[emp_id] = (total, 0, total)
    return result


