"""П.2-продолжение: единые теги + явные employees в отчетах."""

from datetime import timedelta
from decimal import Decimal


def make_dt(date_str, time_str):
    from datetime import datetime
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestDayTags:
    def test_values_frozen(self):
        from core import day_models as dm
        assert (dm.TAG_WORK, dm.TAG_WEEKEND, dm.TAG_HOLIDAY,
                dm.TAG_VACATION, dm.TAG_TRUANCY) == (
            'work', 'weekend', 'holiday', 'vacation', 'truancy')
        assert dm.OVERTIME == 'переработка'
        assert dm.UNDERTIME == 'недоработка'
        assert set(dm.ALLOWED_TAGS) == {
            'work', 'weekend', 'holiday', 'vacation', 'truancy'}

    def test_calculations_use_constants(self, setup_employees):
        from core.calculations import calculate_hours_per_day
        from core.day_models import TAG_WORK
        date_key = '2026-07-06'
        tt = {date_key: {101: [make_dt(date_key, '16:00:00'),
                               make_dt(date_key, '08:00:00'), TAG_WORK]}}
        assert calculate_hours_per_day(tt)[date_key][101].day_tag == TAG_WORK


class TestExplicitEmployeesReports:
    def test_preview_and_dashboard_use_passed_staff(self, setup_employees):
        from core.ui import build_dashboard_rows, build_preview_rows
        from core.config import EmployeeData
        staff = dict(setup_employees)
        staff[999] = EmployeeData(999, 'Н', 'Новичок', 1, 'Р')
        rows = build_dashboard_rows({}, [999], 2026, 7, employees=staff)
        assert rows[0]['name'] == 'Новичок Н'
        summary = {999: ((1, timedelta(0), timedelta(0)),
                         (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        wages = {999: (Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))}
        # без employees fallback тоже работает, но с явным — имя из staff
        preview = build_preview_rows(summary, wages, employees=staff)
        assert preview[0]['name'] == 'Новичок Н'

    def test_html_excel_builders_accept_employees(self, setup_employees, tmp_path, monkeypatch):
        from core import html_builder, excel_builder
        from core.day_models import DayMark, DayWork, EmployeeMonth, HolidayGroup, WorkGroup, WageResult
        monkeypatch.chdir(tmp_path)
        date_key = '2026-07-06'
        tt = {date_key: {101: DayMark(go=make_dt(date_key, '16:00:00'),
                                      come=make_dt(date_key, '08:00:00'), tag='work')}}
        wt = {date_key: {101: DayWork(delta=timedelta(0), worked=timedelta(hours=8),
                                      overtime_tag='недоработка', day_tag='work')}}
        summary = {101: EmployeeMonth(work=WorkGroup(1, timedelta(0), timedelta(0)),
                                      holiday=HolidayGroup(0, timedelta(0), timedelta(0), timedelta(0)),
                                      vacation_days=0, truancy_days=0)}
        wages = {101: WageResult(Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))}
        f = html_builder.build_html(101, tt, wt, summary, wages, employees=setup_employees)
        assert f and tmp_path.joinpath(f).exists()
        x = excel_builder.build_excel(tt, wt, summary, wages, employees=setup_employees)
        assert x and tmp_path.joinpath(x).exists()
