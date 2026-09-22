"""Этап 6: воспроизводимый пакет расчёта и журнал (F08)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from core.config import EmployeeData
from core.pay_calendar import month_date_keys, working_days_in_month
from core.pay_store import connect, init_db, migrate_from_dat, seed_defaults
from core.payroll import build_bundle

YEAR, MONTH = 2026, 10


@pytest.fixture
def paydb(tmp_path):
    from tests.synth_data import write_synth_dat_dir

    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    seed_defaults(con)
    migrate_from_dat(con, write_synth_dat_dir(tmp_path / 'synth'))
    con.close()
    return db


@pytest.fixture
def emp_patch(monkeypatch):
    from core import analysis, data_array
    emps = {
        1: EmployeeData(id=1, first_name='А', last_name='Цеховик',
                        role_id=1, role_name='Работник цеха'),
    }
    monkeypatch.setattr(data_array, 'EMPLOYEES', emps)
    monkeypatch.setattr(analysis, 'EMPLOYEES', emps)
    return emps


def _dt(day_key: str, hm: str) -> datetime:
    return datetime.strptime(f'{day_key} {hm}', '%Y-%m-%d %H:%M')


def make_tables():
    from core.pay_calendar import workday_keys_in_month
    data_array, work_time = {}, {}
    for key in workday_keys_in_month(YEAR, MONTH):
        out, inn = _dt(key, '16:00'), _dt(key, '08:00')
        data_array.setdefault(key, {})[1] = [out, inn, 'work']
        work_time.setdefault(key, {})[1] = (timedelta(0), timedelta(hours=8),
                                            'норма', 'work')
    return data_array, work_time


def make_bundle(paydb):
    from core.calculations import calculate_hours_per_month
    data_array, work_time = make_tables()
    summary, _ = calculate_hours_per_month(work_time)
    summary = {1: summary[1]}
    return data_array, work_time, summary, build_bundle(
        data_array, work_time, summary, YEAR, MONTH, paydb)


def test_rule_versions_record_actual_effective_dates(paydb, emp_patch):
    data_array, work_time, summary, bundle = make_bundle(paydb)
    assert bundle.rule_versions[1] == '2026-01-01'  # было month_start 2026-10-01 (F08.1)
    assert bundle.seniority_eff is None
    snap = bundle.versions_snapshot()
    assert snap['role_rule_versions'] == {'1': '2026-01-01'}
    assert snap['seniority_scale']['effective_from'] is None


def test_seniority_version_recorded(paydb, emp_patch):
    from core.pay_store import set_seniority_scale
    con = connect(paydb)
    set_seniority_scale(con, '2026-01-01', [(0, Decimal('0')), (5, Decimal('0.10'))])
    con.close()
    _, _, _, bundle = make_bundle(paydb)
    assert bundle.seniority_eff == '2026-01-01'
    assert bundle.versions_snapshot()['seniority_scale']['thresholds'] == [
        [0, '0'], [5, '0.10']]


def test_package_revisions_increment_and_link(paydb, emp_patch, tmp_path):
    from core.pay_package import (
        build_new_package, file_meta, list_revisions, load_package,
        next_revision, save_package, staff_snapshot,
    )
    d = str(tmp_path)
    data_array, work_time, summary, bundle = make_bundle(paydb)
    journal = [{'ts': '2026-10-01T10:00:00', 'emp_id': 1, 'action': 'x',
                'before': '—', 'after': '08:00 -> 16:00 [work]'}]
    snap = staff_snapshot(paydb, [1], f'{YEAR}-{MONTH:02d}-01', emp_patch)
    rev, prev = next_revision(YEAR, MONTH, d)
    assert (rev, prev) == (1, None)
    pkg = build_new_package(
        bundle=bundle, data_array=data_array, journal=journal,
        participants=[1], excluded={}, assignments=snap['assignments'],
        names=snap['names'], hires=snap['hires'],
        dat_meta=file_meta(None), db_meta=file_meta(paydb),
        reports=[], prev_package_id=prev)
    p1 = save_package(pkg, d)
    assert p1.endswith('payroll_2026_10_rev01.json')
    rev, prev2 = next_revision(YEAR, MONTH, d)
    assert rev == 2
    pkg2 = build_new_package(
        bundle=bundle, data_array=data_array, journal=journal,
        participants=[1], excluded={1: 'тест'}, assignments=snap['assignments'],
        names=snap['names'], hires=snap['hires'],
        dat_meta=file_meta(None), db_meta=file_meta(paydb),
        reports=[], prev_package_id=prev2)
    p2 = save_package(pkg2, d)
    assert p2.endswith('payroll_2026_10_rev02.json')
    assert [r for r, _ in list_revisions(YEAR, MONTH, d)] == [1, 2]
    first, second = load_package(p1), load_package(p2)
    assert second['prev_package_id'] == first['package_id'] != second['package_id']
    assert first['excluded'] == {} and second['excluded'] == {'1': 'тест'}


def test_package_explains_totals(paydb, emp_patch, tmp_path):
    from core.pay_package import build_new_package, save_package, staff_snapshot
    d = str(tmp_path)
    data_array, work_time, summary, bundle = make_bundle(paydb)
    snap = staff_snapshot(paydb, [1], f'{YEAR}-{MONTH:02d}-01', emp_patch)
    pkg = build_new_package(
        bundle=bundle, data_array=data_array, journal=[],
        participants=[1], excluded={}, assignments=snap['assignments'],
        names=snap['names'], hires=snap['hires'],
        dat_meta={}, db_meta={}, reports=[], prev_package_id=None)
    entry = pkg['results']['1']
    res = {k: Decimal(v) if k not in ('full_month_ok', 'full_month_reason') else v
           for k, v in entry['result'].items()}
    assert res['total'] == (res['ordinary_pay'] + res['overtime_bonus']
                            + res['full_month_bonus'] + res['seniority_bonus'])
    assert res['total'] == bundle.results[1].result.total
    assert entry['inputs']['fact_hours'] == str(bundle.results[1].inputs.fact_hours)
    assert pkg['calendar']['D'] == bundle.workdays
    assert len(pkg['calendar']['dates']) == len(month_date_keys(YEAR, MONTH))
    work_kinds = [k for k, v in pkg['calendar']['dates'].items() if v == 'work']
    assert len(work_kinds) == working_days_in_month(YEAR, MONTH)
    assert pkg['marks']  # отметки после правок внутри
    assert pkg['settings']['effective_from'] == '2026-01-01'
    assert pkg['rules']['1']['effective_from'] == '2026-01-01'


def test_journal_survives_session_file(tmp_path, monkeypatch):
    from core.analysis import clear_journal, get_journal, restore_journal
    from core.session import (
        load_session_with_journal, save_session, validate_session_raw,
    )
    monkeypatch.chdir(tmp_path)
    clear_journal()
    table = {'2026-10-01': {1: [datetime(2026, 10, 1, 16), datetime(2026, 10, 1, 8), 'work']}}
    journal = [{'ts': '2026-10-02T09:00:00', 'emp_id': 1, 'name': 'Тест',
                'date': '2026-10-01', 'action': 'edit',
                'before': '—', 'after': '08:00 -> 16:00 [work]'}]
    save_session(table, 2026, 10, journal=journal)
    loaded, back = load_session_with_journal()
    assert loaded is not None and back == journal
    restore_journal(back)
    assert get_journal() == journal
    clear_journal()
    assert get_journal() == []
    _, errors = validate_session_raw({'version': 2, 'entries': {}, 'journal': 'x',
                                      'period': {'year': 2026, 'month': 10}})
    assert errors
    # R09: запись без обязательных полей отклоняется до отчётов.
    _, errors2 = validate_session_raw({
        'version': 2,
        'entries': {'2026-10-01': {'1': ['2026-10-01T16:00:00', '2026-10-01T08:00:00', 'work']}},
        'journal': [{'ts': 'x'}],
        'period': {'year': 2026, 'month': 10}})
    assert errors2


def test_legacy_package_roundtrip(tmp_path):
    from core.pay_package import build_legacy_package, load_package, save_package
    d = str(tmp_path)
    data_array, work_time = make_tables()
    from core.calculations import calculate_hours_per_month
    summary, _ = calculate_hours_per_month(work_time)
    from core.day_models import WageResult
    wages = {1: WageResult(salary=Decimal('800.00'), milk=Decimal('40.00'),
                           total_with_milk=Decimal('840.00'))}
    pkg = build_legacy_package(
        year=YEAR, month=MONTH, salary_mode=True, data_array=data_array,
        journal=[], summary={1: summary[1]}, wages=wages, rates_meta={},
        participants=[1], excluded={}, names={1: 'А Цеховик'},
        dat_meta={}, reports=[], prev_package_id=None)
    assert pkg['algorithm'] == 'legacy'
    assert pkg['results']['1'] == {'salary': '800.00', 'milk': '40.00',
                                   'total_with_milk': '840.00'}
    path = save_package(pkg, d)
    assert load_package(path)['package_id'] == pkg['package_id']
    import json
    bad = dict(pkg, package_version=999)
    bad_path = tmp_path / 'bad.json'
    bad_path.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='версия пакета'):
        load_package(str(bad_path))


def test_main_smoke_two_revisions_keep_history(tmp_path, monkeypatch, capsys):
    """Сквозной main(): rev01→rev02 без перезаписи, сессия удалена после пакета."""
    import json
    import shutil
    import sys

    import main as main_mod

    shutil.copytree('data/variable_data_for_app',
                    tmp_path / 'data' / 'variable_data_for_app')
    (tmp_path / 'data' / '1_attlog.dat').write_text(
        '1 2026-10-01 08:00:00\n1 2026-10-01 16:00:00\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    argv = ['main.py', '-f', '1_attlog.dat', '-y', '2026', '-m', '10',
            '-k', 't', '--no-edit']
    monkeypatch.setattr(sys, 'argv', argv)
    main_mod.main()
    capsys.readouterr()
    rev1 = tmp_path / 'result' / 'payroll_2026_10_rev01.json'
    assert rev1.exists()
    pkg1 = json.loads(rev1.read_text(encoding='utf-8'))
    assert pkg1['algorithm'] == 'legacy' and pkg1['revision'] == 1
    assert pkg1['prev_package_id'] is None
    assert pkg1['results'] and pkg1['marks'] and pkg1['calendar']['D'] > 0
    assert not (tmp_path / 'result' / 'temporary.json').exists()
    # Повторный запуск — новая ревизия со связью, первая цела.
    before = rev1.read_bytes()
    monkeypatch.setattr(sys, 'argv', argv)
    main_mod.main()
    capsys.readouterr()
    rev2 = tmp_path / 'result' / 'payroll_2026_10_rev02.json'
    assert rev2.exists()
    assert rev1.read_bytes() == before
    pkg2 = json.loads(rev2.read_text(encoding='utf-8'))
    assert pkg2['revision'] == 2
    assert pkg2['prev_package_id'] == pkg1['package_id']
