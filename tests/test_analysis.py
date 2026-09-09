from datetime import datetime
from unittest.mock import patch
from core.analysis import (
    search_missed_work_days,
    search_missed_marks,
    generation_of_lists_of_days,
    group_consecutive_days,
    format_range,
)


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestGenerationOfListsOfWorkDays:
    def test_july_2026(self, mock_holidays_jan2026, mock_postponed_empty):
        work, non_work = generation_of_lists_of_days(2026, 7)
        assert len(work) + len(non_work) == 31
        assert '2026-07-06' in work  # Monday
        assert '2026-07-04' in non_work  # Saturday

    def test_january_2026_holiday(self, mock_holidays_jan2026, mock_postponed_empty):
        work, non_work = generation_of_lists_of_days(2026, 1)
        assert '2026-01-01' in non_work  # holiday


class TestSearchMissedWorkDays:
    def test_employee_with_all_marks(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Employee has marks every workday -> no missed days."""
        tt = {
            '2026-07-06': {101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work']},
            '2026-07-07': {101: [make_dt('2026-07-07', '16:00:00'), make_dt('2026-07-07', '08:00:00'), 'work']},
        }
        result = search_missed_work_days(tt, 101, 2026, 7)
        # Should not include 07-06 and 07-07, but may include other workdays
        if result != 0:
            assert '2026-07-06' not in result
            assert '2026-07-07' not in result

    def test_employee_missing_some_days(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Employee is missing marks for some workdays."""
        tt = {
            '2026-07-06': {101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work']},
        }
        result = search_missed_work_days(tt, 101, 2026, 7)
        assert result != 0
        assert '2026-07-06' not in result
        assert '2026-07-07' in result

    def test_employee_no_marks_at_all(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """P1 #5 FIXED: Employee with zero marks returns all workdays as missed."""
        tt = {}
        result = search_missed_work_days(tt, 101, 2026, 7)
        # FIXED: returns all workdays, not 0
        assert result != 0
        assert '2026-07-06' in result

    def test_employee_in_other_month(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Employee only has marks in a different month - all July workdays are missed."""
        tt = {
            '2026-06-30': {101: [make_dt('2026-06-30', '16:00:00'), make_dt('2026-06-30', '08:00:00'), 'work']},
        }
        result = search_missed_work_days(tt, 101, 2026, 7)
        assert result != 0
        assert '2026-07-06' in result

    def test_unknown_employee(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Unknown employee returns 0."""
        tt = {}
        result = search_missed_work_days(tt, 999, 2026, 7)
        assert result == 0

    def test_no_missed_days(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """When all workdays have marks, returns 0."""
        work_days, _ = generation_of_lists_of_days(2026, 7)
        tt = {}
        for d in work_days:
            tt[d] = {101: [make_dt(d, '16:00:00'), make_dt(d, '08:00:00'), 'work']}
        result = search_missed_work_days(tt, 101, 2026, 7)
        assert result == 0


class TestSearchMissedMarks:
    def test_single_mark_detected(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Day with only one mark (same come=go) is detected."""
        dt = make_dt('2026-07-06', '08:00:00')
        tt = {
            '2026-07-06': {101: [dt, dt, 'work']},
        }
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result != 0
        assert len(result) == 1
        assert result[0][0] == '2026-07-06'

    def test_two_marks_not_flagged(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Day with two different marks is not flagged."""
        tt = {
            '2026-07-06': {101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work']},
        }
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result == 0

    def test_vacation_single_mark_not_flagged(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Single mark on vacation day is not flagged (vacation excluded from check)."""
        dt = make_dt('2026-07-06', '00:00:01')
        tt = {
            '2026-07-06': {101: [dt, dt, 'vacation']},
        }
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result == 0

    def test_no_marks_not_flagged(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Day with no marks at all is not flagged by missed_marks (handled by missed_work_days)."""
        tt = {}
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result == 0

    def test_multiple_single_mark_days(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Multiple days with single marks are all detected."""
        dt1 = make_dt('2026-07-06', '08:00:00')
        dt2 = make_dt('2026-07-07', '09:00:00')
        tt = {
            '2026-07-06': {101: [dt1, dt1, 'work']},
            '2026-07-07': {101: [dt2, dt2, 'work']},
        }
        result = search_missed_marks(tt, 101, 2026, 7)
        assert result != 0
        assert len(result) == 2


class TestGroupConsecutiveDays:
    def test_empty(self):
        assert group_consecutive_days([]) == []

    def test_single(self):
        assert group_consecutive_days(['2026-07-21']) == [['2026-07-21']]

    def test_consecutive(self):
        days = ['2026-07-21', '2026-07-22', '2026-07-23']
        assert group_consecutive_days(days) == [days]

    def test_weekend_gap_merges(self):
        """Пт и пн (разрыв 3 дня через выходные) — один диапазон."""
        days = ['2026-07-17', '2026-07-20']
        assert group_consecutive_days(days) == [days]

    def test_big_gap_splits(self):
        days = ['2026-07-06', '2026-07-07', '2026-07-20', '2026-07-21']
        assert group_consecutive_days(days) == [
            ['2026-07-06', '2026-07-07'], ['2026-07-20', '2026-07-21']]

    def test_unsorted_input(self):
        days = ['2026-07-22', '2026-07-21', '2026-07-23']
        assert group_consecutive_days(days) == [['2026-07-21', '2026-07-22', '2026-07-23']]

    def test_format_range(self):
        assert format_range(['2026-07-21']) == '21.07'
        assert format_range(['2026-07-21', '2026-07-22', '2026-07-23']) == '21.07–23.07 (3 раб. дн.)'


class TestBulkMissedEdit:
    def test_bulk_vacation(self, setup_employees):
        """Диапазон из 3 дней отмечается отпуском одним подтверждением."""
        from core import analysis
        analysis.clear_journal()
        missed = ['2026-07-21', '2026-07-22', '2026-07-23']
        tt: dict = {}
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, missed)):
            with patch('builtins.input', side_effect=['2', 'д']):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        for d in missed:
            assert tt[d][101][2] == 'vacation'
        entries = analysis.get_journal()
        assert len(entries) == 1
        assert 'x3' in entries[0]['action']
        analysis.clear_journal()

    def test_skip_all(self, setup_employees):
        """'a' пропускает все оставшиеся диапазоны без изменений."""
        from core import analysis
        analysis.clear_journal()
        missed = ['2026-07-06', '2026-07-21', '2026-07-22']
        tt: dict = {}
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, missed)):
            with patch('builtins.input', side_effect=['a']):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt == {}
        assert analysis.get_journal() == []
        analysis.clear_journal()

    def test_per_day_fallback(self, setup_employees):
        """'4': первый день — отпуск, второй — пропустить."""
        from core import analysis
        analysis.clear_journal()
        missed = ['2026-07-21', '2026-07-22']
        tt: dict = {}
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, missed)):
            with patch('builtins.input', side_effect=['4', '2', 'д', '0']):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt['2026-07-21'][101][2] == 'vacation'
        assert '2026-07-22' not in tt
        analysis.clear_journal()

    def test_bulk_work_same_time(self, setup_employees):
        """Диапазон заполняется рабочими днями с одним временем."""
        from core import analysis
        analysis.clear_journal()
        missed = ['2026-07-21', '2026-07-22']
        tt: dict = {}
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, missed)):
            with patch('builtins.input', side_effect=['1', '08 00 00', '17 00 00', 'д']):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        for d in missed:
            assert tt[d][101][1] == make_dt(d, '08:00:00')
            assert tt[d][101][0] == make_dt(d, '17:00:00')
        analysis.clear_journal()
