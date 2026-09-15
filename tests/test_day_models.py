"""П.1: именованные структуры дня — named-доступ + legacy-индексы."""

from datetime import datetime, timedelta
from decimal import Decimal


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestDayMark:
    def test_named_and_index_access(self):
        from core.day_models import DayMark
        dt_go = make_dt('2026-07-06', '16:00:00')
        dt_come = make_dt('2026-07-06', '08:00:00')
        m = DayMark(go=dt_go, come=dt_come, tag='work')
        assert m.go == dt_go
        assert m.come == dt_come
        assert m.tag == 'work'
        assert m[0] == dt_go
        assert m[1] == dt_come
        assert m[2] == 'work'
        assert list(m) == [dt_go, dt_come, 'work']
        assert len(m) == 3

    def test_mutation_both_styles(self):
        from core.day_models import DayMark
        m = DayMark(go=make_dt('2026-07-06', '17:00:00'),
                    come=make_dt('2026-07-06', '17:00:00'), tag='work')
        m.come = make_dt('2026-07-06', '08:00:00')
        assert m[1] == make_dt('2026-07-06', '08:00:00')
        m[0] = make_dt('2026-07-06', '18:00:00')
        assert m.go == make_dt('2026-07-06', '18:00:00')

    def test_eq_with_legacy_list(self):
        from core.day_models import DayMark
        dt = make_dt('2026-07-06', '08:00:00')
        assert DayMark(go=dt, come=dt, tag='work') == [dt, dt, 'work']


class TestDayWork:
    def test_named_and_index(self):
        from core.day_models import DayWork
        w = DayWork(delta=timedelta(hours=2), worked=timedelta(hours=10),
                    overtime_tag='переработка', day_tag='work')
        assert w.delta == timedelta(hours=2)
        assert w.worked == timedelta(hours=10)
        assert w[0] == timedelta(hours=2)
        assert w[1] == timedelta(hours=10)
        assert w[2] == 'переработка'
        assert w[3] == 'work'


class TestSummaryAndWages:
    def test_employee_month_index_compat(self):
        from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup
        s = EmployeeMonth(work=WorkGroup(1, timedelta(0), timedelta(0)),
                          holiday=HolidayGroup(0, timedelta(0), timedelta(0), timedelta(0)),
                          vacation_days=0, truancy_days=0)
        assert s[0][0] == 1
        assert s[1][0] == 0
        assert s[2] == 0
        assert s[3] == 0
        assert s.work.days == 1
        assert s.vacation_days == 0

    def test_wage_result(self):
        from core.day_models import WageResult
        w = WageResult(Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))
        assert w.salary == Decimal('800.00')
        assert w[0] == Decimal('800.00')
        assert w[1] == Decimal('40.00')
        assert w[2] == Decimal('840.00')


class TestProducersReturnNamed:
    def test_build_data_array_returns_daymark(self, setup_employees,
                                              mock_holidays_jan2026, mock_postponed_empty):
        from core.data_array import build_data_array
        from core.day_models import DayMark
        lines = ['        101\t2026-07-06 08:00:00\t1\t255\t1\t0']
        tt = build_data_array(lines)
        marks = tt['2026-07-06'][101]
        assert isinstance(marks, DayMark)
        assert marks.tag == 'work'
        # legacy-индексы живы
        assert marks[2] == 'work'

    def test_calculations_return_named(self, setup_employees):
        from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
        from core.day_models import DayMark, DayWork, EmployeeMonth, WageResult
        date_key = '2026-07-06'
        tt = {date_key: {101: DayMark(go=make_dt(date_key, '16:00:00'),
                                      come=make_dt(date_key, '08:00:00'), tag='work')}}
        wt = calculate_hours_per_day(tt)
        assert isinstance(wt[date_key][101], DayWork)
        assert wt[date_key][101].worked == timedelta(hours=8)
        summary, _ = calculate_hours_per_month(wt)
        assert isinstance(summary[101], EmployeeMonth)
        assert summary[101].work.days == 1
        wages = calculate_wages(summary)
        assert isinstance(wages[101], WageResult)

    def test_calculations_accept_legacy_lists(self, setup_employees):
        """Старые тесты/вызовы со списками продолжают считаться."""
        from core.calculations import calculate_hours_per_day
        date_key = '2026-07-06'
        tt = {date_key: {101: [make_dt(date_key, '16:00:00'),
                               make_dt(date_key, '08:00:00'), 'work']}}
        wt = calculate_hours_per_day(tt)
        assert wt[date_key][101].worked == timedelta(hours=8)
        assert wt[date_key][101][1] == timedelta(hours=8)

    def test_end_to_end_named(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Сквозной: DAT -> DayMark -> DayWork -> EmployeeMonth -> WageResult."""
        from core.data_array import build_data_array
        from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
        lines = [
            '        101\t2026-07-06 08:00:00\t1\t255\t1\t0',
            '        101\t2026-07-06 16:00:00\t1\t255\t1\t0',
        ]
        tt = build_data_array(lines)
        wt = calculate_hours_per_day(tt)
        summary, _ = calculate_hours_per_month(wt)
        wages = calculate_wages(summary)
        assert summary[101].work.days == 1
        assert wages[101].salary == Decimal('800.00')
