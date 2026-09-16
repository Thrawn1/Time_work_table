"""Регрессия Этапа 3 (F01/F02/F05): режим, salary_mode, состав."""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import EmployeeData

YEAR, MONTH = 2026, 10


def _dt(day_key, hm):
    return datetime.strptime(f'{day_key} {hm}', '%Y-%m-%d %H:%M')


def _make_db(tmp_path, with_settings=True):
    from core.pay_store import init_db, seed_defaults, upsert_employee, assign_role
    db = str(tmp_path / 'pay3.db')
    con = init_db(db)
    if with_settings:
        seed_defaults(con)
    # сотрудник 1 — роль 1, сотрудник 7 — роль 0 (не участвует)
    con.execute("INSERT OR IGNORE INTO roles(id, name) VALUES(0,'Руководитель')")
    upsert_employee(con, 1, 'А', 'Цеховик', '2020-01-01')
    upsert_employee(con, 7, 'Р', 'Руководитель', '2020-01-01')
    try:
        assign_role(con, 1, 1, '2026-01-01')
    except ValueError:
        pass
    try:
        assign_role(con, 7, 0, '2026-01-01')
    except ValueError:
        pass
    con.close()
    return db


def _make_tables(emps=(1,)):
    from core.pay_calendar import workday_keys_in_month
    data_array, work_time = {}, {}
    for key in workday_keys_in_month(YEAR, MONTH):
        out, inn = _dt(key, '16:00'), _dt(key, '08:00')
        for emp in emps:
            data_array.setdefault(key, {})[emp] = [out, inn, 'work']
            work_time.setdefault(key, {})[emp] = (
                timedelta(0), timedelta(hours=8), 'недоработка', 'work')
    from core.calculations import calculate_hours_per_month
    summary, _ = calculate_hours_per_month(work_time)
    return data_array, work_time, {e: summary[e] for e in emps if e in summary}


def _patch_emp(monkeypatch):
    from core import analysis, data_array
    emps = {
        1: EmployeeData(id=1, first_name='А', last_name='Цеховик',
                        role_id=1, role_name='Работник цеха'),
        7: EmployeeData(id=7, first_name='Р', last_name='Руководитель',
                        role_id=0, role_name='Руководитель'),
    }
    monkeypatch.setattr(data_array, 'EMPLOYEES', emps)
    monkeypatch.setattr(analysis, 'EMPLOYEES', emps)
    return emps


class TestF01SalaryMode:
    def test_no_salary_zeroes_new_model_keeps_milk(self, tmp_path, monkeypatch):
        from core.payroll import build_bundle, bundle_to_wages, pay_header_text
        _patch_emp(monkeypatch)
        db = _make_db(tmp_path)
        da, wt, summary = _make_tables(emps=(1,))
        full = build_bundle(da, wt, summary, YEAR, MONTH, db, salary_mode=True)
        assert full.results[1].result.total > Decimal('0')
        zero = build_bundle(da, wt, summary, YEAR, MONTH, db, salary_mode=False)
        res = zero.results[1].result
        assert res.total == Decimal('0.00')
        assert res.ordinary_pay == Decimal('0.00')
        assert res.milk_amount > Decimal('0')  # молоко сохранено
        assert res.total_with_milk == res.milk_amount
        wages = bundle_to_wages(zero)
        assert wages[1].salary == Decimal('0.00')
        assert wages[1].total_with_milk == wages[1].milk
        assert 'без зарплаты' in pay_header_text(zero)

    def test_manual_bundle_without_salary_zeroes_wages(self):
        from core.payroll import PayrollBundle, PayEmployeeResult, bundle_to_wages
        from core.pay_calc import PayInputs, calculate_pay
        from core.roles import get_default_rule
        inputs = PayInputs(
            monthly_base=Decimal('60000'), base_day_hours=8,
            full_month_bonus=Decimal('5000'), workdays=20,
            shift_norm_hours=Decimal('8'), fact_hours=Decimal('160'),
            workdays_present=20, overtime_eligible=True,
            full_month_eligible=True, seniority_eligible=False,
            milk_amount=Decimal('800'),
        )
        result = calculate_pay(inputs)
        bundle = PayrollBundle(
            year=2026, month=10, workdays=20, settings_eff='2026-01-01',
            monthly_base=Decimal('60000'), base_day_hours=8,
            full_month_bonus=Decimal('5000'), seniority_scale=[],
            rule_versions={}, results={1: PayEmployeeResult(
                emp_id=1, name='N', rule=get_default_rule(1),
                inputs=inputs, result=result)},
            salary_mode=False,
        )
        wages = bundle_to_wages(bundle)
        assert wages[1].salary == Decimal('0.00')
        assert wages[1].milk == Decimal('800.00')


