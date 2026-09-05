import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from core.calculations import str_timedelta


def test_str_timedelta_zero():
    td = timedelta(0)
    assert str_timedelta(td) == '00:00:00'


def test_str_timedelta_hours():
    td = timedelta(hours=8)
    assert str_timedelta(td) == '08:00:00'


def test_str_timedelta_complex():
    td = timedelta(hours=10, minutes=30, seconds=15)
    assert str_timedelta(td) == '10:30:15'


def test_str_timedelta_large():
    td = timedelta(hours=100, minutes=5, seconds=59)
    assert str_timedelta(td) == '100:05:59'
