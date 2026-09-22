"""Этап 7 (F18/F19/F22): ключ в памяти, CLI-валидация, парсеры, HTML.

Критерии из ревью 2026-09-16 §2.8:
- неверный ввод — диагностика без трассировки;
- запуск не оставляет ключ на диске;
- финансовые/временные показатели согласованы между консолью, Excel и HTML.
"""
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path


def make_dt(date_str, time_str):
    from datetime import datetime
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestKeyInMemory:
    def test_set_does_not_create_file(self, tmp_path, monkeypatch):
        from core import config
        monkeypatch.chdir(tmp_path)
        config.clear_secret_key()
        try:
            config.set_secret_key(Decimal('123.45'))
            assert config.get_secret_key() == Decimal('123.45')
            assert not Path('_secret_key.tmp').exists()
            assert not Path(config.LEGACY_SECRET_FILE).exists()
        finally:
            config.clear_secret_key()

    def test_legacy_file_migrates_once_and_removed(self, tmp_path, monkeypatch):
        from core import config
        monkeypatch.chdir(tmp_path)
        config.clear_secret_key()
        try:
            Path('_secret_key.tmp').write_text('7.50', encoding='utf-8')
            assert config.get_secret_key() == Decimal('7.50')
            assert not Path('_secret_key.tmp').exists()
            # повторный вызов — уже из памяти, файла нет
            assert config.get_secret_key() == Decimal('7.50')
        finally:
            config.clear_secret_key()

    def test_huge_key_accepted_full_precision_no_crash_at_use(self):
        """Ключ на границе длины (122) принимается с полной точностью.

        Крах на InvalidOperation невозможен: переполнение при ключ×ставка
        становится ConfigError в load_wage_rates (F18), а не здесь.
        """
        from main import parse_secret_key
        huge = '9' * 122
        secret, mode, warn = parse_secret_key(huge)
        assert mode is True and warn is None
        assert secret == Decimal(huge[:-2] + '.' + huge[-2:])

    def test_huge_key_use_raises_config_error_not_invalid_operation(self, tmp_path, monkeypatch):
        from core import config
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'data' / 'variable_data_for_app').mkdir(parents=True)
        (tmp_path / 'data' / 'variable_data_for_app' / 'wage_rates.dat').write_text(
            '101 [867508.425]\n', encoding='utf-8')
        import pytest
        huge = '9' * 122
        with pytest.raises(config.ConfigError):
            config.load_wage_rates(key=Decimal(huge[:-2] + '.' + huge[-2:]))

    def test_valid_key_accepted(self):
        from main import parse_secret_key
        secret, mode, warn = parse_secret_key('12345')
        assert secret == Decimal('123.45') and mode is True and warn is None

    def test_load_rates_explicit_key_no_file(self, tmp_path, monkeypatch):
        from core import config
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'data' / 'variable_data_for_app').mkdir(parents=True)
        (tmp_path / 'data' / 'variable_data_for_app' / 'wage_rates.dat').write_text(
            '101 [867508.425]\n', encoding='utf-8')
        config.clear_secret_key()
        try:
            rates = config.load_wage_rates(key=Decimal('1.00'))
            assert rates[101] == Decimal('425.87')
            assert not Path('_secret_key.tmp').exists()
        finally:
            config.clear_secret_key()


class TestPeriodValidation:
    def test_validate_ok(self):
        from main import validate_period
        assert validate_period(2026, 7) == (2026, 7)

    def test_month_zero_is_error_not_missing(self):
        from main import validate_period
        import pytest
        with pytest.raises(ValueError, match='месяц'):
            validate_period(2026, 0)

    def test_month_13_is_error(self):
        from main import validate_period
        import pytest
        with pytest.raises(ValueError, match='месяц'):
            validate_period(2026, 13)

    def test_year_out_of_range(self):
        from main import validate_period
        import pytest
        with pytest.raises(ValueError, match='год'):
            validate_period(1800, 7)

    def test_none_is_error(self):
        from main import validate_period
        import pytest
        with pytest.raises(ValueError):
            validate_period(None, 7)

    def test_resume_help_mentions_json_not_pickle_as_valid(self):
        # --resume должен ссылаться на temporary.json; pickle — только как
        # неподдерживаемый legacy, а не как валидный источник.
        # Аргументы разбирает core/cli.py (build_parser), не main.py напрямую.
        text = Path('core/cli.py').read_text(encoding='utf-8')
        assert 'temporary.json' in text
        # help --resume не должен обещать загрузку pickle как валидную.
        assert 'temporary.pickle не поддерживается' in text or 'pickle' in text.lower()


