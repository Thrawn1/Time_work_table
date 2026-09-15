"""П.2: явные зависимости финпути + кэш календаря + одно чтение ставок."""

from datetime import datetime, timedelta
from decimal import Decimal


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestExplicitDeps:
    def test_calculate_wages_uses_passed_rates(self, setup_employees):
        from core.calculations import calculate_wages
        summary = {
            101: ((1, timedelta(0), timedelta(0)),
                  (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0),
        }
        custom = {101: Decimal('1000.00'), 102: Decimal('800.00'), 103: Decimal('800.00')}
        res = calculate_wages(summary, rates=custom, employees=setup_employees)
        assert res[101].salary == Decimal('1000.00')

    def test_calculate_hours_uses_passed_employees(self, setup_employees):
        from core.calculations import calculate_hours_per_day
        from core.config import EmployeeData
        date_key = '2026-07-06'
        tt = {date_key: {999: [make_dt(date_key, '16:00:00'),
                               make_dt(date_key, '08:00:00'), 'work']}}
        # без явного справочника неизвестный ID пропускается
        assert 999 not in calculate_hours_per_day(tt, employees=setup_employees)[date_key]
        staff = dict(setup_employees)
        staff[999] = EmployeeData(999, 'Н', 'Н', 1, 'Р', Decimal('0.00'))
        out = calculate_hours_per_day(tt, employees=staff)
        assert out[date_key][999].worked == timedelta(hours=8)

    def test_build_data_array_uses_passed_employees(self, setup_employees,
                                                    mock_holidays_jan2026, mock_postponed_empty):
        from core.data_array import build_data_array
        lines = ['        999\t2026-07-06 08:00:00\t1\t255\t1\t0']
        assert build_data_array(lines, employees=setup_employees) == {}
        staff = dict(setup_employees)
        from core.config import EmployeeData
        staff[999] = EmployeeData(999, 'Н', 'Н', 1, 'Р', Decimal('0.00'))
        assert '2026-07-06' in build_data_array(lines, employees=staff)


class TestCalendarCache:
    def test_single_read_per_year(self, monkeypatch):
        from core import file_parser
        file_parser.clear_calendar_cache()
        calls = {'h': 0, 'p': 0}
        real_h = file_parser.load_holidays.__wrapped__
        real_p = file_parser.load_postponed_days.__wrapped__

        def cnt_h(year):
            calls['h'] += 1
            return real_h(year)

        def cnt_p(year):
            calls['p'] += 1
            return real_p(year)

        monkeypatch.setattr(file_parser.load_holidays, 'cache_clear',
                            file_parser.load_holidays.cache_clear)
        # Подменяем wrapped-доступ через monkeypatch объекта кэша невозможен напрямую,
        # поэтому проверяем проще: повторные вызовы дают один и тот же объект (кэш).
        file_parser.clear_calendar_cache()
        a = file_parser.load_holidays(2026)
        b = file_parser.load_holidays(2026)
        assert a is b
        c = file_parser.load_postponed_days(2026)
        d = file_parser.load_postponed_days(2026)
        assert c is d

    def test_definition_uses_cache(self, mock_holidays_jan2026, mock_postponed_empty):
        from core.file_parser import clear_calendar_cache, definition_of_working_day
        clear_calendar_cache()
        assert definition_of_working_day('2026-07-06')[0] == 'work'
        assert definition_of_working_day('2026-07-06')[0] == 'work'


class TestStaleDailyRateGone:
    def test_load_employees_does_not_read_rates(self, monkeypatch, tmp_path):
        from core import config
        monkeypatch.chdir(tmp_path)
        # _load_employees больше не должен дергать load_wage_rates:
        # подмена на взрыв — загрузка обязана пройти.
        def _boom():
            raise AssertionError('load_wage_rates не должен вызываться в _load_employees')
        monkeypatch.setattr(config, 'load_wage_rates', _boom)
        import tempfile, os
        var = tmp_path / 'data' / 'variable_data_for_app'
        var.mkdir(parents=True)
        (var / 'roles_employee.dat').write_text('[1] Работник\n', encoding='utf-8')
        (var / 'id_employee.dat').write_text('101 [1] Петров Иван\n', encoding='utf-8')
        monkeypatch.setattr(config, 'ROLES_FILE', str(var / 'roles_employee.dat'))
        monkeypatch.setattr(config, 'ID_EMPLOYEE_FILE', str(var / 'id_employee.dat'))
        # ROLES нужен для резолва имен
        config.ROLES.clear()
        config.ROLES.update(config._load_roles())
        emps = config._load_employees()
        assert emps[101].daily_rate == Decimal('0.00')
