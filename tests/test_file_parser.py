import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.file_parser import parse_attlog_line, definition_of_working_day


def test_parse_attlog_line_valid():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    result = parse_attlog_line(line)
    assert result is not None
    emp_id, dt = result
    assert emp_id == 5
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 1
    assert dt.hour == 6
    assert dt.minute == 46
    assert dt.second == 1


def test_parse_attlog_line_invalid():
    result = parse_attlog_line('invalid line')
    assert result is None


def test_parse_attlog_line_empty():
    result = parse_attlog_line('')
    assert result is None


def test_definition_workday_monday():
    tag, weekday = definition_of_working_day('2026-07-06')
    assert tag == 'work'
    assert weekday == 'Понедельник'


def test_definition_weekend_saturday():
    tag, weekday = definition_of_working_day('2026-07-04')
    assert tag == 'weekend'
    assert weekday == 'Суббота'


def test_definition_weekend_sunday():
    tag, weekday = definition_of_working_day('2026-07-05')
    assert tag == 'weekend'
    assert weekday == 'Воскресенье'


def test_definition_holiday():
    tag, weekday = definition_of_working_day('2026-01-01')
    assert tag == 'holiday'
    assert weekday == 'Четверг'


def test_definition_postponed_workday():
    tag, weekday = definition_of_working_day('2026-11-01')
    assert tag == 'work'
    assert weekday == 'Воскресенье'