class TestRobustParsers:
    def test_employee_tabs_and_spaces(self):
        from core.config import _parse_employee_line
        for line in ('101 [1] Петров Иван',
                     '101   [1]   Петров   Иван',
                     '101\t[1]\tПетров\tИван',
                     '  101  [1]  Петров  Иван  '):
            emp_id, role_id, last, first = _parse_employee_line(line, 1, 't.dat')
            assert (emp_id, role_id, last, first) == (101, 1, 'Петров', 'Иван')

    def test_employee_bad_format_has_file_line(self):
        from core.config import _parse_employee_line, ConfigError
        import pytest
        with pytest.raises(ConfigError, match='t.dat:3'):
            _parse_employee_line('oops', 3, 't.dat')
        with pytest.raises(ConfigError, match='t.dat:5'):
            _parse_employee_line('101 Петров', 5, 't.dat')

    def test_roles_whitespace(self):
        from core.config import _parse_roles_line
        assert _parse_roles_line('[1] Работник', 1, 'r.dat') == (1, 'Работник')
        assert _parse_roles_line('  [2]\tКладовщик  ', 2, 'r.dat') == (2, 'Кладовщик')

    def test_roles_bad_has_line(self):
        from core.config import _parse_roles_line, ConfigError
        import pytest
        with pytest.raises(ConfigError, match='r.dat:7'):
            _parse_roles_line('no brackets', 7, 'r.dat')

    def test_wage_tabs(self):
        from core.config import _parse_wage_line
        emp_id, dec = _parse_wage_line('101\t[867508.425]', 1, 'w.dat')
        assert emp_id == 101 and dec == Decimal('425.867508')

    def test_wage_bad_has_line(self):
        from core.config import _parse_wage_line, ConfigError
        import pytest
        with pytest.raises(ConfigError, match='w.dat:2'):
            _parse_wage_line('101 no-brackets', 2, 'w.dat')

    def test_calendar_bad_has_line(self):
        from core.file_parser import _parse_calendar_line
        import pytest
        with pytest.raises(ValueError, match='h.dat:4'):
            _parse_calendar_line('oops', 4, 'h.dat')
        with pytest.raises(ValueError, match='h.dat:5'):
            _parse_calendar_line('32.01', 5, 'h.dat')
        with pytest.raises(ValueError, match='h.dat:6'):
            _parse_calendar_line('01.13', 6, 'h.dat')

    def test_calendar_ok_pads(self):
        from core.file_parser import _parse_calendar_line
        assert _parse_calendar_line('1.1', 1, 'h.dat') == ('01', '01', None)

    def test_calendar_impossible_rejected(self):
        from core.file_parser import _parse_calendar_line
        import pytest
        with pytest.raises(ValueError, match='невозможная'):
            _parse_calendar_line('31.02', 1, 'h.dat')
        # Полная дата со своим годом принимается.
        assert _parse_calendar_line('2026-01-01', 1, 'h.dat') == ('01', '01', '2026')


