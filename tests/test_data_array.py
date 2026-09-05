from datetime import datetime
from core.data_array import (
    build_data_array,
    _parse_line,
    get_employee_work_dates,
    get_all_employees_in_data,
    get_name_employee,
    is_settlement_allowed,
)


def make_line(emp_id, date_str, time_str):
    """Create a raw attlog line."""
    return f'        {emp_id}\t{date_str} {time_str}\t1\t255\t1\t0'


class TestParseLine:
    def test_valid_line(self):
        result = _parse_line(make_line(5, '2026-07-01', '06:46:01'))
        assert result is not None
        emp_id, dt = result
        assert emp_id == 5
        assert dt == datetime(2026, 7, 1, 6, 46, 1)

    def test_invalid_line(self):
        assert _parse_line('not a data line') is None

    def test_empty_line(self):
        assert _parse_line('') is None

    def test_extra_text_ignored(self):
        result = _parse_line(make_line(5, '2026-07-01', '08:00:00') + ' extra stuff')
        assert result is not None
        assert result[0] == 5


class TestBuildDataArray:
    def test_single_mark(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Single mark creates a day entry with same come/go."""
        lines = [make_line(101, '2026-07-06', '08:00:00')]
        result = build_data_array(lines)
        assert '2026-07-06' in result
        marks = result['2026-07-06'][101]
        assert marks[0] == marks[1]  # same dt for single mark
        assert marks[2] == 'work'

    def test_two_marks_expands_window(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Two marks: earliest and latest are stored."""
        lines = [
            make_line(101, '2026-07-06', '08:00:00'),
            make_line(101, '2026-07-06', '16:00:00'),
        ]
        result = build_data_array(lines)
        marks = result['2026-07-06'][101]
        assert marks[0] == datetime(2026, 7, 6, 16, 0, 0)  # latest
        assert marks[1] == datetime(2026, 7, 6, 8, 0, 0)   # earliest

    def test_multiple_marks_window(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Three marks: window is min/max of all."""
        lines = [
            make_line(101, '2026-07-06', '07:00:00'),
            make_line(101, '2026-07-06', '12:00:00'),
            make_line(101, '2026-07-06', '18:00:00'),
        ]
        result = build_data_array(lines)
        marks = result['2026-07-06'][101]
        assert marks[0] == datetime(2026, 7, 6, 18, 0, 0)
        assert marks[1] == datetime(2026, 7, 6, 7, 0, 0)

    def test_two_employees(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Two employees on same day."""
        lines = [
            make_line(101, '2026-07-06', '08:00:00'),
            make_line(102, '2026-07-06', '09:00:00'),
        ]
        result = build_data_array(lines)
        assert 101 in result['2026-07-06']
        assert 102 in result['2026-07-06']

    def test_different_dates(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Marks on different days create separate entries."""
        lines = [
            make_line(101, '2026-07-06', '08:00:00'),
            make_line(101, '2026-07-07', '08:00:00'),
        ]
        result = build_data_array(lines)
        assert '2026-07-06' in result
        assert '2026-07-07' in result

    def test_unknown_employee_skipped(self, monkeypatch, mock_holidays_jan2026, mock_postponed_empty):
        """Unknown employee ID is skipped with warning."""
        from core import config
        monkeypatch.setattr(config, 'EMPLOYEES', {
            101: config.EmployeeData(101, 'И', 'П', 1, 'Р', 800),
        })
        lines = [make_line(999, '2026-07-06', '08:00:00')]
        result = build_data_array(lines)
        assert '2026-07-06' not in result or 999 not in result.get('2026-07-06', {})

    def test_empty_list(self, setup_employees):
        """Empty input returns empty dict."""
        result = build_data_array([])
        assert result == {}

    def test_invalid_lines_skipped(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Invalid lines are silently skipped."""
        lines = ['bad line', '', 'also bad']
        result = build_data_array(lines)
        assert result == {}

    def test_holiday_tag_preserved(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """P1 #1: Holiday tag is set correctly on the day entry."""
        lines = [make_line(101, '2026-01-01', '08:00:00')]
        result = build_data_array(lines)
        marks = result['2026-01-01'][101]
        assert marks[2] == 'holiday'

    def test_weekend_tag_preserved(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        """Weekend tag is set correctly."""
        lines = [make_line(101, '2026-07-04', '08:00:00')]  # Saturday
        result = build_data_array(lines)
        marks = result['2026-07-04'][101]
        assert marks[2] == 'weekend'


class TestGetEmployeeWorkDates:
    def test_returns_dates(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        lines = [
            make_line(101, '2026-07-07', '08:00:00'),
            make_line(101, '2026-07-06', '08:00:00'),
        ]
        tt = build_data_array(lines)
        dates = get_employee_work_dates(tt, 101)
        assert '2026-07-06' in dates
        assert '2026-07-07' in dates
        assert len(dates) == 2

    def test_other_employee_not_included(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        lines = [
            make_line(101, '2026-07-06', '08:00:00'),
            make_line(102, '2026-07-07', '08:00:00'),
        ]
        tt = build_data_array(lines)
        dates = get_employee_work_dates(tt, 101)
        assert '2026-07-07' not in dates


class TestGetAllEmployeesInData:
    def test_returns_unique_ids(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        lines = [
            make_line(101, '2026-07-06', '08:00:00'),
            make_line(101, '2026-07-07', '08:00:00'),
            make_line(102, '2026-07-06', '08:00:00'),
        ]
        tt = build_data_array(lines)
        ids = get_all_employees_in_data(tt)
        assert ids == [101, 102]


class TestGetNameEmployee:
    def test_known_employee(self, setup_employees):
        name = get_name_employee(101)
        assert name == 'Петров Иван'

    def test_unknown_employee(self, setup_employees):
        name = get_name_employee(999)
        assert name == ''


class TestIsSettlementAllowed:
    def test_allowed(self, setup_employees):
        assert is_settlement_allowed(101) is True

    def test_exception(self, setup_employees, monkeypatch):
        from core import data_array
        monkeypatch.setattr(data_array, 'SETTLEMENT_EXCEPTIONS', [101])
        assert is_settlement_allowed(101) is False
