"""Регрессия Этапа 2 (F09–F11): DAT без потери строк, явный бэкап, валидация сессий."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestMinimalDatLines:
    def test_two_minimal_lines_with_trailing_newline(self, tmp_path, monkeypatch):
        """F11: две минимальные строки с \\n -> две отметки."""
        from core.file_parser import read_file_data_with_errors, parse_attlog_line
        monkeypatch.chdir(tmp_path)
        os.makedirs('data', exist_ok=True)
        with open('data/min.dat', 'w', encoding='utf-8', newline='\n') as f:
            f.write('101 2026-10-01 08:00:00\n')
            f.write('101 2026-10-01 16:00:00\n')
        rows, errors = read_file_data_with_errors('min.dat', 2026, 10)
        assert len(errors) == 0, errors
        assert len(rows) == 2
        # построение таблицы не должно терять строки
        assert parse_attlog_line(rows[0]) is not None
        assert parse_attlog_line(rows[1]) is not None

    def test_two_marks_form_8h_shift(self, setup_employees, mock_holidays_jan2026,
                                     mock_postponed_empty):
        """F11: две отметки -> одна восьмичасовая смена."""
        from datetime import timedelta
        from core.data_array import build_data_array
        from core.calculations import calculate_hours_per_day
        lines = ['101 2026-10-01 08:00:00', '101 2026-10-01 16:00:00']
        tt = build_data_array(lines)
        assert '2026-10-01' in tt and 101 in tt['2026-10-01']
        wt = calculate_hours_per_day(tt)
        _, worked, _, _ = wt['2026-10-01'][101]
        assert worked == timedelta(hours=8)

    def test_without_final_newline_same_result(self, tmp_path, monkeypatch):
        """F11: вариант без последнего перевода строки даёт тот же результат."""
        from core.file_parser import read_file_data_with_errors
        monkeypatch.chdir(tmp_path)
        os.makedirs('data', exist_ok=True)
        with open('data/a.dat', 'w', encoding='utf-8', newline='') as f:
            f.write('101 2026-10-01 08:00:00\n101 2026-10-01 16:00:00\n')
        with open('data/b.dat', 'w', encoding='utf-8', newline='') as f:
            f.write('101 2026-10-01 08:00:00\n101 2026-10-01 16:00:00')
        rows_a, _ = read_file_data_with_errors('a.dat', 2026, 10)
        rows_b, _ = read_file_data_with_errors('b.dat', 2026, 10)
        assert len(rows_a) == 2
        assert len(rows_b) == 2

    def test_format_error_in_diagnostics(self, tmp_path, monkeypatch):
        """F11: строка с ошибкой формата присутствует в диагностике."""
        from core.file_parser import read_file_data_with_errors
        monkeypatch.chdir(tmp_path)
        os.makedirs('data', exist_ok=True)
        with open('data/bad.dat', 'w', encoding='utf-8') as f:
            f.write('this is not a dat line\n')
            f.write('101 2026-10-01 08:00:00\n')
        rows, errors = read_file_data_with_errors('bad.dat', 2026, 10)
        assert len(rows) == 1
        assert len(errors) == 1
        assert 'строка 1' in errors[0]


class TestSessionBackup:
    def test_replace_failure_raises_and_preserves(self, tmp_path, monkeypatch):
        """F09: отказ os.replace -> исключение, исходная сессия побайтно сохранена."""
        from core.session import save_session, backup_existing_session, SessionBackupError, SESSION_FILE
        monkeypatch.chdir(tmp_path)
        data = {'2026-06-15': {101: [make_dt('2026-06-15', '16:00:00'),
                                     make_dt('2026-06-15', '08:00:00'), 'work']}}
        save_session(data)
        with open(SESSION_FILE, 'rb') as f:
            before = f.read()
        monkeypatch.setattr('core.session.os.replace',
                            lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
        try:
            backup_existing_session()
            assert False, 'ожидался SessionBackupError'
        except SessionBackupError:
            pass
        assert os.path.exists(SESSION_FILE)
        with open(SESSION_FILE, 'rb') as f:
            assert f.read() == before

    def test_main_aborts_on_backup_failure(self, setup_employees, tmp_path, monkeypatch, capsys):
        """F09: main не начинает новый расчёт при ошибке бэкапа."""
        import main as main_mod
        monkeypatch.chdir(tmp_path)
        from core.session import save_session
        save_session({'2026-06-15': {101: [make_dt('2026-06-15', '16:00:00'),
                                           make_dt('2026-06-15', '08:00:00'), 'work']}})
        monkeypatch.setattr(main_mod, 'load_config', lambda: None)
        monkeypatch.setattr(main_mod, 'set_secret_key', lambda k: None)
        import core.session as session_mod
        def _fail():
            raise session_mod.SessionBackupError('disk full')
        monkeypatch.setattr(main_mod, 'backup_existing_session', _fail)
        called = {}
        def _must_not_run(*a, **k):
            called['run'] = True
            return []
        monkeypatch.setattr(main_mod, 'read_file_data', _must_not_run)
        monkeypatch.setattr(sys, 'argv', ['main.py', '-y', '2026', '-m', '7', '-k', 't', '--no-edit'])
        try:
            main_mod.main()
            assert False, 'ожидался SystemExit'
        except SystemExit as e:
            assert e.code == 1
        assert 'run' not in called
        # Дефолтный --output-dir='result': сессия при старте перенесена туда (adopt_cwd_session).
        assert os.path.exists(os.path.join('result', 'temporary.json'))

    def test_repeated_backups_do_not_overwrite(self, tmp_path, monkeypatch):
        """F09: повторные бэкапы одного периода не перезаписывают друг друга."""
        from core.session import save_session, backup_existing_session
        monkeypatch.chdir(tmp_path)
        save_session({'2026-06-15': {101: [make_dt('2026-06-15', '16:00:00'),
                                           make_dt('2026-06-15', '08:00:00'), 'work']}})
        first = backup_existing_session()
        assert first is not None and os.path.exists(first)
        # вторая сессия того же периода
        save_session({'2026-06-20': {101: [make_dt('2026-06-20', '16:00:00'),
                                           make_dt('2026-06-20', '08:00:00'), 'work']}})
        second = backup_existing_session()
        assert second is not None and os.path.exists(second)
        assert first != second
        assert os.path.exists(first)


class TestSessionValidation:
    def test_empty_without_period_rejected(self, tmp_path, monkeypatch):
        """F10: пустая entries без period -> диагностируемый отказ, а не {}."""
        from core.session import load_session, validate_session_raw
        monkeypatch.chdir(tmp_path)
        with open('empty.json', 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'entries': {}}, f)
        assert load_session('empty.json') is None
        table, errors = validate_session_raw({'version': 1, 'entries': {}})
        assert table is None and errors

    def test_empty_with_period_accepted(self, tmp_path, monkeypatch):
        """F10: пустая таблица с периодом восстанавливается по метаданным."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('empty_period.json', 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'period': {'year': 2026, 'month': 10}, 'entries': {}}, f)
        assert load_session('empty_period.json') == {}

    def test_mixed_timezone_rejected_without_typeerror(self, tmp_path, monkeypatch, capsys):
        """F10: приход без TZ + уход с TZ -> отказ валидации, а не TypeError."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        data = {'version': 1, 'entries': {
            '2026-07-06': {'101': ['2026-07-06T08:00:00', '2026-07-06T16:00:00+03:00', 'work']}}}
        with open('tz.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
        assert load_session('tz.json') is None
        out = capsys.readouterr().out
        assert 'часов' in out.lower() or 'пояс' in out.lower() or 'валидации' in out.lower()
