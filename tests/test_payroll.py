"""Тесты месячного пакета новой модели и переключения режимов (шаги 4–5, §7)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from core.config import EmployeeData
from core.money import timedelta_to_hours
from core.pay_calendar import workday_keys_in_month, working_days_in_month
from core.pay_store import connect, init_db, migrate_from_dat, seed_defaults
from core.payroll import (
    PayrollError, build_bundle, bundle_to_wages, new_regime_available,
)

YEAR, MONTH = 2026, 10


@pytest.fixture
def paydb(tmp_path):
    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    seed_defaults(con)
    migrate_from_dat(con)
    con.close()
    return db


@pytest.fixture
def emp_patch(monkeypatch):
    from core import analysis, data_array
    emps = {
        1: EmployeeData(id=1, first_name='А', last_name='Цеховик',
                        role_id=1, role_name='Работник цеха', daily_rate=Decimal('0.00')),
        2: EmployeeData(id=2, first_name='К', last_name='Кладовщик',
                        role_id=2, role_name='Кладовщик', daily_rate=Decimal('0.00')),
        7: EmployeeData(id=7, first_name='Р', last_name='Руководитель',
                        role_id=0, role_name='Руководитель', daily_rate=Decimal('0.00')),
    }
    monkeypatch.setattr(data_array, 'EMPLOYEES', emps)
    monkeypatch.setattr(analysis, 'EMPLOYEES', emps)
    return emps


def _dt(day_key: str, hm: str) -> datetime:
    return datetime.strptime(f'{day_key} {hm}', '%Y-%m-%d %H:%M')


def make_tables(extra_hours: dict[str, int] | None = None, emps=(1,)):
    """data_array + work_time: все рабочие дни по 8 ч + extra_hours в день."""
    extra_hours = extra_hours or {}
    data_array, work_time = {}, {}
    for key in workday_keys_in_month(YEAR, MONTH):
        hours = 8 + extra_hours.get(key, 0)
        out, inn = _dt(key, f'{8 + hours:02d}:00'), _dt(key, '08:00')
        for emp in emps:
            data_array.setdefault(key, {})[emp] = [out, inn, 'work']
            delta = abs(timedelta(hours=hours) - timedelta(hours=8))
            tag = 'переработка' if hours > 8 else 'недоработка'
            work_time.setdefault(key, {})[emp] = (delta, timedelta(hours=hours), tag, 'work')
    return data_array, work_time


def make_summary(work_time, emps=(1,)):
    from core.calculations import calculate_hours_per_month
    summary, _ = calculate_hours_per_month(work_time)
    return {e: summary[e] for e in emps if e in summary}


def test_new_regime_available(paydb, tmp_path):
    assert new_regime_available(paydb, YEAR, MONTH).monthly_base == Decimal('60000.00')
    assert new_regime_available(str(tmp_path / 'nope.db'), YEAR, MONTH) is None


def test_no_settings_raises(emp_patch):
    import tempfile, os
    fd, db = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db).close()
    with pytest.raises(PayrollError, match='общих условий'):
        build_bundle({}, {}, {1: ((1, timedelta(0), timedelta(0)),
                                  (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)},
                     YEAR, MONTH, db)


def test_worker_full_month(paydb, emp_patch):
    data_array, work_time = make_tables()
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    res = bundle.results[1].result
    assert bundle.workdays == working_days_in_month(YEAR, MONTH)
    assert res.ordinary_pay == Decimal('60000.00')
    assert res.full_month_ok is True
    assert res.full_month_bonus == Decimal('5000.00')
    assert res.seniority_bonus == Decimal('0.00')  # hire_date неизвестна
    assert res.total == Decimal('65000.00')
    assert res.milk_amount == Decimal('40.00') * bundle.workdays


def test_monthly_overtime_and_rates(paydb, emp_patch):
    keys = workday_keys_in_month(YEAR, MONTH)
    extra = {k: 2 for k in keys[:5]}  # +10 ч за месяц
    data_array, work_time = make_tables(extra)
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    res = bundle.results[1].result
    rate_hour = Decimal('60000') / (Decimal(bundle.workdays) * Decimal('8'))
    assert res.overtime_hours == Decimal('10')
    assert res.overtime_bonus == (rate_hour * Decimal('10') * Decimal('1.5')).quantize(
        Decimal('0.01'))
    assert res.ordinary_pay == Decimal('60000.00')  # cap нормой, двойной оплаты нет


def test_storekeeper_no_bonuses(paydb, emp_patch):
    keys = workday_keys_in_month(YEAR, MONTH)
    extra = {k: 2 for k in keys[:5]}
    data_array, work_time = make_tables(extra, emps=(2,))
    summary = make_summary(work_time, emps=(2,))
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    res = bundle.results[2].result
    assert res.ordinary_pay == Decimal('60000.00')
    assert res.overtime_bonus == Decimal('0.00')
    assert res.full_month_bonus == Decimal('0.00')
    assert res.total == Decimal('60000.00')


def test_excluded_role0_not_in_results(paydb, emp_patch):
    data_array, work_time = make_tables(emps=(1, 7))
    summary = make_summary(work_time, emps=(1, 7))
    summary[7] = ((1, timedelta(0), timedelta(0)),
                  (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    assert 7 not in bundle.results
    assert 1 in bundle.results


def test_seniority_from_hire_date(paydb, emp_patch):
    con = connect(paydb)
    con.execute("UPDATE employees SET hire_date='2015-01-01' WHERE id=1")
    con.commit()
    con.close()
    data_array, work_time = make_tables()
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    res = bundle.results[1].result
    # Стаж > 5 лет → 10% от полной базы 60000 + 0 + 5000.
    assert res.seniority_rate == Decimal('0.10')
    assert res.seniority_basis_exact == Decimal('65000.00')
    assert res.seniority_bonus == Decimal('6500.00')
    assert res.total == Decimal('71500.00')


def test_midmonth_assignment_warns(paydb, emp_patch):
    con = connect(paydb)
    con.execute("UPDATE assignments SET effective_to='2026-10-15'"
                " WHERE emp_id=1 AND effective_from='2026-09-01'")
    con.commit()
    con.execute("INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)"
                " VALUES(1, 2, '2026-10-16', NULL)")
    con.commit()
    con.close()
    data_array, work_time = make_tables()
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    assert any('внутри месяца' in w for w in bundle.warnings)
    assert bundle.results[1].rule.role_id == 1  # правило на 1-е число


def test_bundle_to_wages_and_snapshot(paydb, emp_patch, tmp_path):
    data_array, work_time = make_tables()
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    wages = bundle_to_wages(bundle)
    total, milk, with_milk = wages[1]
    assert (total, milk, with_milk) == (
        bundle.results[1].result.total,
        bundle.results[1].result.milk_amount,
        bundle.results[1].result.total_with_milk,
    )
    assert with_milk == total + milk  # строки отчётов сходятся с итогом
    path = bundle.save_versions(str(tmp_path / 'v.json'))
    import json
    snap = json.loads(open(path, encoding='utf-8').read())
    assert snap['workdays_D'] == bundle.workdays
    assert snap['pay_settings']['monthly_base'] == '60000.00'


def test_pay_details_console_is_cp1251_safe(paydb, emp_patch, capsys, monkeypatch):
    """Регрессия: ведомость не роняет Windows-консоль (cp1251)."""
    import core.ui as ui_mod
    from core.ui import print_pay_details
    monkeypatch.setattr(ui_mod, 'HAS_RICH', False)
    data_array, work_time = make_tables()
    summary = make_summary(work_time)
    bundle = build_bundle(data_array, work_time, summary, YEAR, MONTH, paydb)
    print_pay_details(bundle)
    out = capsys.readouterr().out
    out.encode('cp1251')  # UnicodeEncodeError при запрещённых символах
    assert 'Новая модель' in out


def test_zero_workdays_month_errors(paydb, emp_patch, monkeypatch):
    import core.payroll as payroll_mod
    monkeypatch.setattr(payroll_mod, 'working_days_in_month', lambda y, m: 0)
    with pytest.raises(PayrollError, match='D=0'):
        build_bundle({}, {}, {}, YEAR, MONTH, paydb)
