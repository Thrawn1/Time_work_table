"""Именованные структуры дня: доступ только по полям, производители отдают модели."""

from datetime import datetime, timedelta
from decimal import Decimal
from core.day_models import DayMark


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestModelsAreNamedOnly:
    def test_daymark_fields_and_equality(self):
        dt_go = make_dt('2026-07-06', '16:00:00')
        dt_come = make_dt('2026-07-06', '08:00:00')
        m = DayMark(go=dt_go, come=dt_come, tag='work')
        assert (m.go, m.come, m.tag) == (dt_go, dt_come, 'work')
        assert m == DayMark(dt_go, dt_come, 'work')

    def test_no_positional_protocol(self):
        """Индексы и распаковка больше не поддерживаются — только имена полей."""
        import pytest
        dt = make_dt('2026-07-06', '08:00:00')
        m = DayMark(go=dt, come=dt, tag='work')
        with pytest.raises(TypeError):
            m[0]
        with pytest.raises(TypeError):
            list(m)
        assert m != [dt, dt, 'work']


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

    def test_calculations_return_named(self, setup_employees):
        from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
        from core.day_models import DayMark, DayWork, EmployeeMonth, WageResult
        date_key = '2026-07-06'
        tt = {date_key: {101: DayMark(go=make_dt(date_key, '16:00:00'),
                                      come=make_dt(date_key, '08:00:00'), tag='work')}}
        wt = calculate_hours_per_day(tt)
        assert isinstance(wt[date_key][101], DayWork)
        assert wt[date_key][101].worked == timedelta(hours=8)
        summary = calculate_hours_per_month(wt)
        assert isinstance(summary[101], EmployeeMonth)
        assert summary[101].work.days == 1
        wages = calculate_wages(summary)
        assert isinstance(wages[101], WageResult)

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
        summary = calculate_hours_per_month(wt)
        wages = calculate_wages(summary)
        assert summary[101].work.days == 1
        assert wages[101].salary == Decimal('800.00')
