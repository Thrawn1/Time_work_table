from datetime import datetime, timedelta
from core.calculations import (
    str_timedelta,
    calculate_hours_per_day,
    calculate_hours_per_month,
    calculate_wages,
)
from core.constants import OVERTIME_WEEKDAY_MULTIPLIER


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


# --- str_timedelta ---

class TestStrTimedelta:
    def test_zero(self):
        assert str_timedelta(timedelta(0)) == '00:00:00'

    def test_positive_hours(self):
        assert str_timedelta(timedelta(hours=8)) == '08:00:00'

    def test_positive_complex(self):
        assert str_timedelta(timedelta(hours=10, minutes=30, seconds=15)) == '10:30:15'

    def test_large(self):
        assert str_timedelta(timedelta(hours=100, minutes=5, seconds=59)) == '100:05:59'

    def test_negative_30min(self):
        td = timedelta(minutes=-30)
        result = str_timedelta(td)
        total = int(td.total_seconds())
        assert total == -1800

    def test_negative_1h30m(self):
        td = timedelta(hours=-1, minutes=-30)
        result = str_timedelta(td)
        total = int(td.total_seconds())
        assert total == -5400

    def test_one_minute(self):
        assert str_timedelta(timedelta(minutes=1)) == '00:01:00'

    def test_seconds_only(self):
        assert str_timedelta(timedelta(seconds=45)) == '00:00:45'


# --- calculate_hours_per_day ---

class TestCalculateHoursPerDay:

    def test_role1_normal_workday(self, setup_employees):
        """8-hour workday: delta=0, tag=work."""
        date_key = '2026-07-06'  # Monday
        time_table = {
            date_key: {
                101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][101]
        assert worked == timedelta(hours=8)
        assert abs_delta == timedelta(0)
        assert tag_day == 'work'

    def test_role1_overtime(self, setup_employees):
        """10-hour workday: 2h overtime."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                101: [make_dt(date_key, '18:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][101]
        assert worked == timedelta(hours=10)
        assert abs_delta == timedelta(hours=2)
        assert tag_overtime == 'переработка'

    def test_role1_undertime(self, setup_employees):
        """6-hour workday: 2h undertime."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                101: [make_dt(date_key, '14:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][101]
        assert worked == timedelta(hours=6)
        assert abs_delta == timedelta(hours=2)
        assert tag_overtime == 'недоработка'

    def test_role1_2h_workday(self, setup_employees):
        """P1 #3: 2-hour workday should NOT give negative wages."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                101: [make_dt(date_key, '10:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][101]
        assert worked == timedelta(hours=2)
        assert abs_delta == timedelta(hours=6)
        assert tag_overtime == 'недоработка'

    def test_role1_weekend_day(self, setup_employees):
        """Weekend day is tagged correctly."""
        date_key = '2026-07-04'  # Saturday
        time_table = {
            date_key: {
                101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'weekend'],
            }
        }
        result = calculate_hours_per_day(time_table)
        _, _, _, tag_day = result[date_key][101]
        assert tag_day == 'weekend'

    def test_role1_holiday_day(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """P1 #1: Holiday should be preserved in daily calculation."""
        date_key = '2026-01-01'
        time_table = {
            date_key: {
                101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'holiday'],
            }
        }
        result = calculate_hours_per_day(time_table)
        _, _, _, tag_day = result[date_key][101]
        assert tag_day == 'holiday'

    def test_role3_always_full_day(self, setup_employees):
        """P1 #2: Role 3 always returns 8h, '', 'work' regardless of tag."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                102: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][102]
        assert worked == timedelta(hours=8)
        assert abs_delta == timedelta(0)
        assert tag_overtime == ''
        assert tag_day == 'work'

    def test_role3_vacation_preserved(self, setup_employees):
        """P1 #2 FIXED: Role 3 with vacation tag preserves 'vacation' status."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                102: [make_dt(date_key, '00:00:01'), make_dt(date_key, '00:00:01'), 'vacation'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][102]
        assert tag_day == 'vacation'
        assert worked == timedelta(0)

    def test_role3_truancy_preserved(self, setup_employees):
        """P1 #2 FIXED: Role 3 with truancy tag preserves 'truancy' status."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                102: [make_dt(date_key, '23:59:59'), make_dt(date_key, '23:59:59'), 'truancy'],
            }
        }
        result = calculate_hours_per_day(time_table)
        _, _, _, tag_day = result[date_key][102]
        assert tag_day == 'truancy'

    def test_role4_works_like_role1(self, setup_employees):
        """Role 4 should behave like role 1."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                103: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][103]
        assert worked == timedelta(hours=8)
        assert abs_delta == timedelta(0)

    def test_unknown_employee_skipped(self, setup_employees):
        """Unknown employee ID is silently skipped."""
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                999: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'work'],
            }
        }
        result = calculate_hours_per_day(time_table)
        assert 999 not in result[date_key]


