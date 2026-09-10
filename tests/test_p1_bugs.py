"""
Регрессионные тесты для P1-багов из project_review.md.

Каждый тест фиксирует ТЕКУЩЕЕ (сломанное) поведение через assert.
Когда баг будет исправлен, тест ДОЛЖЕН начать падать — это сигнал,
что поведение изменилось и тест нужно обновить под новое (правильное) поведение.

Правило: если тест PASS — баг НЕ исправлен. Если FAIL — баг исправлен.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


# =============================================================================
# P1 #1: Праздничные смены теряются в расчетах и детализации
# =============================================================================

class TestP1_1_HolidaysLostInCalculations:
    """Holiday shifts for roles 1 and 4 are lost in monthly aggregation."""

    def test_holiday_preserved_in_daily_calc(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Daily calc preserves holiday tag — this part works correctly."""
        from core.calculations import calculate_hours_per_day
        date_key = '2026-01-01'
        time_table = {
            date_key: {
                101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'holiday'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][101]
        assert worked == timedelta(hours=8)
        assert tag_day == 'holiday'

    def test_holiday_counted_in_monthly_aggregation(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: holiday tag is now recognized and counted as a holiday day."""
        from core.calculations import calculate_hours_per_month
        work_time = {
            '2026-01-01': {
                101: (timedelta(hours=2), timedelta(hours=10), 'переработка', 'holiday'),
            }
        }
        summary, restructured = calculate_hours_per_month(work_time)
        total_work, overtime_wd, undertime_wd = summary[101][0]
        total_holiday, overtime_we, undertime_we, total_worked_we = summary[101][1]
        # FIXED: holiday is counted in total_holiday, not in total_work
        assert total_work == 0
        assert total_holiday == 1
        assert overtime_we == timedelta(hours=2)
        assert total_worked_we == timedelta(hours=10)

    def test_holiday_gives_correct_wages(self, setup_employees, mock_wage_rates, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: holiday day is paid at 1.5x hourly fraction of daily rate."""
        from core.calculations import calculate_wages
        from decimal import Decimal
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),   # 0 work days
                (1, timedelta(0), timedelta(0), timedelta(hours=8)),  # 1 holiday, 8h worked
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        # FIXED: 1 holiday day, 8h worked = 1.5 * (800/8) * 8 = 1200
        assert total == Decimal('1200.00')
        assert milk == Decimal('40.00')

    def test_holiday_single_mark_not_suggested_for_edit(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: single holiday mark IS flagged by search_missed_marks."""
        from core.analysis import search_missed_marks
        dt = make_dt('2026-01-01', '08:00:00')
        tt = {'2026-01-01': {101: [dt, dt, 'holiday']}}
        result = search_missed_marks(tt, 101, 2026, 1)
        assert result != 0
        assert result[0][0] == '2026-01-01'

    def test_holiday_shows_times_in_html(self, setup_employees):
        """Регрессия: праздничная смена показывает время, а не 'holiday'."""
        from core.calculations import calculate_hours_per_day
        from core.html_builder import _build_daily_data, _gen_day_row
        date_key = '2026-01-01'
        tt = {date_key: {101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'holiday']}}
        wt = calculate_hours_per_day(tt)
        dd = _build_daily_data(101, tt, wt)
        assert len(dd) == 1
        html = ''.join(_gen_day_row(dd[0]))
        assert '08:00:00' in html
        assert '16:00:00' in html
        assert 'colspan' not in html

    def test_holiday_shows_times_in_excel(self, setup_employees):
        """Регрессия: праздничная смена заполняет ячейки времени в Excel."""
        from openpyxl import Workbook
        from core.calculations import calculate_hours_per_day
        from core.excel_builder import _write_data_rows
        date_key = '2026-01-01'
        tt = {date_key: {101: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'holiday']}}
        wt = calculate_hours_per_day(tt)
        wb = Workbook()
        ws = wb.active
        _write_data_rows(ws, tt, wt)
        assert ws.cell(column=3, row=2).value is not None
        assert ws.cell(column=4, row=2).value is not None


# =============================================================================
# P1 #2: Роль 3 теряет отпуск, прогул и категорию дня
# =============================================================================

class TestP1_2_Role3LosesStatus:
    """Role 3 (окладник) now preserves vacation/truancy status."""

    def test_role3_vacation_preserved(self, setup_employees):
        """FIXED: role 3 with 'vacation' tag returns 'vacation' and 0h."""
        from core.calculations import calculate_hours_per_day
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                102: [make_dt(date_key, '00:00:01'), make_dt(date_key, '00:00:01'), 'vacation'],
            }
        }
        result = calculate_hours_per_day(time_table)
        abs_delta, worked, tag_overtime, tag_day = result[date_key][102]
        # FIXED: vacation is preserved
        assert tag_day == 'vacation'
        assert worked == timedelta(0)

    def test_role3_truancy_preserved(self, setup_employees):
        """FIXED: role 3 with 'truancy' tag returns 'truancy' and 0h."""
        from core.calculations import calculate_hours_per_day
        date_key = '2026-07-06'
        time_table = {
            date_key: {
                102: [make_dt(date_key, '23:59:59'), make_dt(date_key, '23:59:59'), 'truancy'],
            }
        }
        result = calculate_hours_per_day(time_table)
        _, _, _, tag_day = result[date_key][102]
        # FIXED: truancy is preserved
        assert tag_day == 'truancy'

    def test_role3_vacation_counted_as_vacation_in_monthly(self, setup_employees):
        """FIXED: role 3 vacation day counted as vacation in monthly summary."""
        from core.calculations import calculate_hours_per_month
        work_time = {
            '2026-07-06': {
                102: (timedelta(0), timedelta(0), '', 'vacation'),
            }
        }
        summary, _ = calculate_hours_per_month(work_time)
        total_work, _, _ = summary[102][0]
        vacation = summary[102][2]
        # FIXED: vacation counted as vacation, not work
        assert total_work == 0
        assert vacation == 1

    def test_role3_truancy_counted_as_truancy_in_monthly(self, setup_employees):
        """FIXED: role 3 truancy day counted as truancy in monthly summary."""
        from core.calculations import calculate_hours_per_month
        work_time = {
            '2026-07-06': {
                102: (timedelta(0), timedelta(0), '', 'truancy'),
            }
        }
        summary, _ = calculate_hours_per_month(work_time)
        total_work, _, _ = summary[102][0]
        truancy = summary[102][3]
        # FIXED: truancy counted as truancy, not work
        assert total_work == 0
        assert truancy == 1

    def test_role3_vacation_not_paid_as_work(self, setup_employees, mock_wage_rates):
        """FIXED: role 3 vacation day is NOT paid (not in work+holiday count)."""
        from core.calculations import calculate_wages
        from decimal import Decimal
        summary = {
            102: (
                (0, timedelta(0), timedelta(0)),   # 0 work days — FIXED
                (0, timedelta(0)),
                0,  # vacation tracked separately
                0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[102]
        # FIXED: 0 work+holiday days = 0 salary
        assert total == Decimal('0.00')

    def test_role3_weekend_preserved(self, setup_employees):
        """Регрессия: роль 3 сохраняет 'weekend', а не подменяет на 'work'."""
        from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
        from decimal import Decimal
        date_key = '2026-07-04'
        tt = {date_key: {102: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'weekend']}}
        wt = calculate_hours_per_day(tt)
        assert wt[date_key][102][3] == 'weekend'
        assert wt[date_key][102][1] == timedelta(hours=8)
        summary, _ = calculate_hours_per_month(wt)
        assert summary[102][0][0] == 0  # не в буднях
        assert summary[102][1][0] == 1  # в выходных
        total, _, _ = calculate_wages(summary)[102]
        assert total == Decimal('800.00')

    def test_role3_holiday_preserved(self, setup_employees):
        """Регрессия: роль 3 сохраняет 'holiday', а не подменяет на 'work'."""
        from core.calculations import calculate_hours_per_day, calculate_hours_per_month
        date_key = '2026-01-01'
        tt = {date_key: {102: [make_dt(date_key, '16:00:00'), make_dt(date_key, '08:00:00'), 'holiday']}}
        wt = calculate_hours_per_day(tt)
        assert wt[date_key][102][3] == 'holiday'
        summary, _ = calculate_hours_per_month(wt)
        assert summary[102][0][0] == 0
        assert summary[102][1][0] == 1


# =============================================================================
# P1 #4: Неполный выходной и одиночная отметка оплачиваются как полная смена
# =============================================================================

class TestP1_4_IncompleteWeekendPaidAsFull:
    """Weekend shifts now pay based on actual worked hours."""

    def test_zero_hour_weekend_gives_zero_pay(self, setup_employees, mock_wage_rates):
        """FIXED: 0-hour weekend shift (single mark) pays 0."""
        from core.calculations import calculate_wages
        from decimal import Decimal
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), timedelta(0)),  # 1 day, 0 worked hours
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, milk, total_with_milk = result[101]
        # FIXED: 0 hours worked = 0 pay
        assert total == Decimal('0.00')
        assert milk == Decimal('40.00')  # milk is per day count, not per worked hours

    def test_two_hour_weekend_pays_proportionally(self, setup_employees, mock_wage_rates):
        """FIXED: 2-hour weekend shift pays proportional to hours."""
        from core.calculations import calculate_wages
        from decimal import Decimal
        expected = Decimal('300.00')  # 1.5 * (800/8) * 2
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), timedelta(hours=2)),  # 2h worked
                0, 0,
            )
        }
        result = calculate_wages(summary)
        total, _, _ = result[101]
        assert total == expected
        assert total < Decimal('1200.00')  # FIXED: less than full shift

    def test_single_mark_weekend_flagged_but_paid_correctly(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: single mark on weekend IS flagged, and pays based on actual hours."""
        from core.analysis import search_missed_marks
        from core.calculations import calculate_wages
        dt = make_dt('2026-07-04', '08:00:00')  # Saturday
        tt = {'2026-07-04': {101: [dt, dt, 'weekend']}}
        # search_missed_marks does detect it
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result != 0
        # FIXED: 0-hour shift pays 0
        from decimal import Decimal
        summary = {
            101: (
                (0, timedelta(0), timedelta(0)),
                (1, timedelta(0), timedelta(0), timedelta(0)),
                0, 0,
            )
        }
        wages = calculate_wages(summary)
        total, _, _ = wages[101]
        assert total == Decimal('0.00')

    def test_weekend_undertime_tracked(self, setup_employees):
        """FIXED: weekend undertime is now tracked separately."""
        from core.calculations import calculate_hours_per_month
        work_time = {
            '2026-07-04': {
                101: (timedelta(hours=2), timedelta(hours=2), 'недоработка', 'weekend'),
            }
        }
        summary, _ = calculate_hours_per_month(work_time)
        total_holiday, overtime_we, undertime_we, total_worked_we = summary[101][1]
        # FIXED: undertime is tracked, total_holiday = 1, total_worked = 2h
        assert total_holiday == 1
        assert undertime_we == timedelta(hours=2)
        assert total_worked_we == timedelta(hours=2)

    def test_single_mark_same_time_on_weekend(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: single mark creates a shift with 0 worked hours."""
        from core.data_array import build_data_array
        lines = [f'        101\t2026-07-04 08:00:00\t1\t255\t1\t0']
        result = build_data_array(lines)
        marks = result['2026-07-04'][101]
        # single mark: come == go, worked = 0
        assert marks[0] == marks[1]
        assert marks[2] == 'weekend'


# =============================================================================
# P1 #5: Сотрудник без отметок за весь месяц исчезает из обработки
# =============================================================================

class TestP1_5_EmployeeWithoutMarksDisappears:
    """Employee present in EMPLOYEES but with no marks is now included."""

    def test_employee_no_marks_search_returns_all_workdays(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: search_missed_work_days returns all workdays when no marks."""
        from core.analysis import search_missed_work_days
        tt = {}
        result = search_missed_work_days(tt, 101, 2026, 7)
        # FIXED: returns list of all workdays in July 2026
        assert result != 0
        assert len(result) > 0
        assert '2026-07-06' in result  # Monday

    def test_employee_no_marks_in_all_employees(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: get_all_employees_in_data returns ALL employees from handbook."""
        from core.data_array import get_all_employees_in_data
        tt = {}  # empty — no marks for anyone
        result = get_all_employees_in_data(tt)
        # FIXED: all handbook employees returned
        assert 101 in result
        assert 102 in result
        assert 103 in result

    def test_one_employee_present_others_still_included(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """FIXED: employees without marks are still in the result."""
        from core.data_array import get_all_employees_in_data
        tt = {
            '2026-07-06': {
                101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work'],
            }
        }
        result = get_all_employees_in_data(tt)
        # FIXED: all employees returned, not just those with marks
        assert 101 in result
        assert 102 in result
        assert 103 in result

    def test_employee_no_marks_search_missed_marks_returns_zero(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """search_missed_marks returns 0 for employee with no marks (no marks to check)."""
        from core.analysis import search_missed_marks
        tt = {}
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result == 0


# =============================================================================
# P1 #6: Сохраненная сессия подменяет параметры нового запуска
# =============================================================================

class TestP1_6_SessionReplacesParams:
    """Session now requires explicit --resume flag."""

    def test_ignored_session_preserved_and_new_calc_used(
        self, setup_employees, monkeypatch, tmp_path, capsys
    ):
        """Без --resume: июньская сессия бэкапится, расчёт идёт по июльскому файлу."""
        import main as main_mod
        import sys
        monkeypatch.chdir(tmp_path)

        june_data = {
            '2026-06-15': {
                101: [make_dt('2026-06-15', '16:00:00'), make_dt('2026-06-15', '08:00:00'), 'work'],
            }
        }
        from core.session import save_session, SESSION_FILE
        from core import session as session_mod
        save_session(june_data)
        assert tmp_path.joinpath(SESSION_FILE).exists()

        july_table = {
            '2026-07-06': {
                101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work'],
            }
        }
        calls = {'read_file': [], 'build_array': 0}

        def mock_read_file(file_name, year, month):
            calls['read_file'].append((file_name, year, month))
            return ['        101\t2026-07-06 08:00:00\t1\t255\t1\t0']

        def mock_build_array(lines):
            calls['build_array'] += 1
            return dict(july_table)

        monkeypatch.setattr(main_mod, 'read_file_data', mock_read_file)
        monkeypatch.setattr(main_mod, 'build_data_array', mock_build_array)
        monkeypatch.setattr(main_mod, 'load_config', lambda: None)
        monkeypatch.setattr(main_mod, 'set_secret_key', lambda k: None)
        monkeypatch.setattr(main_mod, 'analyze_for_print', lambda *a, **k: None)
        monkeypatch.setattr(main_mod, 'analyze_for_edit', lambda *a, **k: None)
        monkeypatch.setattr(main_mod, 'calculate_hours_per_day', lambda tt: {
            d: {e: (__import__('datetime').timedelta(0), __import__('datetime').timedelta(hours=8), 'недоработка', 'work')
                for e in emps} for d, emps in tt.items()})
        monkeypatch.setattr(main_mod, 'calculate_hours_per_month',
                            lambda wt: ({101: ((1, __import__('datetime').timedelta(0), __import__('datetime').timedelta(0)),
                                                (0, __import__('datetime').timedelta(0), __import__('datetime').timedelta(0), __import__('datetime').timedelta(0)), 0, 0)}, {}))
        monkeypatch.setattr(main_mod, 'calculate_wages', lambda s: {101: (800, 40, 840)})
        monkeypatch.setattr(main_mod, 'build_excel', lambda *a, **k: 'x.xlsx')
        monkeypatch.setattr(main_mod, 'build_html', lambda *a, **k: 'h.html')
        monkeypatch.setattr('core.config.load_wage_rates', lambda: {101: 800, 102: 800, 103: 800})
        monkeypatch.setattr('core.file_parser.load_holidays', lambda year: [])
        monkeypatch.setattr('core.file_parser.load_postponed_days', lambda year: [])

        monkeypatch.setattr(sys, 'argv', ['main.py', '-y', '2026', '-m', '7', '-k', 't', '--no-edit'])
        main_mod.main()

        # Новый расчёт использовал июльский файл, а не июньскую сессию
        assert calls['read_file'] and calls['read_file'][0][1:] == (2026, 7)
        assert calls['build_array'] == 1
        out = capsys.readouterr().out
        assert 'проигнорирован' in out or 'сохран' in out
        # Июньская сессия не потеряна: лежит в бэкапе
        backups = list(tmp_path.glob('temporary_*.json')) + list(tmp_path.glob('temporary_backup_*.json'))
        assert backups, 'бэкап игнорируемой сессии должен остаться'
        from core.session import load_session as _load
        restored = _load(str(backups[0]))
        assert restored is not None and '2026-06-15' in restored

    def test_resume_loads_session_without_reading_file(
        self, setup_employees, monkeypatch, tmp_path, capsys
    ):
        """С --resume: файл не читается, используется сессия, после успеха сессия удалена."""
        import main as main_mod
        import sys
        monkeypatch.chdir(tmp_path)

        june_data = {
            '2026-06-15': {
                101: [make_dt('2026-06-15', '16:00:00'), make_dt('2026-06-15', '08:00:00'), 'work'],
            }
        }
        from core.session import save_session, session_exists
        save_session(june_data)
        assert session_exists()

        def _fail_read(*a, **k):
            raise AssertionError('read_file_data не должен вызываться при --resume')

        monkeypatch.setattr(main_mod, 'read_file_data', _fail_read)
        monkeypatch.setattr(main_mod, 'load_config', lambda: None)
        monkeypatch.setattr(main_mod, 'set_secret_key', lambda k: None)
        monkeypatch.setattr(main_mod, 'analyze_for_print', lambda *a, **k: None)
        monkeypatch.setattr(main_mod, 'analyze_for_edit', lambda *a, **k: None)
        monkeypatch.setattr(main_mod, 'calculate_hours_per_day', lambda tt: {
            d: {e: (__import__('datetime').timedelta(0), __import__('datetime').timedelta(hours=8), 'недоработка', 'work')
                for e in emps} for d, emps in tt.items()})
        monkeypatch.setattr(main_mod, 'calculate_hours_per_month',
                            lambda wt: ({101: ((1, __import__('datetime').timedelta(0), __import__('datetime').timedelta(0)),
                                                (0, __import__('datetime').timedelta(0), __import__('datetime').timedelta(0), __import__('datetime').timedelta(0)), 0, 0)}, {}))
        monkeypatch.setattr(main_mod, 'calculate_wages', lambda s: {101: (800, 40, 840)})
        monkeypatch.setattr(main_mod, 'build_excel', lambda *a, **k: 'x.xlsx')
        monkeypatch.setattr(main_mod, 'build_html', lambda *a, **k: 'h.html')
        monkeypatch.setattr('core.config.load_wage_rates', lambda: {101: 800, 102: 800, 103: 800})
        monkeypatch.setattr('core.file_parser.load_holidays', lambda year: [])
        monkeypatch.setattr('core.file_parser.load_postponed_days', lambda year: [])

        monkeypatch.setattr(sys, 'argv', ['main.py', '--resume', '-k', 't', '--no-edit'])
        main_mod.main()

        # После успешного resumed-расчёта рабочая сессия удалена
        assert not session_exists()
