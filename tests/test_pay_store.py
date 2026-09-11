"""Тесты SQLite-хранилища справочников (план roles_rates, шаг 1, §7)."""

from decimal import Decimal

import pytest

from core import pay_store
from core.pay_store import (
    add_exception, assign_role, connect, get_assignment, get_pay_settings,
    get_role_rule, get_seniority_scale, init_db, is_excluded, list_exceptions,
    migrate_from_dat, remove_exception, role_rule_history, seed_defaults,
    set_pay_settings, set_role_rule, set_seniority_scale, upsert_employee,
    upsert_role,
)
from core.roles import DEFAULT_RULES, RoleRule


@pytest.fixture
def db():
    con = init_db(':memory:')
    yield con
    con.close()


def test_init_idempotent_and_version():
    con = init_db(':memory:')
    init_db(':memory:')  # повторный вызов файловой схемы — здесь smoke
    row = con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    assert row['value'] == '1'
    con.close()


def test_settings_effective_dating(db):
    assert get_pay_settings(db, '2026-09-01') is None
    set_pay_settings(db, '2026-09-01')
    set_pay_settings(db, '2027-01-01', monthly_base=Decimal('70000.00'))
    s = get_pay_settings(db, '2026-12-15')
    assert s.monthly_base == Decimal('60000.00')
    assert s.base_day_hours == 8
    assert s.full_month_bonus == Decimal('5000.00')
    s2 = get_pay_settings(db, '2027-01-01')
    assert s2.monthly_base == Decimal('70000.00')


def test_settings_money_exact_cents(db):
    set_pay_settings(db, '2026-09-01', monthly_base=Decimal('60000.00'))
    raw = db.execute('SELECT monthly_base_cents FROM pay_settings').fetchone()
    assert raw['monthly_base_cents'] == 6000000


def test_settings_validation(db):
    with pytest.raises(ValueError, match='ISO'):
        set_pay_settings(db, '09-2026')
    with pytest.raises(ValueError, match='base_day_hours'):
        set_pay_settings(db, '2026-09-01', base_day_hours=0)


def test_role_rule_versioning(db):
    upsert_role(db, 1, 'Работник цеха')
    rule = DEFAULT_RULES[1]
    set_role_rule(db, rule, '2026-09-01')
    other = RoleRule(role_id=1, role_name='Работник цеха', time_mode='actual',
                     shift_norm_hours=Decimal('12'), check_single_mark=True,
                     participates=True, overtime_eligible=False,
                     full_month_eligible=False, seniority_eligible=False)
    set_role_rule(db, other, '2027-01-01')
    assert get_role_rule(db, 1, '2026-10-01').shift_norm_hours == Decimal('8')
    assert get_role_rule(db, 1, '2027-02-01').shift_norm_hours == Decimal('12')
    assert len(role_rule_history(db, 1)) == 2
    assert get_role_rule(db, 2, '2026-10-01') is None


def test_role_rule_validation(db):
    upsert_role(db, 1, 'X')
    bad = RoleRule(role_id=1, role_name='X', time_mode='night', shift_norm_hours=Decimal('8'),
                   check_single_mark=True, participates=True)
    with pytest.raises(ValueError, match='time_mode'):
        set_role_rule(db, bad, '2026-09-01')
    with pytest.raises(ValueError, match='Сначала заведите|сначала заведите'):
        set_role_rule(db, DEFAULT_RULES[2], '2026-09-01')


def test_assignments_overlap_rejected(db):
    upsert_role(db, 1, 'A')
    upsert_role(db, 2, 'B')
    upsert_employee(db, 10, 'Иван', 'Петров')
    assign_role(db, 10, 1, '2026-01-01')
    with pytest.raises(ValueError, match='пересекающееся'):
        assign_role(db, 10, 2, '2026-06-01')  # открытый период уже занят
    assert get_assignment(db, 10, '2026-05-01') == (1, None)
    assert get_assignment(db, 10, '2025-01-01') is None


def test_closed_assignment_then_reassign(db):
    upsert_role(db, 1, 'A')
    upsert_role(db, 2, 'B')
    upsert_employee(db, 11, 'Петр', 'Иванов')
    db.execute("UPDATE assignments SET effective_to='2026-05-31'")
    assign_role(db, 11, 1, '2026-01-01', '2026-05-31')
    assign_role(db, 11, 2, '2026-06-01')
    assert get_assignment(db, 11, '2026-05-31') == (1, '2026-05-31')
    assert get_assignment(db, 11, '2026-06-01')[0] == 2


def test_seniority_scale(db):
    assert get_seniority_scale(db, '2026-09-01') == []
    set_seniority_scale(db, '2026-09-01', [(0, Decimal('0')), (5, Decimal('0.10'))])
    assert get_seniority_scale(db, '2027-01-01') == [(0, Decimal('0')), (5, Decimal('0.10'))]
    with pytest.raises(ValueError):
        set_seniority_scale(db, '2026-09-01', [(5, Decimal('0.10'))])  # дубликат версии
    with pytest.raises(ValueError, match='доля'):
        set_seniority_scale(db, '2028-01-01', [(0, Decimal('1.5'))])


def test_exceptions(db):
    add_exception(db, 7, 'подрядчик')
    assert is_excluded(db, 7) is True
    assert list_exceptions(db) == {7: 'подрядчик'}
    remove_exception(db, 7)
    assert is_excluded(db, 7) is False


def test_seed_defaults(db):
    seed_defaults(db)
    s = get_pay_settings(db, '2026-09-01')
    assert (s.monthly_base, s.base_day_hours, s.full_month_bonus) == (
        Decimal('60000.00'), 8, Decimal('5000.00'))
    for role_id in (0, 1, 2, 3, 4):
        assert get_role_rule(db, role_id, '2026-10-01') is not None
    assert get_role_rule(db, 0, '2026-10-01').participates is False
    assert get_seniority_scale(db, '2026-10-01') == [(0, Decimal('0')), (5, Decimal('0.10'))]


def test_migrate_from_dat_counts():
    con = init_db(':memory:')
    report = migrate_from_dat(con)
    assert report['roles'] == 4
    assert report['employees'] == 23
    assert report['exceptions'] == 3
    assert report['conflicts'] == []
    # Все сотрудники получили назначение с даты перехода, ID сохранены.
    assert get_assignment(con, 1, '2026-09-15') == (1, None)
    assert get_assignment(con, 7, '2026-09-15') == (0, None)
    assert is_excluded(con, 27) is True
    con.close()


def test_migrate_idempotent():
    con = init_db(':memory:')
    migrate_from_dat(con)
    report2 = migrate_from_dat(con)
    assert report2['roles'] == 0
    assert report2['employees'] == 0
    assert report2['exceptions'] == 0
    con.close()


def test_migrate_conflict_rolls_back():
    con = init_db(':memory:')
    upsert_role(con, 1, 'ДРУГОЕ НАЗВАНИЕ')
    with pytest.raises(ValueError, match='Конфликты переноса'):
        migrate_from_dat(con)
    # Откат: ни одного сотрудника не записано.
    assert con.execute('SELECT COUNT(*) c FROM employees').fetchone()['c'] == 0
    con.close()
