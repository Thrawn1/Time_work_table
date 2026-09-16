"""F02-union: SQLite-only сотрудник проходит импорт и расчёт."""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import EmployeeData

YEAR, MONTH = 2026, 10


def _dt(day_key, hm):
    return datetime.strptime(f'{day_key} {hm}', '%Y-%m-%d %H:%M')


def _db_with_sqlite_only(tmp_path):
    from core.pay_store import init_db, seed_defaults, upsert_employee, assign_role
    db = str(tmp_path / 'union.db')
    con = init_db(db)
    seed_defaults(con)
    upsert_employee(con, 900, 'Новый', 'Сотрудник', '2020-01-01')
    try:
        assign_role(con, 900, 1, '2026-01-01')
    except ValueError:
        pass
    con.close()
    return db


class TestCombinedStaff:
    def test_sqlite_only_included_with_sqlite_role(self, tmp_path):
        from core.pay_context import combined_staff_for_import
        dat = {1: EmployeeData(id=1, first_name='А', last_name='Б',
                               role_id=2, role_name='Кладовщик')}
        db = _db_with_sqlite_only(tmp_path)
        # overlapping ID 1: DAT role 2 vs SQLite? 1 has no SQLite assignment here
        # (only 900) — DAT role preserved; 900 added with role 1.
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        assert 900 in combined
        assert combined[900].role_id == 1
        assert combined[900].last_name == 'Сотрудник'

    def test_overlapping_role_sqlite_wins(self, tmp_path):
        from core.pay_context import combined_staff_for_import
        from core.pay_store import connect, upsert_employee, assign_role
        db = _db_with_sqlite_only(tmp_path)
        con = connect(db)
        upsert_employee(con, 1, 'А', 'Б', '2020-01-01')
        try:
            assign_role(con, 1, 1, '2026-01-01')
        except ValueError:
            pass
        con.close()
        dat = {1: EmployeeData(id=1, first_name='А', last_name='Б',
                               role_id=2, role_name='Кладовщик')}
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        assert combined[1].role_id == 1


class TestUnionImportAndBundle:
    def test_dat_drops_but_combined_keeps(self, tmp_path):
        from core.data_array import build_data_array
        from core.pay_context import combined_staff_for_import
        dat = {1: EmployeeData(id=1, first_name='А', last_name='Б',
                               role_id=1, role_name='Р')}
        db = _db_with_sqlite_only(tmp_path)
        combined = combined_staff_for_import(dat, db, '2026-10-01')
        lines = ['900 2026-10-06 08:00:00', '900 2026-10-06 16:00:00']
        dropped = build_data_array(lines, employees=dat)
        assert dropped == {}
        kept = build_data_array(lines, employees=combined)
        assert '2026-10-06' in kept and 900 in kept['2026-10-06']

    def test_exclusion_reason_uses_passed_staff(self):
        from core.data_array import exclusion_reason, is_included_in_settlement
        combined = {900: EmployeeData(id=900, first_name='Н', last_name='С',
                                      role_id=1, role_name='Р')}
        assert exclusion_reason(900) != ''
        assert exclusion_reason(900, combined) == ''
        assert is_included_in_settlement(900, combined) is True

    def test_bundle_includes_sqlite_only(self, tmp_path, monkeypatch):
        from core import analysis, data_array
        from core.payroll import build_bundle
        from core.pay_context import combined_staff_for_import
        dat = {900: EmployeeData(id=900, first_name='Н', last_name='С',
                                 role_id=1, role_name='Р')}
        # DAT-глобалы тоже знают 900, чтобы _get_marks_and_missed не влиял
        monkeypatch.setattr(data_array, 'EMPLOYEES', dat)
        monkeypatch.setattr(analysis, 'EMPLOYEES', dat)
        db = _db_with_sqlite_only(tmp_path)
        combined = combined_staff_for_import({}, db, '2026-10-01')
        assert 900 in combined
        da = {'2026-10-06': {900: [_dt('2026-10-06', '16:00'),
                                   _dt('2026-10-06', '08:00'), 'work']}}
        wt = {'2026-10-06': {900: (timedelta(0), timedelta(hours=8),
                                    'недоработка', 'work')}}
        summary = {900: ((1, timedelta(0), timedelta(0)),
                          (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        bundle = build_bundle(da, wt, summary, YEAR, MONTH, db, employees=combined)
        assert 900 in bundle.results
        assert bundle.results[900].name != 'ID 900'
