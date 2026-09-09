import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import (
    MONTHS_NAME_TO_RUSSIAN, WEEKDAYS_NAME, MONTHS_NAME_GENITIVE,
)


def test_months_name_to_russian_keys():
    assert len(MONTHS_NAME_TO_RUSSIAN) == 12
    for i in range(1, 13):
        assert i in MONTHS_NAME_TO_RUSSIAN


def test_weekdays_name_keys():
    assert len(WEEKDAYS_NAME) == 7
    for i in range(7):
        assert i in WEEKDAYS_NAME


def test_months_name_genitive():
    assert MONTHS_NAME_GENITIVE[1] == 'Января'
    assert MONTHS_NAME_GENITIVE[12] == 'Декабря'
