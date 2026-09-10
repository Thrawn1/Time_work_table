import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime
from decimal import Decimal
from core.config import EmployeeData, Role


@pytest.fixture
def setup_employees(monkeypatch):
    """Set up synthetic employees for testing, patching all consumer modules."""
    from core import config
    from core import calculations
    from core import data_array
    from core import analysis
    from core import html_builder
    from core import excel_builder

    roles = {
        1: Role(id=1, name='Работник', work_shift=8, lost_tag_flag=1),
        3: Role(id=3, name='Окладник', work_shift=8, lost_tag_flag=1),
        4: Role(id=4, name='Работник4', work_shift=8, lost_tag_flag=1),
    }
    employees = {
        101: EmployeeData(id=101, first_name='Иван', last_name='Петров',
                          role_id=1, role_name='Работник', daily_rate=Decimal('800.00')),
        102: EmployeeData(id=102, first_name='Мария', last_name='Сидорова',
                          role_id=3, role_name='Окладник', daily_rate=Decimal('800.00')),
        103: EmployeeData(id=103, first_name='Алексей', last_name='Козлов',
                          role_id=4, role_name='Работник4', daily_rate=Decimal('800.00')),
    }
    exceptions = []

    # Patch config globals
    monkeypatch.setattr(config, 'ROLES', roles)
    monkeypatch.setattr(config, 'EMPLOYEES', employees)
    monkeypatch.setattr(config, 'SETTLEMENT_EXCEPTIONS', exceptions)

    # Patch imported names in all consumer modules
    monkeypatch.setattr(calculations, 'EMPLOYEES', employees)
    monkeypatch.setattr(calculations, 'load_wage_rates',
                        lambda: {101: Decimal('800.00'), 102: Decimal('800.00'), 103: Decimal('800.00')})
    monkeypatch.setattr(data_array, 'EMPLOYEES', employees)
    monkeypatch.setattr(data_array, 'SETTLEMENT_EXCEPTIONS', exceptions)
    monkeypatch.setattr(analysis, 'EMPLOYEES', employees)
    monkeypatch.setattr(html_builder, 'EMPLOYEES', employees)
    monkeypatch.setattr(excel_builder, 'EMPLOYEES', employees)

    return employees


@pytest.fixture
def mock_wage_rates(monkeypatch):
    """Mock wage rates to return fixed values (rate=800.00 руб/смена для всех)."""
    from decimal import Decimal
    from core import config
    monkeypatch.setattr(config, 'load_wage_rates',
                        lambda: {101: Decimal('800.00'), 102: Decimal('800.00'), 103: Decimal('800.00')})


@pytest.fixture
def mock_holidays_jan2026(monkeypatch):
    """Mock holiday loading for January 2026: only Jan 1 is a holiday."""
    from core import file_parser
    original_load_holidays = file_parser.load_holidays

    def fake_holidays(year):
        if year == 2026:
            return ['2026-01-01']
        return original_load_holidays(year)

    monkeypatch.setattr(file_parser, 'load_holidays', fake_holidays)


@pytest.fixture
def mock_postponed_empty(monkeypatch):
    """Mock postponed days to return empty list."""
    from core import file_parser
    monkeypatch.setattr(file_parser, 'load_postponed_days', lambda year: [])


def make_dt(date_str, time_str):
    """Helper: create datetime from date and time strings."""
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')
