"""Тесты правил ролей и производственного календаря (план roles_rates, §7)."""

import calendar as _calendar
from decimal import Decimal

import pytest

from core import roles
from core.roles import (
    TIME_ACTUAL, TIME_FIXED_SHIFT, get_default_rule, known_default_role_ids,
    monthly_norm_hours,
)


def test_known_roles_present():
    assert known_default_role_ids() == [0, 1, 2, 3, 4]


def test_unknown_role_is_explicit_error():
    with pytest.raises(KeyError, match='Неизвестная роль 99'):
        get_default_rule(99)


def test_role_0_excluded_with_reason_in_dashboard():
    rule = get_default_rule(0)
    assert rule.participates is False
    assert rule.exclude_reason == 'руководство — не участвует'


def test_storekeeper_has_no_bonuses():
    rule = get_default_rule(2)
    assert rule.participates is True
    assert rule.overtime_eligible is False
    assert rule.full_month_eligible is False
    assert rule.seniority_eligible is False


def test_worker_has_all_bonuses():
    rule = get_default_rule(1)
    assert (rule.overtime_eligible, rule.full_month_eligible, rule.seniority_eligible) == (True, True, True)
    assert rule.time_mode == TIME_ACTUAL
    assert rule.overtime_coef == Decimal('1.5')


def test_fixed_shift_mode_does_not_change_tariff_base():
    # Норма роли 8 при фиксированной смене; H_base=8 живёт в общих условиях,
    # а не выводится из нормы смены.
    rule = get_default_rule(3)
    assert rule.time_mode == TIME_FIXED_SHIFT
    assert rule.shift_norm_hours == Decimal('8')


def test_monthly_norm_hours():
    assert monthly_norm_hours(get_default_rule(1), 20) == Decimal('160')
    assert monthly_norm_hours(get_default_rule(1), 0) == Decimal('0')


def test_no_hardcoded_accounting_outside_roles():
    # Учёт времени — только через time_mode из core.roles.
    # calculate_wages остаётся legacy-адаптером старого режима до шага 4.
    import pathlib
    calc_src = pathlib.Path('core/calculations.py').read_text(encoding='utf-8')
    hours_fn = calc_src.split('def calculate_hours_per_day')[1].split('def calculate_hours_per_month')[0]
    assert 'role_id in (1, 2, 4)' not in hours_fn
    assert 'role_id == 3' not in hours_fn
    assert 'get_default_rule' in hours_fn


def test_working_days_plain_month(monkeypatch):
    """Без праздников/переносов D = числу будней Пн–Пт."""
    from core import file_parser
    from core.pay_calendar import working_days_in_month
    monkeypatch.setattr(file_parser, 'load_holidays', lambda year: [])
    monkeypatch.setattr(file_parser, 'load_postponed_days', lambda year: [])
    year, month = 2026, 7
    n_days = _calendar.monthrange(year, month)[1]
    expected = sum(1 for d in range(1, n_days + 1)
                   if _calendar.weekday(year, month, d) < 5)
    assert working_days_in_month(year, month) == expected


def test_working_days_with_holiday_and_postpone(monkeypatch):
    from core import file_parser
    from core.pay_calendar import working_days_in_month
    # 2026-07-03 (пятница) — праздник, 2026-07-04 (суббота) — перенесённый рабочий.
    monkeypatch.setattr(file_parser, 'load_holidays', lambda year: ['2026-07-03'])
    monkeypatch.setattr(file_parser, 'load_postponed_days', lambda year: ['2026-07-04'])
    n_days = _calendar.monthrange(2026, 7)[1]
    plain_weekdays = sum(1 for d in range(1, n_days + 1)
                         if _calendar.weekday(2026, 7, d) < 5)
    assert plain_weekdays == 23  # опора примера: июль 2026 начинается со среды
    assert working_days_in_month(2026, 7) == plain_weekdays - 1 + 1
