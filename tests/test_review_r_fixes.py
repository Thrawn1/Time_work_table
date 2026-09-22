"""Регрессия ревью 2026-09-17 (R01–R22): поведение по spec_payroll.md v1.0."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from core.config import EmployeeData

YEAR, MONTH = 2026, 10


def _dt(key, hm):
    return datetime.strptime(f'{key} {hm}', '%Y-%m-%d %H:%M')


def _synth_db(tmp_path):
    from tests.synth_data import write_synth_dat_dir
    from core.pay_store import init_db, seed_defaults, migrate_from_dat

    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    seed_defaults(con)
    migrate_from_dat(con, write_synth_dat_dir(tmp_path / 'synth'))
    con.close()
    return db


def _full_month_tables(emp=1, hours=8):
    from core.pay_calendar import workday_keys_in_month

    da, wt = {}, {}
    for key in workday_keys_in_month(YEAR, MONTH):
        out, inn = _dt(key, f'{8 + hours:02d}:00') if hours != 8 else (_dt(key, '16:00'), _dt(key, '08:00')), _dt(key, '08:00')
        if hours == 8:
            out, inn = _dt(key, '16:00'), _dt(key, '08:00')
        else:
            out, inn = _dt(key, f'{8 + hours:02d}:00'), _dt(key, '08:00')
        da.setdefault(key, {})[emp] = [out, inn, 'work']
        delta = abs(timedelta(hours=hours) - timedelta(hours=8))
        tag = 'переработка' if hours > 8 else 'недоработка'
        wt.setdefault(key, {})[emp] = (delta, timedelta(hours=hours), tag, 'work')
    return da, wt


class TestR04Repairmen:
    def test_full_month_no_accrual(self, tmp_path):
        from core.pay_context import combined_staff_for_import, load_rules_map
        from core.calculations import calculate_hours_per_month
        from core.payroll import build_bundle

        db = _synth_db(tmp_path)
        from core.pay_store import connect
        con = connect(db)
        from core.pay_store import upsert_employee, assign_role
        upsert_employee(con, 4, 'Р', 'Ремонтник', '2020-01-01')
        try:
            assign_role(con, 4, 4, '2026-01-01')
        except ValueError:
            pass
        con.close()
        from core.config import EmployeeData as _ED
        dat = {4: _ED(id=4, first_name='Р', last_name='Ремонтник', role_id=4, role_name='Ремонтники')}
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        rules = load_rules_map(db, '2026-10-01', combined)
        assert rules[4].participates is False
        da, wt = _full_month_tables(emp=4)
        summary, _ = calculate_hours_per_month(wt)
        bundle = build_bundle(da, wt, {4: summary[4]}, YEAR, MONTH, db,
                              employees=combined, rules_by_role=rules)
        assert 4 not in bundle.results


class TestR05Weekends:
    def test_saturday_not_overtime(self, tmp_path):
        from core.calculations import calculate_hours_per_month
        from core.pay_context import combined_staff_for_import, load_rules_map
        from core.payroll import build_bundle

        db = _synth_db(tmp_path)
        from core.config import EmployeeData as _ED
        dat = {1: _ED(id=1, first_name='А', last_name='Цех', role_id=1, role_name='Р')}
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        rules = load_rules_map(db, '2026-10-01', combined)
        da, wt = _full_month_tables(emp=1)
        # Суббота 8 ч после полного буднего месяца.
        sat = '2026-10-03'
        da[sat] = {1: [_dt(sat, '16:00'), _dt(sat, '08:00'), 'weekend']}
        wt[sat] = {1: (timedelta(hours=8), timedelta(hours=8), 'переработка', 'weekend')}
        summary, _ = calculate_hours_per_month(wt)
        bundle = build_bundle(da, wt, {1: summary[1]}, YEAR, MONTH, db,
                              employees=combined, rules_by_role=rules)
        res = bundle.results[1].result
        assert res.overtime_hours == Decimal('0')
        assert res.overtime_bonus == Decimal('0.00')


class TestR06Boundaries:
    def test_midmonth_pay_settings_rejected(self, tmp_path):
        from core.pay_store import init_db, set_pay_settings

        con = init_db(str(tmp_path / 'p.db'))
        with pytest.raises(ValueError, match='1-го числа'):
            set_pay_settings(con, '2026-10-15')
        con.close()

    def test_midmonth_assignment_rejected(self, tmp_path):
        from core.pay_store import init_db, upsert_employee, upsert_role, assign_role

        con = init_db(str(tmp_path / 'p.db'))
        upsert_role(con, 1, 'A')
        upsert_employee(con, 1, 'И', 'П')
        with pytest.raises(ValueError, match='1-го числа'):
            assign_role(con, 1, 1, '2026-10-15')
        con.close()


class TestR14Types:
    def test_bool_and_list_ids_rejected(self, tmp_path):
        from core.pay_store import init_db
        from core.pay_toml import import_toml

        db = str(tmp_path / 'p.db')
        init_db(db)
        bad_roles = ('schema_version = 1\n[[roles]]\nid = true\nname = "X"\n')
        assert import_toml(db, bad_roles)['errors']
        bad_list = ('schema_version = 1\n[[roles]]\nid = 1\nname = "A"\n'
                    '[[employees]]\nid = 1\nfirst_name = "A"\nlast_name = "B"\n'
                    '[[assignments]]\nemp_id = [1]\nrole_id = 1\n'
                    'effective_from = "2026-01-01"\n')
        rep = import_toml(db, bad_list)
        assert rep['errors']
        # При ошибках запись не выполняется: ролей в БД нет.
        from core.pay_store import connect
        con = connect(db)
        try:
            assert con.execute('SELECT COUNT(*) c FROM roles').fetchone()['c'] == 0
        finally:
            con.close()

    def test_dust_money_rejected_in_dry_run(self, tmp_path):
        from core.pay_store import init_db
        from core.pay_toml import import_toml

        db = str(tmp_path / 'p.db')
        init_db(db)
        text = ('schema_version = 1\n[[pay_settings]]\neffective_from = "2026-01-01"\n'
                'monthly_base = "0.001"\nbase_day_hours = 8\nfull_month_bonus = "0.00"\n')
        rep = import_toml(db, text, dry_run=True)
        assert rep['errors']

    def test_infinite_coef_rejected(self, tmp_path):
        from core.pay_store import init_db, upsert_role
        from core.roles import RoleRule

        con = init_db(str(tmp_path / 'p.db'))
        upsert_role(con, 1, 'A')
        bad = RoleRule(role_id=1, role_name='A', time_mode='actual',
                       shift_norm_hours=Decimal('8'), check_single_mark=True,
                       participates=True, overtime_eligible=True,
                       full_month_eligible=True, seniority_eligible=True,
                       overtime_coef=Decimal('Infinity'))
        with pytest.raises(ValueError, match='конечная'):
            from core.pay_store import set_role_rule
            set_role_rule(con, bad, '2026-01-01')
        con.close()


class TestR17Seniority:
    def test_anniversary_exact(self):
        from core.payroll import _service_years
        from datetime import date

        assert _service_years('2025-10-01', date(2026, 10, 1)) == Decimal(1)
        assert _service_years('2025-10-01', date(2026, 9, 30)) == Decimal(0)
        assert _service_years('2020-02-29', date(2026, 2, 28)) == Decimal(6)


class TestR20DurationFormat:
    def test_monthly_durations_use_brackets(self, tmp_path):
        from datetime import timedelta as _td
        from core.day_models import EmployeeMonth, HolidayGroup, WageResult, WorkGroup
        from core.excel_builder import build_excel
        import openpyxl

        monkeypatch_cwd = tmp_path
        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            summary = {1: EmployeeMonth(
                work=WorkGroup(days=22, overtime=_td(hours=30), undertime=_td(0)),
                holiday=HolidayGroup(days=0, overtime=_td(0), undertime=_td(0), worked=_td(0)),
                vacation_days=0, truancy_days=0)}
            wages = {1: WageResult(Decimal('60000.00'), Decimal('880.00'), Decimal('60880.00'))}
            fn = build_excel({}, {}, summary, wages,
                             employees={1: EmployeeData(id=1, first_name='А', last_name='Б',
                                                        role_id=1, role_name='Р')},
                             year=2026, month=10)
            assert fn
            wb = openpyxl.load_workbook(fn)
            ws = wb.active
            found = [c.number_format for row in ws.iter_rows() for c in row
                     if c.value == _td(hours=30)]
            assert found and found[0] == '[h]:mm:ss'
        finally:
            os.chdir(cwd)


class TestR11Replay:
    def test_new_package_replays(self, tmp_path):
        import os
        from core.calculations import calculate_hours_per_month
        from core.pay_context import combined_staff_for_import, load_rules_map
        from core.pay_package import (build_new_package, file_meta, replay_package,
                                      save_package, staff_snapshot, verify_package_structure)
        from core.payroll import build_bundle

        import shutil

        cwd = os.getcwd()
        (tmp_path / 'data' / 'variable_data_for_app').mkdir(parents=True, exist_ok=True)
        for _fn in ('holidays.dat', 'postponed_working_days.dat'):
            _src = os.path.join('data', 'variable_data_for_app', _fn)
            if os.path.exists(_src):
                shutil.copy(_src, tmp_path / 'data' / 'variable_data_for_app' / _fn)
        os.chdir(tmp_path)
        try:
            db = _synth_db(tmp_path)
            from core.config import EmployeeData as _ED
            dat = {1: _ED(id=1, first_name='А', last_name='Цех', role_id=1, role_name='Р')}
            combined = combined_staff_for_import(dat, db, '2026-10-01')
            rules = load_rules_map(db, '2026-10-01', combined)
            da, wt = _full_month_tables(emp=1)
            summary, _ = calculate_hours_per_month(wt)
            bundle = build_bundle(da, wt, {1: summary[1]}, YEAR, MONTH, db,
                                  employees=combined, rules_by_role=rules)
            snap = staff_snapshot(db, [1], '2026-10-01', combined)
            pkg = build_new_package(
                bundle=bundle, data_array=da, journal=[], participants=[1],
                excluded={}, assignments=snap['assignments'], names=snap['names'],
                hires=snap['hires'], dat_meta=file_meta(None),
                db_meta=file_meta(db), reports=[], prev_package_id=None)
            assert verify_package_structure(pkg) == []
            path = save_package(pkg, str(tmp_path))
            rep = replay_package(path)
            assert rep['errors'] == [] and rep['checked'] == 1
        finally:
            os.chdir(cwd)


class TestE2EMatrix:
    @pytest.mark.parametrize('salary_mode', [True, False])
    @pytest.mark.parametrize('with_empty', [False, True])
    def test_new_model_matrix(self, tmp_path, salary_mode, with_empty):
        """Сквозная матрица new × salary × empty: состав и деньги сходятся."""
        import os
        from core.calculations import (calculate_hours_per_day, calculate_hours_per_month)
        from core.pay_context import combined_staff_for_import, load_rules_map
        from core.payroll import build_bundle, bundle_to_wages

        db = _synth_db(tmp_path)
        from core.config import EmployeeData as _ED
        dat = {1: _ED(id=1, first_name='А', last_name='Цех', role_id=1, role_name='Р')}
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        rules = load_rules_map(db, '2026-10-01', combined)
        da, wt_raw = _full_month_tables(emp=1)
        if with_empty:
            # Второй участник без отметок — нулевая месячная запись.
            from datetime import timedelta as _td
            from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup
            wt = dict(wt_raw)
        else:
            wt = wt_raw
        work_time = calculate_hours_per_day(da, employees=combined, rules_by_role=rules)
        summary, _ = calculate_hours_per_month(work_time)
        if with_empty:
            from datetime import timedelta as _td
            from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup
            summary[2] = EmployeeMonth(
                work=WorkGroup(0, _td(0), _td(0)),
                holiday=HolidayGroup(0, _td(0), _td(0), _td(0)),
                vacation_days=0, truancy_days=0)
            # Участник 2 должен существовать в штате/БД для назначений.
            from core.pay_store import connect, upsert_employee, assign_role
            con = connect(db)
            try:
                upsert_employee(con, 2, 'К', 'Кладовщик', '2020-01-01')
                try:
                    assign_role(con, 2, 2, '2026-01-01')
                except ValueError:
                    pass
            finally:
                con.close()
            combined[2] = _ED(id=2, first_name='К', last_name='Кладовщик',
                              role_id=2, role_name='Кладовщик')
            rules = load_rules_map(db, '2026-10-01', combined)
        bundle = build_bundle(da, work_time, summary, YEAR, MONTH, db,
                              salary_mode=salary_mode,
                              employees=combined, rules_by_role=rules)
        wages = bundle_to_wages(bundle)
        for emp_id, res in bundle.results.items():
            assert wages[emp_id].salary == res.result.total or salary_mode is False
            if salary_mode is False:
                assert wages[emp_id].salary == Decimal('0.00')
        if not with_empty:
            assert set(bundle.results) == {1}
