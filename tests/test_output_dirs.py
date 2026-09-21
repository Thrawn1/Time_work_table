"""Каталоги данных/результатов: --data-dir/--output-dir.

Дефолты сохраняют прежнее поведение (cwd + 'data'), явные каталоги
уводят все артефакты из корня: Excel/HTML/версии/сессия/секрет.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


def make_tables():
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


@pytest.fixture
def session_guard():
    from core import session as s
    old = (s.SESSION_FILE, s.SESSION_FILE_LEGACY)
    yield s
    s.SESSION_FILE, s.SESSION_FILE_LEGACY = old


@pytest.fixture
def config_guard():
    from core import config as c
    keys = ('DATA_DIR', 'VARIABLE_DATA_DIR', 'ID_EMPLOYEE_FILE', 'ROLES_FILE',
            'WAGE_RATES_FILE', 'HOLIDAYS_FILE', 'POSTPONED_DAYS_FILE',
            'SETTLEMENT_EXCEPTIONS_FILE', 'SECRET_FILE')
    old = {k: getattr(c, k) for k in keys}
    yield c
    for k, v in old.items():
        setattr(c, k, v)


class TestBuildersOutputDir:
    def test_excel_goes_to_output_dir(self, setup_employees, tmp_path, monkeypatch):
        from core.excel_builder import build_excel
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = make_tables()
        f = build_excel(tt, wt, summary, wages, employees=setup_employees,
                        output_dir='out')
        assert f.startswith('out')
        assert (tmp_path / f).exists()
        # в корне tmp ничего не создано, кроме каталога результатов
        assert [p.name for p in tmp_path.iterdir()] == ['out']

    def test_html_goes_to_output_dir(self, setup_employees, tmp_path, monkeypatch):
        from core.html_builder import build_html
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = make_tables()
        f = build_html(101, tt, wt, summary, wages, employees=setup_employees,
                       output_dir='out')
        assert f.startswith('out')
        assert (tmp_path / f).exists()
        assert [p.name for p in tmp_path.iterdir()] == ['out']

    def test_builders_default_to_cwd(self, setup_employees, tmp_path, monkeypatch):
        """Без output_dir — прежнее поведение (файл в cwd)."""
        from core.excel_builder import build_excel
        from core.html_builder import build_html
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = make_tables()
        fx = build_excel(tt, wt, summary, wages, employees=setup_employees)
        fh = build_html(101, tt, wt, summary, wages, employees=setup_employees)
        assert '/' not in fx and '/' not in fh
        assert (tmp_path / fx).exists() and (tmp_path / fh).exists()

    def test_output_dir_created_if_missing(self, setup_employees, tmp_path, monkeypatch):
        from pathlib import Path
        from core.excel_builder import build_excel
        monkeypatch.chdir(tmp_path)
        tt, wt, summary, wages = make_tables()
        deep = tmp_path / 'a' / 'b'
        assert not deep.exists()
        f = build_excel(tt, wt, summary, wages, employees=setup_employees,
                        output_dir=str(deep))
        assert Path(f).exists()
        assert Path(f).parent == deep


class TestDataDir:
    def test_read_file_data_custom_dir(self, tmp_path):
        from core.file_parser import read_file_data
        d = tmp_path / 'mydata'
        d.mkdir()
        (d / '1_attlog.dat').write_text(
            '101 2026-07-06 08:00:00 1 255 1 0\n'
            '101 2026-08-06 08:00:00 1 255 1 0\n', encoding='utf-8')
        rows = read_file_data('1_attlog.dat', 2026, 7, str(d))
        assert len(rows) == 1 and '2026-07-06' in rows[0]

    def test_set_data_dir_repoints_references(self, tmp_path, config_guard):
        from core import config
        from core.file_parser import load_holidays
        d = tmp_path / 'alt'
        (d / 'variable_data_for_app').mkdir(parents=True)
        (d / 'variable_data_for_app' / 'holidays.dat').write_text('01.01\n', encoding='utf-8')
        config.set_data_dir(str(d))
        assert config.HOLIDAYS_FILE.startswith(str(d))
        assert config.WAGE_RATES_FILE.startswith(str(d))
        assert load_holidays(2026) == ('2026-01-01',)


class TestSessionDir:
    def _marks(self):
        return {'2026-07-06': {
            101: [make_dt('2026-07-06', '16:00:00'),
                  make_dt('2026-07-06', '08:00:00'), 'work']}},

    def test_round_trip_in_session_dir(self, tmp_path, monkeypatch, session_guard):
        from core import session as s
        monkeypatch.chdir(tmp_path)
        out = tmp_path / 'out'
        s.set_session_dir(str(out))
        assert s.SESSION_FILE.startswith(str(out))
        data, = self._marks()
        s.save_session(data)
        assert (out / 'temporary.json').exists()
        assert not (tmp_path / 'temporary.json').exists()
        loaded = s.load_session()
        assert loaded is not None and '2026-07-06' in loaded

    def test_backup_stays_in_session_dir(self, tmp_path, monkeypatch, session_guard):
        from core import session as s
        monkeypatch.chdir(tmp_path)
        out = tmp_path / 'out'
        s.set_session_dir(str(out))
        data, = self._marks()
        s.save_session(data, 2026, 7)
        backup = s.backup_existing_session()
        assert backup is not None and backup.startswith(str(out))
        import os
        assert os.path.exists(backup)
        assert not s.session_exists()  # исходный файл сессии съеден бэкапом

    def test_adopt_moves_cwd_session(self, tmp_path, monkeypatch, session_guard):
        import os
        from core import session as s
        monkeypatch.chdir(tmp_path)
        data, = self._marks()
        s.save_session(data)  # ещё в cwd
        assert (tmp_path / 'temporary.json').exists()
        out = tmp_path / 'out'
        s.set_session_dir(str(out))
        moved = s.adopt_cwd_session()
        assert moved is not None
        assert not (tmp_path / 'temporary.json').exists()
        assert os.path.exists(moved)
        assert s.load_session() is not None

    def test_adopt_noop_when_same_dir(self, tmp_path, monkeypatch, session_guard):
        from core import session as s
        monkeypatch.chdir(tmp_path)
        assert s.adopt_cwd_session() is None


class TestVersionsAndSecret:
    def test_save_versions_creates_parents(self, tmp_path):
        from core.payroll import PayrollBundle
        b = PayrollBundle(year=2026, month=7, workdays=20, settings_eff='2026-01-01',
                          monthly_base=Decimal('60000.00'), base_day_hours=8,
                          full_month_bonus=Decimal('5000.00'), seniority_scale=[],
                          rule_versions={})
        target = tmp_path / 'out' / 'nested' / 'payroll_versions_2026_07.json'
        assert not target.parent.exists()
        b.save_versions(str(target))
        assert target.exists()

    def test_secret_file_follows_setter(self, tmp_path, monkeypatch, config_guard):
        from core import config
        monkeypatch.chdir(tmp_path)
        out = tmp_path / 'out'
        out.mkdir()
        config.set_secret_file(str(out / '_secret_key.tmp'))
        config.set_secret_key('12345')
        assert (out / '_secret_key.tmp').exists()
        assert not (tmp_path / '_secret_key.tmp').exists()


class TestStartScreenDirs:
    def test_start_info_has_dirs(self):
        from core.ui import build_start_info
        info = build_start_info('f.dat', 2026, 7, 3, 2, 'fresh',
                                output_dir='out', data_dir='dd')
        assert info['output_dir'] == 'out' and info['data_dir'] == 'dd'

    def test_print_shows_dirs(self, capsys):
        from core.ui import build_start_info, print_start_screen
        print_start_screen(build_start_info('f.dat', 2026, 7, 3, 2, 'fresh',
                                            output_dir='out', data_dir='dd'))
        out = capsys.readouterr().out
        assert 'out' in out and 'dd' in out
