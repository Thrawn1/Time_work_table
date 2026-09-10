from datetime import datetime, timedelta
from decimal import Decimal
from core.calculations import (
    str_timedelta,
    calculate_hours_per_day,
    calculate_hours_per_month,
    calculate_wages,
)


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
        # -1800с -> -1ч +3599с? Текущий формат даёт '-1:30:00' через floor-деление.
        # Проверяем именно возвращаемую строку, а не исходный timedelta.
        assert result == '-1:30:00'

    def test_negative_1h30m(self):
        td = timedelta(hours=-1, minutes=-30)
        result = str_timedelta(td)
        assert result == '-2:30:00'

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
    """Ставка — руб/смена 8ч (Decimal). 800/смена: день=800, выходной 8ч=1200."""

    def test_role1_standard_8h(self, setup_employees, mock_wage_rates):
        """8-hour day, no overtime: 800 * 1 = 800."""
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
        # rate=800 руб/смена, 1 смена: 800
        assert total == Decimal('800.00')
        assert milk == Decimal('40.00')  # 1 day * 40
        assert total_with_milk == Decimal('840.00')

    def test_role1_with_overtime(self, setup_employees, mock_wage_rates):
        """1 day worked + 2h overtime: 800 + 1.5*100*2 = 1100."""
        summary = {
            101: (
                (1, timedelta(hours=2), timedelta(0)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        assert total == Decimal('1100.00')
        assert milk == Decimal('40.00')
        assert total_with_milk == Decimal('1140.00')

    def test_role1_undertime_reduces_salary_correctly(self, setup_employees, mock_wage_rates):
        """P1 #3 FIX: 2h workday reduces salary by regular hourly fraction, not 1.5x."""
        summary = {
            101: (
                (1, timedelta(0), timedelta(hours=6)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        # 800 - (800/8)*6 = 800 - 600 = 200
        assert total == Decimal('200.00')
        assert total > 0  # FIX: no longer negative

    def test_role1_weekend_pay(self, setup_employees, mock_wage_rates):
        """Weekend work: 1.5 * (800/8) * 8h = 1200."""
        worked = timedelta(hours=8)
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), worked),  # 1 day, 0 overtime, 0 undertime, 8h worked
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        assert total == Decimal('1200.00')
        assert milk == Decimal('40.00')  # weekends also get milk
        assert total_with_milk == Decimal('1240.00')

    def test_role1_vacation_pay(self, setup_employees, mock_wage_rates):
        """Vacation: 800 * days = 800 * 5 = 4000."""
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
        assert total == Decimal('4000.00')
        assert milk == Decimal('0.00')  # no work days -> no milk
        assert total_with_milk == total

    def test_role1_mixed_month(self, setup_employees, mock_wage_rates):
        """20 work days, 2 weekend days (8h fact), 1 vacation."""
        weekend_worked = timedelta(hours=8)
        weekend_overwork = timedelta(hours=3)
        expected_weekday = Decimal('800') * 20  # 16000
        # Выходные оплачиваются только по факту: 1.5x * (rate/8) * hours.
        # overtime/undertime из summary в оплату не входят (уже сидят в worked).
        expected_weekend = Decimal('1.5') * (Decimal('800') / 8) * Decimal('8')  # 1200
        expected_vacation = Decimal('800') * 1  # 800
        summary = {
            101: (
                (20, timedelta(0), timedelta(0)),
                (2, weekend_overwork, timedelta(0), weekend_worked),
                1, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        expected_total = expected_weekday + expected_weekend + expected_vacation
        assert total == expected_total == Decimal('18000.00')
        assert milk == Decimal('880.00')  # 22 * 40

    def test_role3_monthly_salary(self, setup_employees, mock_wage_rates):
        """Role 3: 800 * (work_days + holiday_days) = 800*22."""
        summary = {
            102: (
                (22, timedelta(0), timedelta(0)),
                (0, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[102]
        assert total == Decimal('17600.00')
        assert milk == Decimal('0.00')
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
        assert milk == Decimal('0.00')

    def test_short_weekend_never_negative(self, setup_employees, mock_wage_rates):
        """Регрессия: 2ч в выходной + недоработка 6ч -> 300, а не минус."""
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(hours=6), timedelta(hours=2)),
                0, 0,
            )
        }
        total, milk, total_with_milk = calculate_wages(summary)[101]
        assert total == Decimal('300.00')
        assert total >= 0

    def test_weekend_overtime_not_double_counted(self, setup_employees, mock_wage_rates):
        """Регрессия: 10ч в выходной (8+2) -> 1500, а не 1950."""
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(hours=2), timedelta(0), timedelta(hours=10)),
                0, 0,
            )
        }
        total, _, _ = calculate_wages(summary)[101]
        assert total == Decimal('1500.00')
