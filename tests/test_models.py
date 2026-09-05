import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, time
from core.models import Mark, WorkDay


def test_mark_from_raw_line():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    assert mark.mark_date == date(2026, 7, 1)
    assert mark.mark_time == time(6, 46, 1)
    assert mark.flag == 0


def test_mark_day_property():
    line = '        5\t2026-07-15 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    assert mark.day == 15


def test_mark_set_flag():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    mark.set_flag(1)
    assert mark.flag == 1


def test_mark_str():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    s = str(mark)
    assert 'Приход' in s
    assert '06:46:01' in s


def test_workday_from_mark():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    wd = WorkDay.from_mark(mark)
    assert wd.year == 2026
    assert wd.month == 7
    assert wd.day == 1
    assert wd.day_of_week == 'Среда'
    assert wd.month_name == 'Июль'


def test_workday_has_lost_mark():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    wd = WorkDay.from_mark(mark)
    assert wd.has_lost_mark() is True


def test_workday_edit_mark():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    wd = WorkDay.from_mark(mark)
    wd.edit_mark(0, '08:00:00')
    assert wd.mark_come.mark_time == time(8, 0, 0)


def test_workday_str():
    line = '        5\t2026-07-01 06:46:01\t1\t255\t1\t0'
    mark = Mark.from_raw_line(line)
    wd = WorkDay.from_mark(mark)
    s = str(wd)
    assert '1' in s
    assert 'Июль' in s
    assert '2026' in s
    assert 'Среда' in s