class TestF05ModeBoundary:
    def test_pre_transition_always_legacy(self, tmp_path):
        from core.pay_store import init_db, set_pay_settings
        from core.payroll import new_regime_available, resolve_pay_mode
        db = str(tmp_path / 'early.db')
        init_db(db).close()
        from core.pay_store import connect
        con = connect(db)
        set_pay_settings(con, '2025-01-01')
        con.close()
        assert new_regime_available(db, 2025, 12) is None
        assert resolve_pay_mode(db, 2025, 12) == 'legacy'

    def test_missing_file_is_legacy(self, tmp_path):
        from core.payroll import new_regime_available, resolve_pay_mode
        missing = str(tmp_path / 'nope.db')
        assert new_regime_available(missing, YEAR, MONTH) is None
        assert resolve_pay_mode(missing, YEAR, MONTH) == 'legacy'

    def test_corrupt_db_raises_payroll_error(self, tmp_path):
        import pytest
        from core.payroll import PayrollError, new_regime_available
        bad = str(tmp_path / 'bad.db')
        with open(bad, 'w', encoding='utf-8') as f:
            f.write('not a sqlite file')
        with pytest.raises(PayrollError, match='справочник'):
            new_regime_available(bad, YEAR, MONTH)

    def test_missing_assignment_raises_no_fallback(self, tmp_path, monkeypatch):
        import pytest
        from core.payroll import PayrollError, build_bundle
        _patch_emp(monkeypatch)
        db = _make_db(tmp_path)
        # emp 99 есть в DAT-списке, но назначения SQLite нет
        emps = {99: EmployeeData(id=99, first_name='X', last_name='Y',
                                 role_id=1, role_name='Работник')}
        from core import analysis, data_array
        monkeypatch.setattr(data_array, 'EMPLOYEES', emps)
        monkeypatch.setattr(analysis, 'EMPLOYEES', emps)
        da, wt, summary = _make_tables(emps=(1,))
        # подменим summary на 99 с минимальными данными
        summary = {99: ((1, timedelta(0), timedelta(0)),
                        (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        da = {'2026-10-06': {99: [_dt('2026-10-06', '16:00'),
                                  _dt('2026-10-06', '08:00'), 'work']}}
        wt = {'2026-10-06': {99: (timedelta(0), timedelta(hours=8),
                                   'недоработка', 'work')}}
        with pytest.raises(PayrollError, match='назначения'):
            build_bundle(da, wt, summary, YEAR, MONTH, db)


class TestF02Participants:
    def test_non_participating_rule_excluded(self, tmp_path, monkeypatch):
        from core.payroll import build_bundle
        _patch_emp(monkeypatch)
        db = _make_db(tmp_path)
        da, wt, summary = _make_tables(emps=(1, 7))
        # summary для 7 вручную (роль 0)
        summary[7] = ((1, timedelta(0), timedelta(0)),
                      (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)
        da.setdefault('2026-10-06', {})[7] = [_dt('2026-10-06', '16:00'),
                                              _dt('2026-10-06', '08:00'), 'work']
        wt.setdefault('2026-10-06', {})[7] = (timedelta(0), timedelta(hours=8),
                                              'недоработка', 'work')
        bundle = build_bundle(da, wt, summary, YEAR, MONTH, db)
        assert 1 in bundle.results
        assert 7 not in bundle.results

    def test_preview_and_excel_skip_non_bundle(self, setup_employees):
        from datetime import timedelta as _td
        from core.payroll import PayrollBundle, PayEmployeeResult
        from core.pay_calc import PayInputs, calculate_pay
        from core.roles import get_default_rule
        from core.ui import build_preview_rows
        summary = {
            101: ((1, _td(0), _td(0)), (0, _td(0), _td(0), _td(0)), 0, 0),
            102: ((1, _td(0), _td(0)), (0, _td(0), _td(0), _td(0)), 0, 0),
        }
        from core.day_models import WageResult
        wages = {101: WageResult(Decimal('100'), Decimal('40'), Decimal('140')),
                 102: WageResult(Decimal('0'), Decimal('0'), Decimal('0'))}
        inputs = PayInputs(monthly_base=Decimal('60000'), base_day_hours=8,
                           full_month_bonus=Decimal('5000'), workdays=20,
                           shift_norm_hours=Decimal('8'), fact_hours=Decimal('8'),
                           workdays_present=1, milk_amount=Decimal('40'))
        bundle = PayrollBundle(year=2026, month=10, workdays=20,
                               settings_eff='2026-01-01',
                               monthly_base=Decimal('60000'), base_day_hours=8,
                               full_month_bonus=Decimal('5000'), seniority_scale=[],
                               rule_versions={},
                               results={101: PayEmployeeResult(
                                   emp_id=101, name='П', rule=get_default_rule(1),
                                   inputs=inputs, result=calculate_pay(inputs))})
        rows_all = build_preview_rows(summary, wages, employees=setup_employees)
        rows_new = build_preview_rows(summary, wages, employees=setup_employees,
                                      bundle=bundle)
        assert {r['emp_id'] for r in rows_all} >= {101}
        assert {r['emp_id'] for r in rows_new} == {101}

    def test_dashboard_extra_excluded(self, setup_employees):
        from core.ui import build_dashboard_rows
        tt = {'2026-07-06': {101: [datetime(2026, 7, 6, 16), datetime(2026, 7, 6, 8), 'work']}}
        rows = build_dashboard_rows(tt, [101], 2026, 7, employees=setup_employees,
                                    extra_excluded={101: 'роль не участвует'})
        assert rows[0]['excluded'] is True
        assert 'не участвует' in rows[0]['reason']