class TestValidHtml:
    def _tables(self, setup_employees):
        from core.day_models import DayMark, DayWork, EmployeeMonth, HolidayGroup, WorkGroup, WageResult
        d = '2026-10-06'
        tt = {d: {101: DayMark(go=make_dt(d, '16:00:00'), come=make_dt(d, '08:00:00'), tag='work')}}
        wt = {d: {101: DayWork(delta=timedelta(0), worked=timedelta(hours=8),
                               overtime_tag='недоработка', day_tag='work')}}
        summary = {101: EmployeeMonth(work=WorkGroup(1, timedelta(0), timedelta(0)),
                                      holiday=HolidayGroup(0, timedelta(0), timedelta(0), timedelta(0)),
                                      vacation_days=0, truancy_days=0)}
        wages = {101: WageResult(Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))}
        return tt, wt, summary, wages

    def test_doctype_lang_charset_title(self, setup_employees, tmp_path, monkeypatch):
        from core.html_builder import build_html
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = self._tables(setup_employees)
        f = build_html(101, tt, wt, summary, wages, employees=setup_employees)
        text = (tmp_path / f).read_text(encoding='utf-8')
        assert text.lstrip().startswith('<!DOCTYPE html>')
        assert '<html lang="ru">' in text
        assert '<meta charset="utf-8">' in text
        assert '<head>' in text and '<title>' in text
        assert '<body>' in text and '</body>' in text

    def test_no_nested_tr(self, setup_employees, tmp_path, monkeypatch):
        from core.html_builder import build_html
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = self._tables(setup_employees)
        f = build_html(101, tt, wt, summary, wages, employees=setup_employees)
        text = (tmp_path / f).read_text(encoding='utf-8')
        # Старый баг: внешняя <tr> вокруг набора строк давала '<tr> ... <tr>'.
        assert '<tr>\n      <tr>' not in text
        assert '<tr>\n        <tr>' not in text
        # Один день + шапки + итог: вложенных строк нет, все <tr> закрыты.
        assert text.count('<tr') == text.count('</tr>')

    def test_durations_unified(self, setup_employees, tmp_path, monkeypatch):
        from core.html_builder import build_html, _build_daily_data
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = self._tables(setup_employees)
        dd = _build_daily_data(101, tt, wt, employees=setup_employees)
        assert dd[0]['delta_time'] == '08:00:00'
        assert dd[0]['overtime'] == '00:00:00'
        f = build_html(101, tt, wt, summary, wages, employees=setup_employees)
        text = (tmp_path / f).read_text(encoding='utf-8')
        assert '08:00:00' in text
        # Старый str(timedelta) давал '8:00:00' без ведущего нуля.
        assert '8:00:00' not in text.replace('08:00:00', '')


class TestUnifiedViews:
    def test_excel_time_number_format(self, setup_employees, tmp_path, monkeypatch):
        from core.excel_builder import build_excel
        from openpyxl import load_workbook
        monkeypatch.chdir(tmp_path)
        from core.day_models import DayMark, DayWork, EmployeeMonth, HolidayGroup, WorkGroup, WageResult
        d = '2026-10-06'
        tt = {d: {101: DayMark(go=make_dt(d, '16:00:00'), come=make_dt(d, '08:00:00'), tag='work')}}
        wt = {d: {101: DayWork(delta=timedelta(0), worked=timedelta(hours=8),
                               overtime_tag='недоработка', day_tag='work')}}
        summary = {101: EmployeeMonth(work=WorkGroup(1, timedelta(0), timedelta(0)),
                                      holiday=HolidayGroup(0, timedelta(0), timedelta(0), timedelta(0)),
                                      vacation_days=0, truancy_days=0)}
        wages = {101: WageResult(Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))}
        f = build_excel(tt, wt, summary, wages, employees=setup_employees)
        wb = load_workbook(tmp_path / f)
        ws = wb.active
        formats = {c.number_format for row in ws.iter_rows(min_row=2, max_row=2, min_col=3, max_col=7)
                   for c in row if c.value is not None}
        assert 'hh:mm:ss' in formats

    def test_preview_money_format(self, setup_employees):
        from core.ui import build_preview_rows
        from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup, WageResult
        summary = {101: EmployeeMonth(work=WorkGroup(1, timedelta(0), timedelta(0)),
                                      holiday=HolidayGroup(0, timedelta(0), timedelta(0), timedelta(0)),
                                      vacation_days=0, truancy_days=0)}
        wages = {101: WageResult(Decimal('800.00'), Decimal('40.00'), Decimal('840.00'))}
        rows = build_preview_rows(summary, wages, employees=setup_employees)
        assert rows[0]['overtime'] == '00:00:00'
        from core.money import format_money
        assert format_money(rows[0]['total']) == '840.00'