# --- calculate_hours_per_month ---

class TestCalculateHoursPerMonth:

    def _build_work_time(self, entries):
        """Helper: build work_time dict from daily calculation results."""
        work_time = {}
        for date_key, emp_id, abs_delta, worked, tag_overtime, tag_day in entries:
            if date_key not in work_time:
                work_time[date_key] = {}
            work_time[date_key][emp_id] = (abs_delta, worked, tag_overtime, tag_day)
        return work_time

    def test_single_workday(self, setup_employees):
        """One normal workday."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(0), timedelta(hours=8), '', 'work'),
        ])
        summary, restructured = calculate_hours_per_month(work_time)
        total_work, overtime_wd, undertime_wd = summary[101][0]
        total_holiday, overtime_we, undertime_we, total_worked_we = summary[101][1]
        vacation = summary[101][2]
        truancy = summary[101][3]
        assert total_work == 1
        assert total_holiday == 0
        assert vacation == 0
        assert truancy == 0
        assert overtime_wd == timedelta(0)
        assert undertime_wd == timedelta(0)

    def test_undertime_separate_from_overtime(self, setup_employees):
        """P1 #3 FIX: Undertime is tracked separately, not mixed with overtime."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(hours=6), timedelta(hours=2), 'недоработка', 'work'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        _, overtime_wd, undertime_wd = summary[101][0]
        # FIX: undertime goes to separate field, overtime stays zero
        assert overtime_wd == timedelta(0)
        assert undertime_wd == timedelta(hours=6)

    def test_overtime_positive(self, setup_employees):
        """Normal overtime adds up."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(hours=2), timedelta(hours=10), 'переработка', 'work'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        _, overtime_wd, undertime_wd = summary[101][0]
        assert overtime_wd == timedelta(hours=2)
        assert undertime_wd == timedelta(0)

    def test_weekend_overtime_only_positive(self, setup_employees):
        """P1 #4: Weekend overwork only counts positive deltas."""
        work_time = self._build_work_time([
            ('2026-07-04', 101, timedelta(hours=2), timedelta(hours=10), 'переработка', 'weekend'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        total_holiday, overtime_we, undertime_we, total_worked_we = summary[101][1]
        assert total_holiday == 1
        assert overtime_we == timedelta(hours=2)
        assert total_worked_we == timedelta(hours=10)

    def test_vacation_counted(self, setup_employees):
        """Vacation days are counted separately."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(0), timedelta(hours=8), '', 'vacation'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        vacation = summary[101][2]
        assert vacation == 1

    def test_truancy_counted(self, setup_employees):
        """Truancy days are counted separately."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(0), timedelta(hours=8), '', 'truancy'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        truancy = summary[101][3]
        assert truancy == 1

    def test_multiple_days_mixed(self, setup_employees):
        """Mix of work, weekend, vacation, truancy."""
        work_time = self._build_work_time([
            ('2026-07-06', 101, timedelta(0), timedelta(hours=8), '', 'work'),
            ('2026-07-07', 101, timedelta(hours=1), timedelta(hours=9), 'переработка', 'work'),
            ('2026-07-04', 101, timedelta(hours=2), timedelta(hours=10), 'переработка', 'weekend'),
            ('2026-07-08', 101, timedelta(0), timedelta(0), '', 'vacation'),
            ('2026-07-09', 101, timedelta(0), timedelta(0), '', 'truancy'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        total_work, overtime_wd, undertime_wd = summary[101][0]
        total_holiday, overtime_we, undertime_we, total_worked_we = summary[101][1]
        vacation = summary[101][2]
        truancy = summary[101][3]
        assert total_work == 2
        assert total_holiday == 1
        assert vacation == 1
        assert truancy == 1
        assert overtime_wd == timedelta(hours=1)
        assert undertime_wd == timedelta(0)
        assert overtime_we == timedelta(hours=2)
        assert total_worked_we == timedelta(hours=10)

    def test_holiday_counted_in_monthly_aggregation(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """P1 #1 FIXED: Holiday tag is now recognized in monthly aggregation."""
        work_time = self._build_work_time([
            ('2026-01-01', 101, timedelta(hours=2), timedelta(hours=10), 'переработка', 'holiday'),
        ])
        summary, restructured = calculate_hours_per_month(work_time)
        total_work, _, _ = summary[101][0]
        total_holiday, overtime_we, _, total_worked_we = summary[101][1]
        # FIXED: holiday counted in total_holiday, not lost
        assert total_work == 0
        assert total_holiday == 1
        assert overtime_we == timedelta(hours=2)
        assert total_worked_we == timedelta(hours=10)

    def test_role3_monthly_summary(self, setup_employees):
        """Role 3: all days counted as work in monthly summary."""
        work_time = self._build_work_time([
            ('2026-07-06', 102, timedelta(0), timedelta(hours=8), '', 'work'),
            ('2026-07-07', 102, timedelta(0), timedelta(hours=8), '', 'work'),
        ])
        summary, _ = calculate_hours_per_month(work_time)
        total_work, _, _ = summary[102][0]
        assert total_work == 2


# --- calculate_wages ---

class TestCalculateWages:

    def test_role1_standard_8h(self, setup_employees, mock_wage_rates):
        """8-hour day, no overtime: rate * 1."""
        summary = {
            101: (
                (1, timedelta(0), timedelta(0)),   # work_days, overtime, undertime
                (0, timedelta(0), timedelta(0), timedelta(0)),   # holiday_days, overtime, undertime, worked
                0,  # vacation
                0,  # truancy
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        # rate=800, 1 day, no overtime: 800 * 1 = 800
        assert total == 800
        assert milk == 40  # 1 day * 40
        assert total_with_milk == 840

    def test_role1_with_overtime(self, setup_employees, mock_wage_rates):
        """1 day worked + 2h overtime."""
        rate = 800
        rate_per_sec = rate / (8 * 3600)
        overtime_secs = timedelta(hours=2).total_seconds()
        expected_salary = rate * 1 + 1.5 * rate_per_sec * overtime_secs
        summary = {
            101: (
                (1, timedelta(hours=2), timedelta(0)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        assert total == round(expected_salary, 2)
        assert milk == 40
        assert total_with_milk == round(expected_salary, 2) + 40

    def test_role1_undertime_reduces_salary_correctly(self, setup_employees, mock_wage_rates):
        """P1 #3 FIX: 2h workday reduces salary by regular rate, not 1.5x."""
        rate = 800
        rate_per_sec = rate / (8 * 3600)
        undertime_secs = timedelta(hours=6).total_seconds()
        # FIX: undertime subtracted at regular rate (not 1.5x)
        expected_salary = rate * 1 - rate_per_sec * undertime_secs
        summary = {
            101: (
                (1, timedelta(0), timedelta(hours=6)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        # 800 - (800/28800)*21600 = 800 - 600 = 200
        assert total == round(expected_salary, 2)
        assert total == 200
        assert total > 0  # FIX: no longer negative

    def test_role1_weekend_pay(self, setup_employees, mock_wage_rates):
        """Weekend work: 1.5 * rate_per_second * worked_seconds."""
        rate = 800
        rate_per_sec = rate / (8 * 3600)
        worked = timedelta(hours=8)
        expected_salary = round(1.5 * rate_per_sec * worked.total_seconds(), 2)
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), worked),  # 1 day, 0 overtime, 0 undertime, 8h worked
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        assert total == expected_salary
        assert milk == 40  # weekends also get milk
        assert total_with_milk == expected_salary + 40

    def test_role1_vacation_pay(self, setup_employees, mock_wage_rates):
        """Vacation: rate * days."""
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                5,  # 5 vacation days
                0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        assert total == 5 * 800
        assert milk == 0  # no work days -> no milk
        assert total_with_milk == total

    def test_role1_mixed_month(self, setup_employees, mock_wage_rates):
        """20 work days, 2 weekend days, 1 vacation."""
        rate = 800
        rate_per_sec = rate / (8 * 3600)
        weekend_worked = timedelta(hours=8)
        weekend_overwork = timedelta(hours=3)
        expected_weekday = rate * 20
        expected_weekend = (1.5 * rate_per_sec * weekend_worked.total_seconds()
                            + 1.5 * OVERTIME_WEEKDAY_MULTIPLIER * rate_per_sec * weekend_overwork.total_seconds())
        expected_vacation = rate * 1
        summary = {
            101: (
                (20, timedelta(0), timedelta(0)),
                (2, weekend_overwork, timedelta(0), weekend_worked),
                1, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        expected_total = round(expected_weekday + expected_weekend + expected_vacation, 2)
        assert total == expected_total
        assert milk == 22 * 40  # 20 work + 2 weekend

    def test_role3_monthly_salary(self, setup_employees, mock_wage_rates):
        """Role 3: flat rate * (work_days + holiday_days)."""
        summary = {
            102: (
                (22, timedelta(0), timedelta(0)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[102]
        assert total == 22 * 800
        assert milk == 0
        assert total_with_milk == total

    def test_role3_no_milk(self, setup_employees, mock_wage_rates):
        """Role 3 never gets milk allowance."""
        summary = {
            102: (
                (1, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        _, milk, _ = result[102]
        assert milk == 0
